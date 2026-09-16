from weatherkit import get_weather
from publish import publish
import emoji
import random

lat = 41.770358
lon = 2.154847
lang = "ca"


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


# WeatherKit ya no devuelve el resumen en catalan como DarkSky:
# conditionCode -> (frase en catalan, emoji)
summaries_dict = {
  "Clear": ("Cel serè", random_sun_emoji()),
  "MostlyClear": ("Majoritàriament serè", random_sun_emoji()),
  "PartlyCloudy": ("Parcialment ennuvolat", emoji.emojize(":sun_behind_cloud:")),
  "MostlyCloudy": ("Majoritàriament ennuvolat", emoji.emojize(":sun_behind_large_cloud:")),
  "Cloudy": ("Ennuvolat", emoji.emojize(":cloud:")),
  "Foggy": ("Boira", emoji.emojize(":fog:")),
  "Haze": ("Boirina", emoji.emojize(":fog:")),
  "Smoky": ("Fum", emoji.emojize(":fog:")),
  "Breezy": ("Brisa", emoji.emojize(":dashing_away:")),
  "Windy": ("Vent", emoji.emojize(":dashing_away:")),
  "Drizzle": ("Plugim", emoji.emojize(":cloud_with_rain:")),
  "Rain": ("Pluja", emoji.emojize(":cloud_with_rain:")),
  "HeavyRain": ("Pluja forta", emoji.emojize(":cloud_with_rain:")),
  "SunShowers": ("Sol i ruixats", emoji.emojize(":sun_behind_rain_cloud:")),
  "IsolatedThunderstorms": ("Tempestes aïllades", emoji.emojize(":cloud_with_lightning:")),
  "ScatteredThunderstorms": ("Tempestes disperses", emoji.emojize(":cloud_with_lightning:")),
  "Thunderstorms": ("Tempesta", emoji.emojize(":cloud_with_lightning_and_rain:")),
  "StrongStorms": ("Tempestes fortes", emoji.emojize(":cloud_with_lightning_and_rain:")),
  "Flurries": ("Volves de neu", emoji.emojize(":cloud_with_snow:")),
  "SunFlurries": ("Sol i volves de neu", emoji.emojize(":cloud_with_snow:")),
  "Sleet": ("Aiguaneu", emoji.emojize(":cloud_with_rain:")),
  "Snow": ("Neu", emoji.emojize(":snowflake:")),
  "HeavySnow": ("Nevada forta", emoji.emojize(":snowflake:")),
  "Blizzard": ("Torb", emoji.emojize(":snowflake:")),
  "BlowingSnow": ("Neu amb vent", emoji.emojize(":snowflake:")),
  "FreezingDrizzle": ("Plugim gelant", emoji.emojize(":cloud_with_rain:")),
  "FreezingRain": ("Pluja gelant", emoji.emojize(":cloud_with_rain:")),
  "WintryMix": ("Pluja i neu", emoji.emojize(":cloud_with_snow:")),
  "Hail": ("Calamarsa", emoji.emojize(":cloud_with_snow:")),
  "Frigid": ("Fred glacial", emoji.emojize(":snowflake:")),
  "Hot": ("Calor intensa", emoji.emojize(":hot_face:")),
  "BlowingDust": ("Pols en suspensió", emoji.emojize(":dashing_away:")),
  "Hurricane": ("Huracà", emoji.emojize(":cyclone:")),
  "TropicalStorm": ("Tempesta tropical", emoji.emojize(":cyclone:")),
}


def build_tweet(datos):
  actual = datos['currentWeather']

  codi = actual['conditionCode']
  sumario_actual, icono = summaries_dict.get(codi, (codi, emoji.emojize(":thermometer:")))

  # de noche, sol -> luna
  if not actual.get('daylight', True):
    if codi in ("Clear", "MostlyClear"):
      icono = random_moon_emoji()
    elif codi == "PartlyCloudy":
      icono = random_moon_emoji() + emoji.emojize(":cloud:")

  #temperatura i humedad actual:
  temp = actual['temperature']
  temp = round(temp, 1)
  temp = f'{temp}'.replace(".", ",")
  hum = actual['humidity']
  hum = int(hum * 100)

  pres = actual['pressure']
  pres = int(pres)

  temp_humedad_pres_actual = f"Actualment {temp} °C i un {hum} %" + " d'humitat." + f" Pressió: {pres} hPa."

  return sumario_actual + " " + icono + " " + temp_humedad_pres_actual


def main():
  datos = get_weather(lat, lon, "currentWeather", lang=lang)
  tweet = build_tweet(datos)

  publish(tweet)


if __name__ == "__main__":
  main()
