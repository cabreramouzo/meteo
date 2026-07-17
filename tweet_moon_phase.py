from my_keys import get_cfg
from weatherkit import get_weather
import tweepy
import emoji

lat = 41.770358
lon = 2.154847
lang = "ca"

# WeatherKit devuelve la fase lunar como enum, ya no hace falta el numero
# de lunacion ni sus rangos: moonPhase -> (emoji, fase en catalan)
phases_dict = {
  "new": (emoji.emojize(':new_moon_face:'), "lluna nova"),
  "waxingCrescent": (emoji.emojize(':waxing_crescent_moon:'), "lluna creixent"),
  "firstQuarter": (emoji.emojize(':first_quarter_moon:'), "quart creixent"),
  "waxingGibbous": (emoji.emojize(':waxing_gibbous_moon:'), "lluna gibosa creixent"),
  "full": (emoji.emojize(':full_moon:'), "lluna plena"),
  "waningGibbous": (emoji.emojize(':waning_gibbous_moon:'), "lluna gibosa minvant"),
  "thirdQuarter": (emoji.emojize(':last_quarter_moon:'), "quart minvant"),
  "lastQuarter": (emoji.emojize(':last_quarter_moon:'), "quart minvant"),
  "waningCrescent": (emoji.emojize(':waning_crescent_moon:'), "lluna minvant"),
}


def build_tweet(datos):
  fase = datos['forecastDaily']['days'][0]['moonPhase']
  print(f'moonPhase={fase}')

  moon_emoji, fase_cat = phases_dict[fase]
  print(moon_emoji)

  return f"Bona nit. Fase lunar d'avui: {moon_emoji} {fase_cat}."


def get_client(cfg):
  return tweepy.Client(
    consumer_key=cfg['consumer_key'],
    consumer_secret=cfg['consumer_secret'],
    access_token=cfg['access_token'],
    access_token_secret=cfg['access_token_secret'],
  )


def main():
  datos = get_weather(lat, lon, "forecastDaily", lang=lang)
  tweet = build_tweet(datos)

  client = get_client(get_cfg())
  client.create_tweet(text=tweet)


if __name__ == "__main__":
  main()
