import requests
from config import get_telegram_cfg

# Canal de Telegram: API gratuita, sin limites practicos. El bot debe ser
# administrador del canal con permiso de publicar.

API = 'https://api.telegram.org/bot{token}/{method}'


def _call(cfg, method, **params):
  r = requests.post(API.format(token=cfg['bot_token'], method=method), timeout=30, **params)
  r.raise_for_status()
  body = r.json()
  if not body.get('ok'):
    raise RuntimeError(f'Telegram {method}: {body}')
  return body['result']


def send_text(text, chat_id=None):
  # chat_id por defecto: el canal publico; se puede apuntar a otro chat
  # (p.ej. el privado del administrador para las alertas)
  cfg = get_telegram_cfg()
  return _call(cfg, 'sendMessage', data={'chat_id': chat_id or cfg['chat_id'], 'text': text,
                                         'disable_web_page_preview': True})


def send_photo(png_bytes, caption):
  cfg = get_telegram_cfg()
  return _call(cfg, 'sendPhoto', data={'chat_id': cfg['chat_id'], 'caption': caption},
               files={'photo': ('radar.png', png_bytes, 'image/png')})
