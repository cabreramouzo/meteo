# meteo

Bot de Twitter/X ([@meteoCastellcir](https://twitter.com/meteoCastellcir)) que publica el tiempo de Castellcir y la predicción de Catalunya.

Tres funciones, pensadas para Google Cloud Functions (gen2) + Cloud Scheduler:

| Entry point | Qué tuitea | Fuente |
|---|---|---|
| `tweet_forecast` | Predicción general de Catalunya (en hilo si no cabe) | Meteocat |
| `tweet_current` | Tiempo actual del pueblo (temp, humedad, presión) | Apple WeatherKit |
| `tweet_moon` | Fase lunar, solo en las 4 fases principales (nova, quarts, plena) | Apple WeatherKit |
| `check_freeze` | Aviso al cruzar 0 °C (solo en el cruce, no repite) | Netatmo |
| `tweet_rain` | Lluvia acumulada de ayer, solo si llovió (≥0,1 l/m²) | Netatmo |
| `tweet_warnings` | Avisos SMP en firme que afecten al Moianès (cada aviso una sola vez) | Meteocat |
| `tweet_year_summary` | Resumen del año el 31 de diciembre (lluvia total, día/mes más lluvioso, máx/mín con fecha, media, días de helada y de calor). `?year=YYYY` para otro año | Netatmo + XEMA Muntanyola (temperatura, mientras el módulo exterior no tenga datos del año) |

Todas aceptan `?dry=1`: construyen la respuesta pero no publican.

## Credenciales

Por variables de entorno (en local, si faltan, se usa `my_keys.py`, que está en el
`.gitignore` — copia `my_keys_example.py` y rellénalo):

| Variable | Contenido |
|---|---|
| `TW_CONSUMER_KEY` / `TW_CONSUMER_SECRET` | API key/secret de la app de X (permisos Read and Write) |
| `TW_ACCESS_TOKEN` / `TW_ACCESS_TOKEN_SECRET` | Access token/secret de la app de X |
| `WK_TEAM_ID` | Team ID de Apple Developer |
| `WK_SERVICE_ID` | Identifier (App ID/Service ID) con WeatherKit activado |
| `WK_KEY_ID` | ID de la clave WeatherKit (los 10 caracteres del AuthKey_XXX.p8) |
| `WK_PRIVATE_KEY` | Contenido PEM completo del fichero `.p8` |
| `METEOCAT_API_KEY` | API key de Meteocat |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | (opcional) bot de @BotFather y `@canal`: todo se publica también en Telegram |
| `NETATMO_CLIENT_ID` / `NETATMO_CLIENT_SECRET` | App de Netatmo (dev.netatmo.com) |
| `GCP_PROJECT` | ID del proyecto (para que la función reescriba el secreto del token) |

El refresh token de Netatmo **rota en cada uso**, así que no va en variable de
entorno: vive en el secreto `netatmo-refresh-token` (en GCF, la propia función
guarda el token nuevo como versión nueva del secreto — el service account
necesita `roles/secretmanager.secretVersionAdder` sobre ese secreto) o en
`~/.netatmo_refresh_token` (en local). El token inicial se saca del "Token
generator" de la app de Netatmo con scope `read_station`.

## Probar en local

```bash
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
./venv/bin/python tweet_current_meteo.py   # ojo: publica un tweet de verdad
```

## Desplegar en Google Cloud Functions

Sube primero los secretos a Secret Manager (una vez):

```bash
echo -n "$TW_CONSUMER_KEY" | gcloud secrets create tw-consumer-key --data-file=-
# ... igual para el resto; el .p8 entero:
gcloud secrets create wk-private-key --data-file=AuthKey_XXXXXXXXXX.p8
```

Despliega con `./deploy.sh` (todas) o `./deploy.sh tweet-current` (una). A mano, cada función es:

```bash
for fn in tweet_forecast tweet_current tweet_moon; do
  gcloud functions deploy "${fn//_/-}" \
    --gen2 --runtime=python312 --region=europe-west1 \
    --source=. --entry-point="$fn" \
    --trigger-http --no-allow-unauthenticated \
    --set-secrets="TW_CONSUMER_KEY=tw-consumer-key:latest,TW_CONSUMER_SECRET=tw-consumer-secret:latest,TW_ACCESS_TOKEN=tw-access-token:latest,TW_ACCESS_TOKEN_SECRET=tw-access-token-secret:latest,WK_TEAM_ID=wk-team-id:latest,WK_SERVICE_ID=wk-service-id:latest,WK_KEY_ID=wk-key-id:latest,WK_PRIVATE_KEY=wk-private-key:latest,METEOCAT_API_KEY=meteocat-api-key:latest"
done
```

Y programa los disparos (horas en `Europe/Madrid`, ajusta a gusto):

```bash
gcloud scheduler jobs create http tweet-forecast-mati \
  --schedule="0 9 * * *" --time-zone="Europe/Madrid" \
  --uri="$(gcloud functions describe tweet-forecast --gen2 --region=europe-west1 --format='value(url)')" \
  --oidc-service-account-email="TU_SA@TU_PROYECTO.iam.gserviceaccount.com"
```

(repite para `tweet-forecast` de tarde, `tweet-current` y `tweet-moon` con sus horarios)

## Coste en X

X cobra por uso: **$0,015 por tweet sin enlace** ($0,20 si lleva URL — no poner
enlaces nunca). Con la programación actual (predicción 9:00, tiempo actual 8:00
y 21:30, luna en fases principales, lluvia/avisos/radar cuando toque) salen
~150 tweets/mes ≈ $2,25. Si se agotan los créditos la API devuelve
`402 Payment Required` y todo deja de publicarse: recargar en console.x.com.

Hay una alerta de Cloud Monitoring ("meteo bot: error en una funcion") que
avisa cuando cualquier función falla, por email y por Telegram privado
(webhook → función `alert_telegram`, protegida con el token
`alert-webhook-token`; el chat de destino va en `TELEGRAM_ALERT_CHAT_ID`).
