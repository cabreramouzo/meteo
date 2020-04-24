from my_keys import get_cfg
from my_keys import get_dark_key
import tweepy
import requests
import json
import emoji
import random
import logging

lang = "ca"
exclude = "currently,minutely,hourly,alerts,flags"
units = "si"
url = 'https://api.darksky.net/forecast/' + get_dark_key() + '/41.770358,2.154847?lang=' + lang + '&exclude=' + exclude + '&units=' + units

respuesta = requests.get(url)
#print(respuesta.url)
respuesta.raise_for_status() # optional but good practice in case the call fails!

def lunar_phase_emoji(lunation_number):

  #if lunation_number == 0:
  if lunation_number >= 0.98 or lunation_number < 0.02:
    moon_emoji = emoji.emojize(':new_moon_face:')
    fase_cat = "lluna nova."
  elif lunation_number >= 0.03 and lunation_number<0.20:
    moon_emoji = emoji.emojize(':waxing_crescent_moon:')
    fase_cat = "lluna creixent,."
  elif lunation_number >= 0.20  and lunation_number < 0.30:
    moon_emoji = emoji.emojize(':first_quarter_moon:')
    fase_cat = "quart creixent."
  elif lunation_number >= 0.30 and lunation_number<0.4:
    moon_emoji = emoji.emojize(':waxing_gibbous_moon:')
    fase_cat = "lluna gibosa creixent."
  elif lunation_number >= 0.45 and lunation_number < 0.55:
    moon_emoji = emoji.emojize(':full_moon:')
    fase_cat = "lluna plena."
  elif lunation_number >= 0.6 and lunation_number<0.7:
    moon_emoji = emoji.emojize(':waning_gibbous_moon:')
    fase_cat = "lluna gibosa minvant."
  elif lunation_number >= 0.75 and lunation_number < 0.80:
    moon_emoji = emoji.emojize(':last_quarter_moon:') 
    fase_cat = "quart minvant."
  elif lunation_number >=  0.80 and lunation_number < 0.90:
    moon_emoji = emoji.emojize(':waning_crescent_moon:')
    fase_cat = "lluna minvant."
  return (moon_emoji, fase_cat)


#print (respuesta.json())
datos = respuesta.json()
#accedo a sumary:
#print datos['hourly']['summary']

lunation_number = datos['daily']['data'][0]['moonPhase']
print(f'l_n={lunation_number}')
moon_emoji,fase_cat = lunar_phase_emoji(lunation_number)

print (moon_emoji)


fase_lunar = f"Bona nit. Fase lunar d'avui: {moon_emoji} {fase_cat}. Nombre llunàtic:{lunation_number}" 

def get_api(cfg):
  auth = tweepy.OAuthHandler(cfg['consumer_key'], cfg['consumer_secret'])
  auth.set_access_token(cfg['access_token'], cfg['access_token_secret'])
  return tweepy.API(auth)


def main():
  # Fill in the values noted in previous step here
  cfg = get_cfg()

  api = get_api(cfg)
  tweet = fase_lunar
  status = api.update_status(status=tweet)
  # Yes, tweet is called 'status' rather confusing

if __name__ == "__main__":
  main()


#return respuesta.json()
