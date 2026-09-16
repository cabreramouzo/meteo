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


def get_meteocat_key():
  # API key de Meteocat (apidocs.meteocat.gencat.cat)
  return '...'


def get_netatmo_cfg():
  # App de Netatmo (dev.netatmo.com > My apps). El refresh token inicial se
  # genera con el "Token generator" de la app (scope read_station) y se
  # guarda en ~/.netatmo_refresh_token (en local) o en el secreto
  # netatmo-refresh-token (en GCF) — ojo: rota en cada uso.
  return {
    'client_id': '...',
    'client_secret': '...',
  }


def get_telegram_cfg():
  # Canal de Telegram (opcional). 1) Habla con @BotFather > /newbot y copia
  # el token. 2) Crea un canal publico y anade el bot como administrador con
  # permiso de publicar. 3) chat_id = '@nombre_del_canal'.
  return {
    'bot_token': '123456789:AAAA...',
    'chat_id': '@meteoCastellcir',
  }
