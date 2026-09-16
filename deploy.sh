#!/usr/bin/env bash
# Despliega las funciones gen2 (todas, o las que se pasen como argumentos).
#   ./deploy.sh                 # todas
#   ./deploy.sh tweet-current   # solo una
set -euo pipefail
export CLOUDSDK_PYTHON="${CLOUDSDK_PYTHON:-/opt/homebrew/bin/python3.12}"
PROJECT=tweet-current-darksky-wheather
REGION=europe-west1
cd "$(dirname "$0")"

TW="TW_CONSUMER_KEY=tw-consumer-key:latest,TW_CONSUMER_SECRET=tw-consumer-secret:latest,TW_ACCESS_TOKEN=tw-access-token:latest,TW_ACCESS_TOKEN_SECRET=tw-access-token-secret:latest"
WK="WK_TEAM_ID=wk-team-id:latest,WK_SERVICE_ID=wk-service-id:latest,WK_KEY_ID=wk-key-id:latest,WK_PRIVATE_KEY=wk-private-key:latest"
MC="METEOCAT_API_KEY=meteocat-api-key:latest"
NA="NETATMO_CLIENT_ID=netatmo-client-id:latest,NETATMO_CLIENT_SECRET=netatmo-client-secret:latest"
# Telegram es opcional: solo se inyecta si los secretos existen
if gcloud secrets describe telegram-bot-token --project=$PROJECT >/dev/null 2>&1; then
  TW="$TW,TELEGRAM_BOT_TOKEN=telegram-bot-token:latest,TELEGRAM_CHAT_ID=telegram-chat-id:latest"
fi

ALL="tweet-forecast tweet-current tweet-moon tweet-warnings check-freeze tweet-rain check-rain-radar alert-telegram tweet-year-summary"
for fn in ${@:-$ALL}; do
  mem=256Mi; env=""; auth="--no-allow-unauthenticated"
  case $fn in
    tweet-forecast)   entry=tweet_forecast;   secrets="$TW,$MC" ;;
    tweet-current)    entry=tweet_current;    secrets="$TW,$WK" ;;
    tweet-moon)       entry=tweet_moon;       secrets="$TW,$WK" ;;
    tweet-warnings)   entry=tweet_warnings;   secrets="$TW,$MC" ;;
    check-freeze)     entry=check_freeze;     secrets="$TW,$NA"; env="GCP_PROJECT=$PROJECT" ;;
    tweet-rain)       entry=tweet_rain;       secrets="$TW,$NA"; env="GCP_PROJECT=$PROJECT" ;;
    check-rain-radar) entry=check_rain_radar; secrets="$TW";     mem=512Mi ;;
    tweet-year-summary) entry=tweet_year_summary; secrets="$TW,$MC,$NA"; env="GCP_PROJECT=$PROJECT" ;;
    alert-telegram)   entry=alert_telegram;   secrets="$TW,ALERT_WEBHOOK_TOKEN=alert-webhook-token:latest"
                      env="TELEGRAM_ALERT_CHAT_ID=5277157"; auth="--allow-unauthenticated" ;;
    *) echo "funcion desconocida: $fn"; exit 1 ;;
  esac
  echo "=== $fn"
  gcloud functions deploy "$fn" --project=$PROJECT --gen2 --runtime=python312 --region=$REGION \
    --source=. --entry-point="$entry" --trigger-http $auth \
    --memory="$mem" --timeout=120s --set-secrets="$secrets" ${env:+--set-env-vars="$env"} -q 2>&1 \
    | grep -E "^state:|ERROR" || true
done
