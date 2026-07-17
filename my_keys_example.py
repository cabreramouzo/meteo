# Plantilla de my_keys.py: copia este fichero a my_keys.py y rellena tus
# credenciales. my_keys.py esta en el .gitignore y nunca se sube al repo.


def get_cfg():
  # App de Twitter/X (developer.x.com), con permisos de lectura y escritura
  return {
    'consumer_key': '...',
    'consumer_secret': '...',
    'access_token': '...',
    'access_token_secret': '...',
  }


def get_weatherkit_cfg():
  # WeatherKit (developer.apple.com > Certificates, Identifiers & Profiles):
  # 1. Identifiers > "+" > Services IDs: crea uno (p.ej. com.tudominio.meteo)
  #    y activale la capacidad WeatherKit.
  # 2. Keys > "+": crea una clave con WeatherKit activado y descarga el .p8
  #    (solo se puede descargar una vez). El key_id son los 10 caracteres
  #    del nombre del fichero AuthKey_XXXXXXXXXX.p8.
  # 3. team_id: tu Team ID, visible arriba a la derecha en el portal
  #    (Membership details).
  return {
    'team_id': 'ABCDE12345',
    'service_id': 'com.tudominio.meteo',
    'key_id': 'XXXXXXXXXX',
    'key_path': '/ruta/a/AuthKey_XXXXXXXXXX.p8',
  }
