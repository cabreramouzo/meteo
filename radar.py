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
# per avisar volem estar MOLT segurs: pluja moderada (no el fleco) prevista
# sobre el poble dins d'un horitzo curt, amb una extensio minima
HORITZO_MIN = 60
AREA_IMPACTE_MODERADA_KM2 = 8.0
# only large rain masses count (fronts, not isolated showers):
AREA_MINIMA_KM2 = 100.0
# RainViewer ignora el parametro de paleta en la URL: sempre torna la
# mateixa (TWC), aixi que classifiquem per color. Ordre d'intensitat
# calibrat empiricament (distancia mitjana als nuclis grocs del radar):
# cian clar (mes feble) -> blau clar -> blau mitja -> blau fosc ->
# groc/taronja/vermell -> rosa. El canal R NO es monoton amb la intensitat.
ALFA_MINIM = 100          # real rain pixels are alpha >= 110 (mostly 255)
# RainViewer also paints a translucent grey/beige field (alpha ~50-70,
# e.g. RGB(127,120,103)) for sub-threshold echo / clutter fanning out from
# the radar site. It is not precipitation: reject low-saturation pixels
SATURACIO_MINIMA = 40
NIVELL_MODERAT = 3        # dark blue or warmer: real rain, not drizzle
# a mass only counts if it carries a considerable amount of moderate rain
# (the 25-jul false positive was all light blue) and is large enough
AREA_MODERADA_MIN_KM2 = 60.0
# emparellament de masses entre frames: descartem salts impossibles
VELOCITAT_MAX_KM_30MIN = 60.0
# ventana de historia (frames de ~10 min) para decidir el re-armado
REFRACTARI_FRAMES = 6
# histeresis (dos umbrales) sobre el eco dentro del disco de alarma: la
# tormenta se considera activa por encima de LLIND_ACTIU y en calma por
# debajo de LLIND_CALMA. La alarma se re-arma tras una calma, asi un frente
# que cruza no repite, pero una tormenta que s'afluixa i es reanima si torna
# a avisar
# calibrats amb la sortida real del 25-jul (pluja moderada dins del disc,
# la tempesta marxant: 105 -> 36 -> 3 -> 0 km2)
LLIND_ACTIU_KM2 = 25.0
LLIND_CALMA_KM2 = 3.0

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


def is_precip(r, g, b, a):
  """True for a pixel that is actual precipitation (opaque enough and a
  saturated colour), False for background/clutter greys."""
  return a >= ALFA_MINIM and (max(r, g, b) - min(r, g, b)) >= SATURACIO_MINIMA


def nivell(r, g, b):
  """Intensity level 0-5 from the radar colour (TWC palette). Within the
  blues, darker is stronger; warm colours are the cores. Calibrated by
  measuring each colour's mean distance to the storm cores."""
  if (max(r, g, b) - min(r, g, b)) < SATURACIO_MINIMA:
    return 0                # grey: clutter / sub-threshold echo
  if b > r + 30:            # blue family
    if g >= 190: return 0   # cian clar: plugim
    if g >= 150: return 1   # blau clar: feble
    if g >= 110: return 2   # blau mitja: feble-moderada
    return 3                # blau fosc: moderada
  if r > 200 and b > 150:
    return 5                # rosa/blanc: calamarsa
  return 4                  # groc/taronja/vermell: forta


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


def big_masses(host, frame, mostra_max=600):
  """Masas de lluvia prou grans (>= AREA_MINIMA_KM2) i amb prou pluja
  moderada (>= AREA_MODERADA_MIN_KM2) dins del radi d'escaneig. Torna
  [{area_km2, area_moderada_km2, dist_km, centre_km, petjada_km}], amb la
  petjada mostrejada en km relatius al poble per poder-la traslladar."""
  canvas, (vx, vy) = _stitch(_radar_url(host, frame, 0, '0_0'), RADAR_SIZE * RADAR_ESCALA,
                             RADI_ESCANEIG_KM, escala=RADAR_ESCALA, resample=Image.NEAREST)
  kmpx = km_per_pixel()
  ample = canvas.width
  r_px = RADI_ESCANEIG_KM / kmpx

  ecos = {}
  for i, (r, g, b, a) in enumerate(canvas.getdata()):
    if not is_precip(r, g, b, a):
      continue
    x, y = i % ample, i // ample
    if abs(x - vx) > r_px or abs(y - vy) > r_px:
      continue
    ecos[(x, y)] = nivell(r, g, b)

  masas = []
  for comp in _components(ecos.keys()):
    area = len(comp) * kmpx * kmpx
    if area < AREA_MINIMA_KM2:
      continue
    moderada = sum(1 for p in comp if ecos[p] >= NIVELL_MODERAT) * kmpx * kmpx
    if moderada < AREA_MODERADA_MIN_KM2:
      continue  # tota plugim: no avisem
    dist = min(math.hypot(x - vx, y - vy) for x, y in comp) * kmpx
    if dist > RADI_ESCANEIG_KM:
      continue
    cx = sum(x for x, _ in comp) / len(comp)
    cy = sum(y for _, y in comp) / len(comp)
    pas = max(1, len(comp) // mostra_max)
    petjada = [((x - vx) * kmpx, (y - vy) * kmpx, ecos[(x, y)]) for x, y in comp[::pas]]
    masas.append({'area_km2': round(area, 1), 'area_moderada_km2': round(moderada, 1),
                  'dist_km': round(dist, 1), 'centre_km': ((cx - vx) * kmpx, (cy - vy) * kmpx),
                  'petjada_km': petjada, 'km2_per_mostra': pas * kmpx * kmpx})
  return masas


def nearest_mass_km(masas):
  return min((m['dist_km'] for m in masas), default=None)


def echo_area_within_km2(host, frame, radi_km=RADI_ALARMA_KM, nivell_minim=NIVELL_MODERAT):
  """Area (km2) de pluja d'intensitat >= nivell_minim dins del disc de
  radi_km al voltant del poble. Barat (retalla al disc): per la histeresi
  sobre els frames passats."""
  canvas, (vx, vy) = _stitch(_radar_url(host, frame, 0, '0_0'), RADAR_SIZE * RADAR_ESCALA,
                             radi_km, escala=RADAR_ESCALA, resample=Image.NEAREST)
  kmpx = km_per_pixel()
  r_px = radi_km / kmpx
  box = (int(vx - r_px), int(vy - r_px), math.ceil(vx + r_px), math.ceil(vy + r_px))
  disc = canvas.crop(box)
  ample = disc.width
  cx, cy = vx - box[0], vy - box[1]
  n = sum(1 for i, (r, g, b, a) in enumerate(disc.getdata())
          if is_precip(r, g, b, a) and nivell(r, g, b) >= nivell_minim
          and math.hypot(i % ample - cx, i // ample - cy) <= r_px)
  return n * kmpx * kmpx


def armed_after_lull(intensitats):
  """intensitats: eco (km2) dentro del disco de alarma en los frames
  anteriores, en orden cronologico. Devuelve si la alarma esta re-armada:
  hubo una calma (<= LLIND_CALMA_KM2) despues del ultimo tramo con tormenta
  activa (>= LLIND_ACTIU_KM2). Histeresis: un front que travessa no repeteix
  (sigue actiu tot el rato), pero si s'afluixa fins a la calma i es reanima,
  torna a armar-se."""
  armat = True
  for a in intensitats:
    if a >= LLIND_ACTIU_KM2:
      armat = False
    elif a <= LLIND_CALMA_KM2:
      armat = True
  return armat


def _moderada_sobre_poble_km2(masa, dx=0.0, dy=0.0):
  """km2 de pluja moderada+ de la petjada (traslladada dx,dy) que cauen a
  menys de RADI_IMPACTE_KM del poble."""
  n = sum(1 for x, y, niv in masa['petjada_km']
          if niv >= NIVELL_MODERAT and math.hypot(x + dx, y + dy) <= RADI_IMPACTE_KM)
  return n * masa['km2_per_mostra']


def impact_predicted(masas_abans, masas_ara, horitzo_min=HORITZO_MIN):
  """Extrapola el moviment de la massa mes propera (centroide fa 30 min ->
  ara) i nomes dona impacte si, dins de l'horitzo, cau PLUJA MODERADA (no
  el fleco blau clar) sobre el poble amb una extensio minima. Traslladem
  la forma real: una massa que passa de llarg no compta, encara que sigui
  gran."""
  if not masas_ara:
    return False
  masa = min(masas_ara, key=lambda m: m['dist_km'])
  if _moderada_sobre_poble_km2(masa) >= AREA_IMPACTE_MODERADA_KM2:
    return True  # ja plou moderat a sobre
  if not masas_abans:
    return False

  cx, cy = masa['centre_km']
  previa = min(masas_abans,
               key=lambda m: math.hypot(m['centre_km'][0] - cx, m['centre_km'][1] - cy))
  px, py = previa['centre_km']
  vx30, vy30 = cx - px, cy - py  # km per 30 min
  desplacament = math.hypot(vx30, vy30)
  if desplacament < 1:                        # practicament estatica
    return False
  if desplacament > VELOCITAT_MAX_KM_30MIN:   # emparellament poc fiable
    return False

  for t in range(10, horitzo_min + 1, 10):
    if _moderada_sobre_poble_km2(masa, vx30 * t / 30, vy30 * t / 30) >= AREA_IMPACTE_MODERADA_KM2:
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
  capa = radar.crop(caixa_radar)
  # drop the grey clutter field so the capture shows real rain only
  capa.putdata([(r, g, b, a if is_precip(r, g, b, a) else 0) for r, g, b, a in capa.getdata()])
  img = Image.alpha_composite(mapa.crop(caixa_mapa), capa)
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
