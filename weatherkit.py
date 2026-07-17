import time
import jwt
import requests
from config import get_weatherkit_cfg

WEATHERKIT_URL = "https://weatherkit.apple.com/api/v1/weather"


def make_token(cfg):
  # WeatherKit exige un JWT ES256 con la cabecera extra "id" = "<team_id>.<service_id>"
  now = int(time.time())
  payload = {
    'iss': cfg['team_id'],
    'iat': now,
    'exp': now + 600,
    'sub': cfg['service_id'],
  }
  headers = {
    'kid': cfg['key_id'],
    'id': f"{cfg['team_id']}.{cfg['service_id']}",
  }
  return jwt.encode(payload, cfg['private_key'], algorithm='ES256', headers=headers)


def get_weather(lat, lon, data_sets, lang='ca', timezone='Europe/Madrid'):
  cfg = get_weatherkit_cfg()
  url = f'{WEATHERKIT_URL}/{lang}/{lat}/{lon}'
  params = {'dataSets': data_sets, 'timezone': timezone}
  headers = {'Authorization': f'Bearer {make_token(cfg)}'}

  respuesta = requests.get(url, params=params, headers=headers)
  respuesta.raise_for_status()
  return respuesta.json()
