import io
from time import sleep

import telegram
from config import get_telegram_cfg
from twitter import get_client, get_api_v1

# Un unico punto de publicacion: cada aviso sale por X y por el canal de
# Telegram. Telegram es opcional (sin credenciales se omite) y cada canal
# se intenta aunque el otro falle; al final se relanza el primer error para
# que la alerta de Monitoring se entere.


def _telegram_enabled():
  try:
    return bool(get_telegram_cfg())
  except (ImportError, AttributeError):
    return False


def publish(parts, image=None):
  """parts: lista de textos (un hilo en X, un unico mensaje en Telegram).
  image: PIL.Image opcional que acompana al primer texto."""
  if isinstance(parts, str):
    parts = [parts]
  png = None
  if image is not None:
    buf = io.BytesIO()
    image.save(buf, format='PNG')
    png = buf.getvalue()

  errors = []

  try:
    client = get_client()
    media_ids = None
    if png:
      media_ids = [get_api_v1().media_upload(filename='radar.png', file=io.BytesIO(png)).media_id]
    tweet = client.create_tweet(text=parts[0], media_ids=media_ids)
    for text in parts[1:]:
      sleep(5)  # delay for API call
      tweet = client.create_tweet(text=text, in_reply_to_tweet_id=tweet.data['id'])
  except Exception as e:  # noqa: BLE001 - queremos seguir con Telegram
    errors.append(e)

  if _telegram_enabled():
    try:
      text = '\n\n'.join(parts)
      if png:
        telegram.send_photo(png, text[:1024])  # limite de caption de Telegram
      else:
        telegram.send_text(text)
    except Exception as e:  # noqa: BLE001
      errors.append(e)

  if errors:
    raise errors[0]
