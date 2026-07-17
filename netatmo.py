import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests
from config import get_netatmo_cfg, load_netatmo_refresh_token, save_netatmo_refresh_token

# Modulo aislado a proposito: cuando la estacion Netatmo se sustituya por otra,
# basta con reescribir este fichero manteniendo get_last_temperatures() y
# get_yesterday_rain().

API = 'https://api.netatmo.com'


def _access_token():
  cfg = get_netatmo_cfg()
  refresh = load_netatmo_refresh_token()
  r = requests.post(f'{API}/oauth2/token', data={
    'grant_type': 'refresh_token',
    'refresh_token': refresh,
    'client_id': cfg['client_id'],
    'client_secret': cfg['client_secret'],
  })
  r.raise_for_status()
  data = r.json()
  # Netatmo rota el refresh token en cada renovacion: si no guardamos el
  # nuevo, la sesion muere y hay que volver a autorizar a mano
  if data.get('refresh_token') and data['refresh_token'] != refresh:
    save_netatmo_refresh_token(data['refresh_token'])
  return data['access_token']


def _station(token):
  r = requests.get(f'{API}/api/getstationsdata', headers={'Authorization': f'Bearer {token}'})
  r.raise_for_status()
  device = r.json()['body']['devices'][0]
  modules = {m['type']: m['_id'] for m in device['modules']}
  return device['_id'], modules


def _getmeasure(token, device_id, module_id, **params):
  r = requests.get(f'{API}/api/getmeasure', headers={'Authorization': f'Bearer {token}'},
                   params={'device_id': device_id, 'module_id': module_id,
                           'optimize': 'false', **params})
  r.raise_for_status()
  body = r.json()['body']  # {timestamp: [valor]}
  return [v[0] for _, v in sorted(body.items(), key=lambda kv: int(kv[0]))]


def get_last_temperatures(n=2):
  """Ultimas n medias de temperatura (escala 30 min) del modulo exterior."""
  token = _access_token()
  device_id, modules = _station(token)
  valores = _getmeasure(token, device_id, modules['NAModule1'],  # modulo exterior
                        scale='30min', type='temperature',
                        date_begin=int(time.time()) - (n + 1) * 1800)
  return valores[-n:]


def get_yesterday_rain():
  """Acumulado de lluvia de ayer (l/m2) del pluviometro."""
  token = _access_token()
  device_id, modules = _station(token)
  tz = ZoneInfo('Europe/Madrid')
  hoy = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
  ayer = hoy - timedelta(days=1)
  valores = _getmeasure(token, device_id, modules['NAModule3'],  # pluviometro
                        scale='1day', type='sum_rain',
                        date_begin=int(ayer.timestamp()),
                        date_end=int(hoy.timestamp()) - 1)
  return valores[0] if valores else 0.0
