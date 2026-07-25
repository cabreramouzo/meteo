import io
import math
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
from PIL import Image, ImageDraw

# Deteccion de lluvia acercandose al pueblo con el radar agregado de
# RainViewer (frames cada ~10 min). La alarma salta en el flanco de subida
# (llega un frente grande al radio de alarma con trayectoria de impacto) y
# un refractario evita re-disparar mientras siga lloviendo sobre el pueblo:
# todo sin estado, mirando el histgrico de frames que da RainViewer.
#
# Escalas: RainViewer solo sirve radar real hasta zoom 7 (mas alla devuelve
# un placeholder "Zoom Level Not Supported"). Trabajamos en el espacio de
# pixeles de OSM z9 a 256px y reescalamos los tiles de radar z7/512 (x2)
# para encajarlos; _stitch detecta placeholders por si RainViewer cambia.

LAT = 41.770358
LON = 2.154847

PIXEL_ZOOM = 9   # el espacio de pixeles comun equivale a z9 con tiles de 256
OSM_ZOOM, OSM_SIZE = 9, 256
RADAR_ZOOM, RADAR_SIZE, RADAR_ESCALA = 7, 512, 2  # 512*2 = 1024 px globales/tile

RADI_ALARMA_KM = 10.0
RADI_ESCANEIG_KM = 40.0  # hasta donde buscamos el eco mas cercano
RADI_IMPACTE_KM = 3.0    # "pasa por el pueblo" = eco previsto a menos de esto
# solo cuentan masas de lluvia grandes (frentes, no chubascos sueltos):
AREA_MINIMA_KM2 = 50.0
# umbral sobre la escala de grises dBZ de RainViewer (color 0): filtra
# ecos debiles (virga, llovizna residual) que no suelen llegar al suelo
GRIS_MINIM = 40
# refractario: no re-disparar si ya llovia sobre el pueblo en alguno de los
# ultimos N frames (~10 min cada uno). Un frente que cruza sigue "dentro"
# mientras pasa, asi que solo un frente nuevo tras un claro re-arma
REFRACTARI_FRAMES = 6
# eco dentro del disco de alarma para considerar que "llueve sobre el pueblo"
LLIND_INTERIOR_KM2 = 20.0

API_MAPS = 'https://api.rainviewer.com/public/weather-maps.json'
UA = {'User-Agent': 'meteoCastellcir-bot/1.0 (+https://twitter.com/meteoCastellcir)'}


def km_per_pixel():
  return 40075.016686 * math.cos(math.radians(LAT)) / (2 ** PIXEL_ZOOM * 256)


def _village_px():
  # posicion del pueblo en el espacio de pixeles global
  n = 2 ** PIXEL_ZOOM
  x = (LON + 180) / 360 * n
  y = (1 - math.asinh(math.tan(math.radians(LAT))) / math.pi) / 2 * n
  return x * 256, y * 256


def get_frames():
  maps = requests.get(API_MAPS, headers=UA, timeout=20).json()
  return maps['host'], maps['radar']['past'], maps['radar'].get('nowcast') or []


def _stitch(url_fn, tile_px, radi_km, escala=1, resample=Image.BILINEAR):
  """Cose los tiles que cubren un radio en km alrededor del pueblo.
  tile_px es el tamano del tile en pixeles globales (imagen fetcheada x
  escala). Devuelve (canvas, posicion del pueblo dentro del canvas)."""
  vx, vy = _village_px()
  r_px = radi_km / km_per_pixel()
  x0, x1 = int((vx - r_px) // tile_px), int((vx + r_px) // tile_px)
  y0, y1 = int((vy - r_px) // tile_px), int((vy + r_px) // tile_px)

  canvas = Image.new('RGBA', ((x1 - x0 + 1) * tile_px, (y1 - y0 + 1) * tile_px), (0, 0, 0, 0))
  vistos = {}
  for xt in range(x0, x1 + 1):
    for yt in range(y0, y1 + 1):
      r = requests.get(url_fn(xt, yt), headers=UA, timeout=20)
      r.raise_for_status()
      tile = Image.open(io.BytesIO(r.content)).convert('RGBA')
      # dos tiles de coordenadas distintas con identico contenido no vacio
      # = placeholder tipo "Zoom Level Not Supported"
      if r.content in vistos and any(p[3] > 0 for p in tile.getdata()):
        raise ValueError(f'tile placeholder detectado en {url_fn(xt, yt)}')
      vistos[r.content] = (xt, yt)
      if escala != 1:
        tile = tile.resize((tile.width * escala, tile.height * escala), resample)
      if tile.size != (tile_px, tile_px):
        raise ValueError(f'tile inesperado {tile.size} de {url_fn(xt, yt)}')
      canvas.paste(tile, ((xt - x0) * tile_px, (yt - y0) * tile_px))
  return canvas, (vx - x0 * tile_px, vy - y0 * tile_px)


def _radar_url(host, frame, color, options):
  return lambda xt, yt: f"{host}{frame['path']}/{RADAR_SIZE}/{RADAR_ZOOM}/{xt}/{yt}/{color}/{options}.png"


def _components(pixels):
  """Agrupa pixeles de eco en componentes conexas (8-conectividad)."""
  restantes = set(pixels)
  comps = []
  while restantes:
    pila = [restantes.pop()]
    comp = list(pila)
    while pila:
      x, y = pila.pop()
      for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
          v = (x + dx, y + dy)
          if v in restantes:
            restantes.remove(v)
            pila.append(v)
            comp.append(v)
    comps.append(comp)
  return comps


def big_masses(host, frame):
  """Masas de lluvia de area >= AREA_MINIMA_KM2 dentro del radio de
  escaneo. Devuelve [{area_km2, dist_km, centre_km}] con el centroide en
  km relativos al pueblo."""
  # color 0 = escala de grises con los dBZ, sin suavizar: para medir
  canvas, (vx, vy) = _stitch(_radar_url(host, frame, 0, '0_0'), RADAR_SIZE * RADAR_ESCALA,
                             RADI_ESCANEIG_KM, escala=RADAR_ESCALA, resample=Image.NEAREST)
  kmpx = km_per_pixel()
  ample = canvas.width
  r_px = RADI_ESCANEIG_KM / kmpx
  ecos = [(i % ample, i // ample) for i, (r, g, b, a) in enumerate(canvas.getdata())
          if a > 0 and r >= GRIS_MINIM
          and abs(i % ample - vx) <= r_px and abs(i // ample - vy) <= r_px]

  masas = []
  for comp in _components(ecos):
    area = len(comp) * kmpx * kmpx
    if area < AREA_MINIMA_KM2:
      continue
    dist = min(math.hypot(x - vx, y - vy) for x, y in comp) * kmpx
    if dist > RADI_ESCANEIG_KM:
      continue
    cx = sum(x for x, _ in comp) / len(comp)
    cy = sum(y for _, y in comp) / len(comp)
    masas.append({'area_km2': round(area, 1), 'dist_km': round(dist, 1),
                  'centre_km': ((cx - vx) * kmpx, (cy - vy) * kmpx)})
  return masas


def nearest_mass_km(masas):
  return min((m['dist_km'] for m in masas), default=None)


def echo_area_within_km2(host, frame, radi_km=RADI_ALARMA_KM):
  """Area de eco (km2) dentro del disco de radi_km alrededor del pueblo.
  Barato (recorta al disco): para el refractario sobre frames pasados."""
  canvas, (vx, vy) = _stitch(_radar_url(host, frame, 0, '0_0'), RADAR_SIZE * RADAR_ESCALA,
                             radi_km, escala=RADAR_ESCALA, resample=Image.NEAREST)
  kmpx = km_per_pixel()
  r_px = radi_km / kmpx
  box = (int(vx - r_px), int(vy - r_px), math.ceil(vx + r_px), math.ceil(vy + r_px))
  disc = canvas.crop(box)
  ample = disc.width
  cx, cy = vx - box[0], vy - box[1]
  n = sum(1 for i, (r, g, b, a) in enumerate(disc.getdata())
          if a > 0 and r >= GRIS_MINIM and math.hypot(i % ample - cx, i // ample - cy) <= r_px)
  return n * kmpx * kmpx


def raining_over_village(host, frame):
  return echo_area_within_km2(host, frame) >= LLIND_INTERIOR_KM2


def impact_predicted(masas_abans, masas_ara, horitzo_min=90):
  """Sin nowcast: extrapola el movimiento de la masa mas cercana (centroide
  hace 30 min -> ahora) y mira si en el horizonte dado pasara a menos de
  RADI_IMPACTE_KM del pueblo."""
  if not masas_ara:
    return False
  masa = min(masas_ara, key=lambda m: m['dist_km'])
  if masa['dist_km'] <= RADI_IMPACTE_KM:
    return True
  if not masas_abans:
    return False
  cx, cy = masa['centre_km']
  # la masa de hace 30 min con el centroide mas parecido
  px, py = min((m['centre_km'] for m in masas_abans),
               key=lambda c: math.hypot(c[0] - cx, c[1] - cy))
  vx30, vy30 = cx - px, cy - py  # km por 30 min
  if math.hypot(vx30, vy30) < 1:  # practicamente estatica
    return False
  # seguimos el centroide: hay impacto si pasa a menos del radio de
  # impacto mas el radio efectivo de la propia masa
  llindar = RADI_IMPACTE_KM + math.sqrt(masa['area_km2'] / math.pi)
  for t in range(10, horitzo_min + 1, 10):
    if math.hypot(cx + vx30 * t / 30, cy + vy30 * t / 30) <= llindar:
      return True
  return False


def build_radar_image(host, frame, mida=480):
  """Compone la captura: mapa OSM + radar + marcador y circulo de alarma."""
  radi_vista_km = mida / 2 * km_per_pixel()
  url_osm = lambda xt, yt: f'https://tile.openstreetmap.org/{OSM_ZOOM}/{xt}/{yt}.png'
  mapa, (vx, vy) = _stitch(url_osm, OSM_SIZE, radi_vista_km)
  # color 4 = paleta The Weather Channel, suavizada y sin color de nieve
  # aparte: visible incluso con lluvia debil
  radar, (rx, ry) = _stitch(_radar_url(host, frame, 4, '1_0'), RADAR_SIZE * RADAR_ESCALA,
                            radi_vista_km, escala=RADAR_ESCALA)
  radar.putalpha(radar.getchannel('A').point(lambda a: int(a * 0.8)))

  # alineo los dos canvas por la posicion del pueblo y recorto centrado
  caixa_mapa = (int(vx - mida / 2), int(vy - mida / 2), int(vx + mida / 2), int(vy + mida / 2))
  caixa_radar = (int(rx - mida / 2), int(ry - mida / 2), int(rx + mida / 2), int(ry + mida / 2))
  img = Image.alpha_composite(mapa.crop(caixa_mapa), radar.crop(caixa_radar))
  cx = cy = mida / 2

  draw = ImageDraw.Draw(img)
  r_px = RADI_ALARMA_KM / km_per_pixel()
  draw.ellipse([cx - r_px, cy - r_px, cx + r_px, cy + r_px], outline=(220, 30, 30, 255), width=3)
  draw.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=(220, 30, 30, 255), outline=(255, 255, 255, 255), width=2)

  hora = datetime.fromtimestamp(frame['time'], ZoneInfo('Europe/Madrid')).strftime('%d/%m/%Y %H:%M')
  peu = f"Radar {hora} · RainViewer · Mapa © OpenStreetMap"
  draw.rectangle([0, mida - 22, mida, mida], fill=(0, 0, 0, 160))
  draw.text((8, mida - 17), peu, fill=(255, 255, 255, 255))

  return img.convert('RGB')
