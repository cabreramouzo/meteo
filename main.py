# Entry points para Google Cloud Functions (gen2, trigger HTTP via Cloud
# Scheduler). Las credenciales llegan por variables de entorno: ver README.

from time import sleep

import functions_framework

import meteocat
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
