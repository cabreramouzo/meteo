from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import re
import emoji
import random
import requests
from config import get_meteocat_key

ID_COMARCA = 42  # Moianès


def random_moon_emoji():
  n = random.randrange(0, 5, 1)
  moons = [
    emoji.emojize(':full_moon_face:'),
    emoji.emojize(':new_moon_face:'),
    emoji.emojize(':crescent_moon:'),
    emoji.emojize(':first_quarter_moon_face:'),
    emoji.emojize(':last_quarter_moon_face:'),
  ]
  return moons[n]


def random_sun_emoji():
  n = random.randrange(0, 2, 1)
  suns = [
    emoji.emojize(':sun:'),
    emoji.emojize(':sun_with_face:'),
  ]
  return suns[n]


icons_dict = {
  "clear-day": random_sun_emoji(),
  "clear-night": random_moon_emoji(),
  "rain": emoji.emojize(":cloud_with_rain:"),
  "snow": emoji.emojize(":snowflake:"),
  "sleet": emoji.emojize(":cloud_with_rain:"),
  "wind": emoji.emojize(":dashing_away:"),
  "fog": emoji.emojize(":fog:"),
  "cloudy": emoji.emojize(":cloud:"),
  "partly-cloudy-day": emoji.emojize(":sun_behind_cloud:"),
  "partly-cloudy-night": random_moon_emoji() + emoji.emojize(":cloud:"),
  "cloud_with_lightning_and_rain": emoji.emojize(":cloud_with_lightning_and_rain:"),
  "hail": emoji.emojize(":cloud:") + emoji.emojize(":ice:"),
  "haze": emoji.emojize(":cloud:") + emoji.emojize(":infinity:"),
}

sky_symbols_meteocat_to_emoji_name = {
  1: "clear-day",
  2: "cloudy",
  3: "partly-cloudy-day",
  4: "cloudy",
  5: "rain",
  6: "rain",
  7: "rain",
  8: "cloud_with_lightning_and_rain",
  9: "hail",
  10: "snow",
  11: "fog",
  12: "fog",
  13: "snow",
  20: "cloudy",
  21: "cloudy",
  22: "haze",
  23: "rain",
  24: "cloud_with_lightning_and_rain",
  25: "cloud_with_lightning_and_rain",
  26: "snow",
  27: "snow",
  28: "snow",
  29: "snow",
  30: "snow",
  31: "rain",
  32: "rain",
}


def _headers():
  return {"Content-Type": "application/json", "X-Api-Key": get_meteocat_key()}


def sky_state(daymoment="mati") -> int:
  today_date = datetime.now(ZoneInfo('Europe/Madrid')).strftime('%Y/%m/%d')

  url_pronostic_comarcal = f'https://api.meteo.cat/pronostic/v1/comarcal/{today_date}'
  response = requests.get(url_pronostic_comarcal, headers=_headers())
  response.raise_for_status()
  res_json = response.json()

  return next(item for item in res_json[daymoment]["cel"] if item["idComarca"] == ID_COMARCA)["simbol"]


def prediccio_general_catalunya(variable="estatDelCel") -> str:
  today_date = datetime.now(ZoneInfo('Europe/Madrid')).strftime('%Y/%m/%d')

  url_prediccio_general = f'https://api.meteo.cat/pronostic/v1/catalunya/{today_date}'
  response = requests.get(url_prediccio_general, headers=_headers())
  response.raise_for_status()
  variables = response.json()["variables"]

  return variables.get(variable, variables["estatDelCel"])


# limite real de X es 280, pero los emojis cuentan como 2 caracteres:
# dejamos margen
TWEET_MAX = 275


# check if tweet is longer than TWEET_MAX characters, then split into chunks
def joiner(chunks):
  i = 0
  newchunks = []
  while (i < len(chunks)):
    try:
      if len(chunks[i]) + 2 + len(chunks[i + 1]) <= TWEET_MAX:
        # put periods back
        newchunks.append(chunks[i] + '. ' + chunks[i + 1])
        i += 1
      else:
        newchunks.append(chunks[i])
      i += 1
    except IndexError:
      newchunks.append(chunks[i])
      i += 1
  if chunks == newchunks:  # if at maximum chunking
    return chunks
  else:
    return joiner(newchunks)


def split_long(text):
  # una frase suelta mas larga que TWEET_MAX se parte por el ultimo espacio
  # que quepa, marcando la continuacion con puntos suspensivos
  pieces = []
  while len(text) > TWEET_MAX:
    cut = text.rfind(' ', 0, TWEET_MAX - 1)
    if cut <= 0:
      cut = TWEET_MAX - 1
    pieces.append(text[:cut] + '…')
    text = '…' + text[cut:].lstrip()
  pieces.append(text)
  return pieces


DIES_SETMANA = ['dilluns', 'dimarts', 'dimecres', 'dijous', 'divendres', 'dissabte', 'diumenge']

# emoji segun el meteoro del aviso SMP (por palabra clave del nombre)
warning_emojis = [
  ('calor', emoji.emojize(':hot_face:')),
  ('fred', emoji.emojize(':cold_face:')),
  ('neu', emoji.emojize(':snowflake:')),
  ('pluja', emoji.emojize(':cloud_with_rain:')),
  ('tempesta', emoji.emojize(':cloud_with_lightning:')),
  ('llamps', emoji.emojize(':cloud_with_lightning:')),
  ('vent', emoji.emojize(':dashing_away:')),
  ('mar', emoji.emojize(':water_wave:')),
]


def warning_emoji(meteor):
  nombre = meteor.lower()
  for clave, icono in warning_emojis:
    if clave in nombre:
      return icono
  return emoji.emojize(':warning:')


def get_new_comarca_warnings(window_hours=3.25):
  """Avisos SMP en firme (no preavisos) emitidos en las ultimas window_hours
  con afectacion sobre la comarca. La ventana ligeramente mayor que el
  intervalo del scheduler evita perder avisos por el filo del reloj."""
  r = requests.get('https://api.meteo.cat/pronostic/v1/smp/episodis-oberts', headers=_headers())
  r.raise_for_status()

  ahora = datetime.now(timezone.utc)
  resultado = []
  for ep in r.json():
    candidatos = []
    for av in ep.get('avisos', []):
      # al ampliar un episodio Meteocat re-emite el aviso con dataEmisio
      # nueva: si la ampliacion pasa a incluir la comarca, se tuiteara
      if av.get('tipus') != 'Avís':
        continue
      emisio = datetime.strptime(av['dataEmisio'], '%Y-%m-%dT%H:%MZ').replace(tzinfo=timezone.utc)
      if ahora - emisio > timedelta(hours=window_hours):
        continue

      franjas = []
      for evo in av.get('evolucions') or []:
        for per in evo.get('periodes') or []:
          for a in per.get('afectacions') or []:
            if a.get('idComarca') == ID_COMARCA:
              franjas.append((evo['dia'][:10], per['nom'], a.get('perill', 1), a.get('llindar') or ''))
      if franjas:
        candidatos.append((emisio, franjas))

    if candidatos:
      _, franjas = max(candidatos)  # la emision mas reciente del episodio
      resultado.append({'meteor': ep['meteor']['nom'], 'franjas': franjas})
  return resultado


def build_warning_tweet(aviso):
  franjas = aviso['franjas']
  max_perill = max(f[2] for f in franjas)
  llindar = next((f[3] for f in franjas if f[3]), '')

  detalles = []
  for dia in sorted({f[0] for f in franjas}):
    nom_dia = DIES_SETMANA[datetime.strptime(dia, '%Y-%m-%d').weekday()]
    hores = ' i '.join(f"de {p.replace('-', ' a ')} h" for f in franjas if f[0] == dia for p in [f[1]])
    detalles.append(f'{nom_dia} {hores}')

  texto = warning_emoji(aviso['meteor']) + f" Meteocat activa un avís per {aviso['meteor'].lower()} al Moianès"
  if llindar:
    texto += f' ({llindar.lower()})'
  texto += ': ' + '; '.join(detalles) + f'. Grau de perill: {max_perill}/6.'
  return texto


def build_forecast_tweets():
  # hora local de Catalunya: en GCF el reloj va en UTC
  now_hour = datetime.now(ZoneInfo('Europe/Madrid')).hour
  if 6 < now_hour < 12:
    daymoment, salutacio = "mati", "Bon dia!"
  else:
    daymoment, salutacio = "tarda", "Bona tarda!"

  simbol = sky_state(daymoment=daymoment)
  icona = icons_dict[sky_symbols_meteocat_to_emoji_name.get(simbol, "partly-cloudy-day")]

  tweet_large_text = salutacio + " " + icona + " " + prediccio_general_catalunya("estatDelCel")

  # split only after periods followed by whitespace
  chunks = re.split(r'\.\s', tweet_large_text)

  tweets = []
  for tweet in joiner(chunks):
    tweets.extend(split_long(tweet) if len(tweet) > TWEET_MAX else [tweet])
  return tweets