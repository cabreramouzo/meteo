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


def get_netatmo_cfg():
  cfg = _from_env({
    'client_id': 'NETATMO_CLIENT_ID',
    'client_secret': 'NETATMO_CLIENT_SECRET',
  })
  if cfg:
    return cfg
  from my_keys import get_netatmo_cfg as local_cfg
  return local_cfg()


# El refresh token de Netatmo rota en cada uso, asi que no puede ir en una
# variable de entorno fija: en GCF vive como secreto que se reescribe, y en
# local como fichero.

NETATMO_TOKEN_SECRET = 'netatmo-refresh-token'
NETATMO_TOKEN_FILE = os.path.expanduser('~/.netatmo_refresh_token')


def _on_gcp():
  return bool(os.environ.get('K_SERVICE'))


def load_netatmo_refresh_token():
  if _on_gcp():
    from google.cloud import secretmanager
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{os.environ['GCP_PROJECT']}/secrets/{NETATMO_TOKEN_SECRET}/versions/latest"
    return client.access_secret_version(name=name).payload.data.decode().strip()
  with open(NETATMO_TOKEN_FILE) as f:
    return f.read().strip()


def save_netatmo_refresh_token(token):
  if _on_gcp():
    from google.cloud import secretmanager
    client = secretmanager.SecretManagerServiceClient()
    parent = f"projects/{os.environ['GCP_PROJECT']}/secrets/{NETATMO_TOKEN_SECRET}"
    nueva = client.add_secret_version(parent=parent, payload={'data': token.encode()})
    # el token rota cada pocos minutos en invierno y Secret Manager cobra
    # por version activa: destruimos las viejas al guardar la nueva
    for v in client.list_secret_versions(request={'parent': parent}):
      if v.name != nueva.name and v.state.name != 'DESTROYED':
        client.destroy_secret_version(name=v.name)
  else:
    with open(NETATMO_TOKEN_FILE, 'w') as f:
      f.write(token)
    os.chmod(NETATMO_TOKEN_FILE, 0o600)
