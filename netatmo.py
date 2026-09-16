import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import requests
from config import get_netatmo_cfg, load_netatmo_refresh_token, save_netatmo_refresh_token

# Modulo aislado a proposito: cuando la estacion Netatmo se sustituya por otra,
# basta con reescribir este fichero manteniendo get_last_temperatures() y
# get_yesterday_rain().

API = 'https://api.netatmo.com'

# Manual rain corrections (mm) for days with known data loss. The outdoor
# modules do not buffer while the base station is off, so a power cut loses
# whatever falls. Estimates come from Meteocat's Muntanyola station scaled
# by that day's Castellcir/Muntanyola ratio.
RAIN_ADJUSTMENTS_MM = {
  date(2026, 9, 16): 5.0,   # power cut 22:33-00:27 during a downpour (Muntanyola 1.2-5 mm x1.45)
}


def rain_adjustment(day):
  return RAIN_ADJUSTMENTS_MM.get(day, 0.0)


def request_with_retry(method, url, tries=3, **kwargs):
  # Netatmo's API returns sporadic 503s; retry with a short backoff
  for attempt in range(tries):
    r = requests.request(method, url, timeout=30, **kwargs)
    if r.status_code < 500 or attempt == tries - 1:
      r.raise_for_status()
      return r
    time.sleep(2 * (attempt + 1))


def _access_token():
  cfg = get_netatmo_cfg()
  refresh = load_netatmo_refresh_token()
  r = request_with_retry('POST', f'{API}/oauth2/token', data={
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
  r = request_with_retry('GET', f'{API}/api/getstationsdata', headers={'Authorization': f'Bearer {token}'})
  device = r.json()['body']['devices'][0]
  modules = {m['type']: m['_id'] for m in device['modules']}
  return device['_id'], modules


def _getmeasure(token, device_id, module_id, **params):
  r = request_with_retry('GET', f'{API}/api/getmeasure', headers={'Authorization': f'Bearer {token}'},
                         params={'device_id': device_id, 'module_id': module_id,
                                 'optimize': 'false', **params})
  body = r.json()['body']
  # segun el caso llega como {timestamp: [valor]} o como lista (vacia si el
  # modulo no ha reportado, p.ej. sin bateria) de {beg_time, value: [[v]]}
  if isinstance(body, dict):
    return [v[0] for _, v in sorted(body.items(), key=lambda kv: int(kv[0]))]
  valores = []
  for tramo in body:
    valores.extend(v[0] for v in tramo.get('value', []))
  return valores


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
  return (valores[0] if valores else 0.0) + rain_adjustment(ayer.date())
