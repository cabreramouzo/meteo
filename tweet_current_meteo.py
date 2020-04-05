from my_keys import get_cfg
import tweepy
import requests
import json
import emoji
import random

lang = "ca"
exclude = "minutely,hourly,daily,alerts,flags"
units = "si"
url = 'https://api.darksky.net/forecast/01654ad792ff747156ee1423767baa2c/41.770358,2.154847?lang=' + lang + '&exclude=' + exclude + '&units=' + units
#https://api.darksky.net/forecast/01654ad792ff747156ee1423767baa2c/41.770358,2.154847?lang=ca&exclude=currently,minutely,hourly,alerts,flags&units=si
respuesta = requests.get(url)
#print(respuesta.url)
respuesta.raise_for_status() # optional but good practice in case the call fails!

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
}



#print (respuesta.json())
datos = respuesta.json()
#accedo a sumary:
#print datos['hourly']['summary']

sumario_actual = datos['currently']['summary']

#icono-palabra a emoji:
icono_ingles = datos['currently']['icon']
icono = icons_dict[icono_ingles]

#print (icono)

#temperatura i humedad actual:
temp = datos['currently']['temperature']
temp = round(temp,1)
temp = f'{temp}'.replace(".", ",")
hum = datos['currently']['humidity']
hum = int(hum*100)

pres = datos['currently']['pressure']
pres = int(pres)

temp_humedad_pres_actual = f"Actualment {temp} °C i un {hum} %" + " d'humitat." + f" Pressió: {pres} hPa."

def get_api(cfg):
  auth = tweepy.OAuthHandler(cfg['consumer_key'], cfg['consumer_secret'])
  auth.set_access_token(cfg['access_token'], cfg['access_token_secret'])
  return tweepy.API(auth)


def main():
  # Fill in the values noted in previous step here
  cfg = get_cfg()

  api = get_api(cfg)
  tweet = sumario_actual + " " + icono + " " + temp_humedad_pres_actual
  status = api.update_status(status=tweet)
  # Yes, tweet is called 'status' rather confusing

if __name__ == "__main__":
  main()


#return respuesta.json()
