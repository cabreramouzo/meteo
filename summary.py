from datetime import date, datetime
from zoneinfo import ZoneInfo
import requests
import emoji
import netatmo
from meteocat import _headers

# Yearly (or year-to-date) weather summary for Castellcir.
# Rain: our own Netatmo rain gauge (hyperlocal).
# Temperature: our Netatmo outdoor module when it has data for enough days
# of the year; otherwise (it was dead through 2025-26) the nearest Meteocat
# XEMA station, Muntanyola (CY, 12 km away, 816 m).

XEMA = 'https://api.meteo.cat/xema/v1'
XEMA_STATION = 'CY'
XEMA_STATION_NAME = 'Muntanyola'
MIN_COVERAGE = 0.9        # fraction of days with data to trust the Netatmo
RAINY_DAY_MM = 1.0

MONTHS_CA = ['gener', 'febrer', 'març', 'abril', 'maig', 'juny', 'juliol', 'agost',
             'setembre', 'octubre', 'novembre', 'desembre']


def date_ca(d):
  month = MONTHS_CA[d.month - 1]
  of = "d'" if month[0] in 'aeiou' else 'de '
  day = f"l'{d.day}" if d.day in (1, 11) else f'el {d.day}'
  return f'{day} {of}{month}'


def decimal_ca(v, decimals=1):
  return f'{v:.{decimals}f}'.replace('.', ',')


def _year_range(year):
  tz = ZoneInfo('Europe/Madrid')
  start = datetime(year, 1, 1, tzinfo=tz)
  end = min(datetime(year + 1, 1, 1, tzinfo=tz), datetime.now(tz))
  return start, end


# ---------- Netatmo ----------

def netatmo_daily(year, module_type, types):
  """{date: [values...]} at daily scale for the given module."""
  token = netatmo._access_token()
  device_id, modules = netatmo._station(token)
  start, end = _year_range(year)
  r = netatmo.request_with_retry('GET', 'https://api.netatmo.com/api/getmeasure',
                                 headers={'Authorization': f'Bearer {token}'},
                                 params={'device_id': device_id, 'module_id': modules[module_type],
                                         'scale': '1day', 'type': types, 'optimize': 'false',
                                         'date_begin': int(start.timestamp()), 'date_end': int(end.timestamp()) - 1})
  body = r.json().get('body') or {}
  if not isinstance(body, dict):   # empty list when the module never reported
    return {}
  return {date.fromtimestamp(int(t)): v for t, v in body.items()}


def netatmo_rain(year):
  days = netatmo_daily(year, 'NAModule3', 'sum_rain')
  return {d: v[0] + netatmo.rain_adjustment(d) for d, v in days.items() if v[0] is not None}


def netatmo_temps(year):
  days = netatmo_daily(year, 'NAModule1', 'min_temp,max_temp,temperature')
  return {d: {'tn': v[0], 'tx': v[1], 'tm': v[2]} for d, v in days.items() if None not in v[:3]}


# ---------- XEMA (Meteocat) ----------

def xema_daily(variable, year, month):
  r = requests.get(f'{XEMA}/variables/estadistics/diaris/{variable}', headers=_headers(),
                   params={'codiEstacio': XEMA_STATION, 'any': year, 'mes': f'{month:02d}'}, timeout=30)
  if r.status_code == 400:   # month without data yet
    return {}
  r.raise_for_status()
  out = {}
  for v in r.json().get('valors', []):
    if v.get('percentatge', 100) >= 80 and v.get('valor') is not None:
      out[date.fromisoformat(v['data'][:10])] = v['valor']
  return out


def xema_temps(year):
  start, end = _year_range(year)
  last_month = end.month if end.year == year else 12
  tn, tx, tm = {}, {}, {}
  for month in range(1, last_month + 1):
    tn.update(xema_daily(1002, year, month))   # daily minimum
    tx.update(xema_daily(1001, year, month))   # daily maximum
    tm.update(xema_daily(1000, year, month))   # daily mean
  return {d: {'tn': tn[d], 'tx': tx[d], 'tm': tm[d]} for d in tn if d in tx and d in tm}


# ---------- summary ----------

def year_summary(year):
  start, end = _year_range(year)
  days_in_range = (end.date() - start.date()).days

  rain = netatmo_rain(year)
  temps = netatmo_temps(year)
  temps_source = None
  if len(temps) < MIN_COVERAGE * days_in_range:
    temps = xema_temps(year)
    temps_source = f'estació de {XEMA_STATION_NAME} (Meteocat)'

  s = {'year': year, 'complete': end.year > year, 'until': end.date(), 'temps_source': temps_source}
  if rain:
    by_month = {}
    for d, v in rain.items():
      by_month[d.month] = by_month.get(d.month, 0) + v
    wettest_day = max(rain, key=rain.get)
    wettest_month = max(by_month, key=by_month.get)
    s['rain'] = {'total': sum(rain.values()), 'wettest_day': (wettest_day, rain[wettest_day]),
                 'rainy_days': sum(1 for v in rain.values() if v >= RAINY_DAY_MM),
                 'wettest_month': (wettest_month, by_month[wettest_month]), 'days': len(rain)}
  if temps:
    hottest = max(temps, key=lambda d: temps[d]['tx'])
    coldest = min(temps, key=lambda d: temps[d]['tn'])
    s['temps'] = {'tx': (hottest, temps[hottest]['tx']), 'tn': (coldest, temps[coldest]['tn']),
                  'mean': sum(v['tm'] for v in temps.values()) / len(temps),
                  'frost_days': sum(1 for v in temps.values() if v['tn'] < 0),
                  'hot_days': sum(1 for v in temps.values() if v['tx'] >= 30),
                  'days': len(temps)}
  return s


def build_summary_parts(s):
  """List of texts: one tweet each on X, a single message on Telegram."""
  title = f"{emoji.emojize(':bar_chart:')} Resum meteorològic de Castellcir {s['year']}"
  if not s['complete']:
    title += f" (fins {date_ca(s['until'])})"
  parts = []

  if 'rain' in s:
    r = s['rain']
    parts.append(
      f"{title}\n\n{emoji.emojize(':cloud_with_rain:')} Pluja: {decimal_ca(r['total'])} l/m²\n"
      f"Dia més plujós: {date_ca(r['wettest_day'][0])}, {decimal_ca(r['wettest_day'][1])} l/m²\n"
      f"Mes més plujós: {MONTHS_CA[r['wettest_month'][0] - 1]} ({decimal_ca(r['wettest_month'][1], 0)} l/m²)\n"
      f"Dies de pluja (≥1 l/m²): {r['rainy_days']}")
  else:
    parts.append(title)

  if 'temps' in s:
    t = s['temps']
    source = f" · {s['temps_source']}" if s['temps_source'] else ''
    mean_label = 'Mitjana anual' if s['complete'] else 'Mitjana'
    parts.append(
      f"{emoji.emojize(':thermometer:')} Temperatures {s['year']}{source}\n"
      f"Màxima: {decimal_ca(t['tx'][1])} °C {date_ca(t['tx'][0])}\n"
      f"Mínima: {decimal_ca(t['tn'][1])} °C {date_ca(t['tn'][0])}\n"
      f"{mean_label}: {decimal_ca(t['mean'])} °C\n"
      f"Dies de glaçada: {t['frost_days']} · Dies de 30 °C o més: {t['hot_days']}")
  return parts
