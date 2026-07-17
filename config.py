import os

# Credenciales: en Google Cloud Functions vienen de variables de entorno /
# Secret Manager; en local, si faltan, se cae a my_keys.py (gitignored).


def _from_env(mapping):
  vals = {campo: os.environ.get(var) for campo, var in mapping.items()}
  if all(vals.values()):
    return vals
  return None


def get_twitter_cfg():
  cfg = _from_env({
    'consumer_key': 'TW_CONSUMER_KEY',
    'consumer_secret': 'TW_CONSUMER_SECRET',
    'access_token': 'TW_ACCESS_TOKEN',
    'access_token_secret': 'TW_ACCESS_TOKEN_SECRET',
  })
  if cfg:
    return cfg
  from my_keys import get_cfg
  return get_cfg()


def get_weatherkit_cfg():
  # WK_PRIVATE_KEY lleva el contenido PEM del .p8 directamente
  cfg = _from_env({
    'team_id': 'WK_TEAM_ID',
    'service_id': 'WK_SERVICE_ID',
    'key_id': 'WK_KEY_ID',
    'private_key': 'WK_PRIVATE_KEY',
  })
  if cfg:
    return cfg
  from my_keys import get_weatherkit_cfg as local_cfg
  cfg = local_cfg()
  with open(cfg['key_path']) as f:
    cfg['private_key'] = f.read()
  return cfg


def get_meteocat_key():
  key = os.environ.get('METEOCAT_API_KEY')
  if key:
    return key
  from my_keys import get_meteocat_key as local_key
  return local_key()
