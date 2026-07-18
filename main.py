# Entry points para Google Cloud Functions (gen2, trigger HTTP via Cloud
# Scheduler). Las credenciales llegan por variables de entorno: ver README.

from time import sleep

import functions_framework

import emoji

import meteocat
import netatmo
import tweet_current_meteo
import tweet_moon_phase
from twitter import get_client
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

  client = get_client()
  tweet = client.create_tweet(text=list_tweets[0])
  for text in list_tweets[1:]:
    sleep(5)  # delay for API call
    tweet = client.create_tweet(text=text, in_reply_to_tweet_id=tweet.data["id"])

  return "OK"


@functions_framework.http
def tweet_current(request):
  # tiempo actual del pueblo (WeatherKit)
  datos = get_weather(lat, lon, "currentWeather")
  tweet = tweet_current_meteo.build_tweet(datos)
  if _dry(request):
    return {"dry": True, "tweets": [tweet]}

  get_client().create_tweet(text=tweet)
  return "OK"


@functions_framework.http
def tweet_moon(request):
  # fase lunar de hoy (WeatherKit)
  datos = get_weather(lat, lon, "forecastDaily")
  tweet = tweet_moon_phase.build_tweet(datos)
  if _dry(request):
    return {"dry": True, "tweets": [tweet]}

  get_client().create_tweet(text=tweet)
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

  client = get_client()
  for texto in textos:
    tweet = None
    for parte in meteocat.split_long(texto):
      if tweet is None:
        tweet = client.create_tweet(text=parte)
      else:
        sleep(5)  # delay for API call
        tweet = client.create_tweet(text=parte, in_reply_to_tweet_id=tweet.data["id"])
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
    get_client().create_tweet(text=tweet)
    return "tweeted"
  return "no crossing"


@functions_framework.http
def tweet_rain(request):
  # lluvia acumulada de ayer; solo tuitea si llovio algo medible
  litros = netatmo.get_yesterday_rain()
  if _dry(request):
    return {"dry": True, "rain": litros}
  if litros < 0.1:
    return "no rain"

  tweet = emoji.emojize(':cloud_with_rain:') + f" Ahir es van recollir {_coma(litros)} l/m² a Castellcir."
  get_client().create_tweet(text=tweet)
  return "tweeted"
