# Entry points para Google Cloud Functions (gen2, trigger HTTP via Cloud
# Scheduler). Las credenciales llegan por variables de entorno: ver README.

import os
from datetime import datetime
from zoneinfo import ZoneInfo

import functions_framework

import emoji

import meteocat
import netatmo
import radar
import summary
import telegram
import tweet_current_meteo
import tweet_moon_phase
from publish import publish
from weatherkit import get_weather

lat = 41.770358
lon = 2.154847


def _dry(request):
  # con ?dry=1 se construye el tweet pero no se publica (para probar deploys)
  return request.args.get('dry')


@functions_framework.http
def tweet_forecast(request):
  # prediccion general de Catalunya (Meteocat), en hilo si no cabe en un tweet
  list_tweets = meteocat.build_forecast_tweets()
  if _dry(request):
    return {"dry": True, "tweets": list_tweets}

  publish(list_tweets)
  return "OK"


@functions_framework.http
def tweet_current(request):
  # tiempo actual del pueblo (WeatherKit)
  datos = get_weather(lat, lon, "currentWeather")
  tweet = tweet_current_meteo.build_tweet(datos)
  if _dry(request):
    return {"dry": True, "tweets": [tweet]}

  publish(tweet)
  return "OK"


@functions_framework.http
def tweet_moon(request):
  # fase lunar de hoy (WeatherKit)
  datos = get_weather(lat, lon, "forecastDaily")
  tweet = tweet_moon_phase.build_tweet(datos)
  principal = tweet_moon_phase.is_principal_phase(datos)
  if _dry(request):
    return {"dry": True, "principal": principal, "tweets": [tweet]}
  if not principal:
    return "minor phase, skipped"

  publish(tweet)
  return "OK"


@functions_framework.http
def tweet_warnings(request):
  # avisos SMP de Meteocat en firme que afecten a la comarca, emitidos desde
  # la ultima comprobacion (cada 3 h): cada aviso se tuitea una sola vez
  textos = [meteocat.build_warning_tweet(av) for av in meteocat.get_new_comarca_warnings()]
  if _dry(request):
    return {"dry": True, "tweets": textos}
  if not textos:
    return "no new warnings"

  for texto in textos:
    publish(meteocat.split_long(texto))
  return "tweeted"


def _coma(valor):
  return f'{valor:.1f}'.replace('.', ',')


@functions_framework.http
def check_freeze(request):
  # tuitea solo en el cruce de 0 °C: la lectura anterior era >= 0 y la
  # actual < 0 (asi no se repite el aviso toda la noche)
  temps = netatmo.get_last_temperatures(2)
  if _dry(request):
    return {"dry": True, "temps": temps}
  if len(temps) < 2:
    return "not enough data"

  anterior, actual = temps
  if anterior >= 0 and actual < 0:
    tweet = emoji.emojize(':snowflake:') + f" Glaçada a Castellcir! Ara mateix {_coma(actual)} °C."
    publish(tweet)
    return "tweeted"
  return "no crossing"


@functions_framework.http
def check_rain_radar(request):
  # alarma de lluvia: solo cuando una masa grande (>= AREA_MINIMA_KM2, un
  # frente y no un chubasco suelto) esta en el radio de alarma Y su
  # trayectoria prevista pasa por el pueblo. La histeresis evita repetir
  # con el mismo frente pero re-arma si la tormenta se afluixa y se reanima
  host, past, nowcast = radar.get_frames()
  masas_ara = radar.big_masses(host, past[-1])
  masas_abans = radar.big_masses(host, past[max(0, len(past) - 4)])
  ara = radar.nearest_mass_km(masas_ara)
  abans = radar.nearest_mass_km(masas_abans)

  if nowcast:
    # el nowcast de RainViewer ya modela el movimiento: impacto solo si
    # preve pluja MODERADA sobre el poble (no el fleco)
    impacte = radar.echo_area_within_km2(host, nowcast[-1], radar.RADI_IMPACTE_KM) >= radar.AREA_IMPACTE_MODERADA_KM2
  else:
    impacte = radar.impact_predicted(masas_abans, masas_ara)

  # re-armado por histeresis sobre la intensidad de eco de los frames
  # anteriores: solo disparamos si hubo una calma desde la ultima tormenta
  previos = past[max(0, len(past) - 1 - radar.REFRACTARI_FRAMES):-1]
  intens_previs = [radar.echo_area_within_km2(host, f) for f in previos]
  armat = radar.armed_after_lull(intens_previs)

  arribada = ara is not None and ara <= radar.RADI_ALARMA_KM
  alarma = arribada and impacte and armat
  propera = min(masas_ara, key=lambda m: m['dist_km'], default=None)
  resultat = {"ara_km": ara, "fa30min_km": abans, "masses": len(masas_ara),
              "area_max": max((m['area_km2'] for m in masas_ara), default=0),
              "area_moderada": propera['area_moderada_km2'] if propera else 0,
              "eco_disc": round(radar.echo_area_within_km2(host, past[-1]), 1),
              "nowcast": bool(nowcast), "impacte": impacte,
              "armat": armat, "alarma": alarma}
  print(resultat)  # queda en Cloud Logging para calibrar umbrales

  if _dry(request) or request.args.get('shadow'):
    return {"dry": True, **resultat}
  if not alarma:
    return "no alarm"

  img = radar.build_radar_image(host, past[-1])
  tweet = (emoji.emojize(':cloud_with_rain:')
           + f" Pluja apropant-se a Castellcir! El radar detecta un front de precipitació a uns {round(ara)} km."
           + " Possible pluja en breu.")
  publish(tweet, image=img)
  return "tweeted"


@functions_framework.http
def tweet_rain(request):
  # lluvia acumulada de ayer; solo tuitea si llovio algo medible
  litros = netatmo.get_yesterday_rain()
  if _dry(request):
    return {"dry": True, "rain": litros}
  if litros < 0.1:
    return "no rain"

  tweet = emoji.emojize(':cloud_with_rain:') + f" Ahir es van recollir {_coma(litros)} l/m² a Castellcir."
  publish(tweet)
  return "tweeted"


@functions_framework.http
def tweet_year_summary(request):
  # yearly summary (runs on Dec 31); ?year=YYYY builds it for another year
  year = int(request.args.get('year') or datetime.now(ZoneInfo('Europe/Madrid')).year)
  parts = summary.build_summary_parts(summary.year_summary(year))
  if _dry(request):
    return {"dry": True, "tweets": parts}

  publish(parts)
  return "OK"


@functions_framework.http
def alert_telegram(request):
  # webhook de Cloud Monitoring: reenvia la alerta al Telegram privado del
  # administrador. Es publica (Monitoring no puede autenticarse con IAM),
  # asi que va protegida por un token en la URL
  if request.args.get('token') != os.environ.get('ALERT_WEBHOOK_TOKEN'):
    return ('forbidden', 403)

  inc = (request.get_json(silent=True) or {}).get('incident', {})
  estat = inc.get('state', '?')
  icona = emoji.emojize(':police_car_light:') if estat == 'open' else emoji.emojize(':check_mark_button:')
  quan = datetime.now(ZoneInfo('Europe/Madrid')).strftime('%d/%m %H:%M')
  text = (f"{icona} Bot meteo — alerta {estat.upper()} ({quan})\n"
          f"{inc.get('policy_name', '')}\n"
          f"{inc.get('summary', '')}\n\n"
          f"{inc.get('documentation', {}).get('content', '')}\n"
          f"{inc.get('url', '')}")
  telegram.send_text(text, chat_id=os.environ['TELEGRAM_ALERT_CHAT_ID'])
  return "OK"
