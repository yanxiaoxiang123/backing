#!/usr/bin/env bash
set -euo pipefail
umask 077
cd /home/yanxx/backing
exec 9>/home/yanxx/backing/ops/sync.lock
flock -n 9 || exit 0
codes=$(docker compose --env-file deployment.env -f source/deploy/production/compose.yaml \
  exec -T backend python -c '
from app.config import SessionLocal, settings
from app.models.models import Stock, WatchlistItem
with SessionLocal() as db:
    requested = set(settings.watchlist_stocks) | {row[0] for row in db.query(WatchlistItem.stock_code)}
    # Dashboard configuration can contain indices; this job updates stock history.
    selected = sorted(row[0] for row in db.query(Stock.code).filter(Stock.code.in_(requested)))
    print("\n".join(selected))
')
if [ -z "$codes" ]; then
  echo 'No stock watchlist configured; nothing to synchronize.'
  exit 0
fi
mapfile -t selected_codes <<< "$codes"
exec docker compose --env-file deployment.env -f source/deploy/production/compose.yaml \
  exec -T backend python data_sync_cli.py --codes "${selected_codes[@]}" --metadata --days 730 \
  --report-file /app/backend/data/daily-sync-report.json
