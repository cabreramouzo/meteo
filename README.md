# meteo

Bot de Twitter/X ([@meteoCastellcir](https://twitter.com/meteoCastellcir)) que publica el tiempo de Castellcir y la predicción de Catalunya.

Tres funciones, pensadas para Google Cloud Functions (gen2) + Cloud Scheduler:

| Entry point | Qué tuitea | Fuente |
|---|---|---|
| `tweet_forecast` | Predicción general de Catalunya (en hilo si no cabe) | Meteocat |
| `tweet_current` | Tiempo actual del pueblo (temp, humedad, presión) | Apple WeatherKit |
| `tweet_moon` | Fase lunar del día | Apple WeatherKit |

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

Despliega cada función (mismo código fuente, distinto entry point):

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
