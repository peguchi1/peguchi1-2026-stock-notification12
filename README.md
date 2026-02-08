# Stock Notificator (Daily Batch)

Daily batch alerting for US equities. Uses NFCI + index SMA200 for market regime, then filters to uptrend names and stages pullback/breakout notifications.

## Features
- Market regime filter (NFCI + SPY/QQQ SMA200)
- Stock eligibility filter (trend + extension + drawdown)
- Multi-stage triggers: pullback A/B and breakout S
- Slack / Pushover / stdout output
- GitHub Actions daily scheduler

## File Tree
```
.
|-- .github/
|   `-- workflows/
|       `-- daily.yml
|-- src/
|   |-- __init__.py
|   |-- cache.py
|   |-- config.py
|   |-- data_provider.py
|   |-- filters.py
|   |-- indicators.py
|   |-- main.py
|   |-- market_regime.py
|   |-- nfci.py
|   |-- notifications.py
|   `-- triggers.py
|-- tests/
|   `-- test_triggers.py
|-- .env.example
|-- config.yaml
|-- requirements.txt
`-- README.md
```

## Requirements
- Python 3.11+
- Twelve Data API key (primary) and/or Alpha Vantage API key (fallback)

## Setup (Local)
```
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set credentials (or export env vars directly). `.env` is loaded automatically on startup:
```
TWELVE_DATA_API_KEY=...
ALPHA_VANTAGE_API_KEY=...
SLACK_WEBHOOK_URL=...
PUSHOVER_USER_KEY=...
PUSHOVER_APP_TOKEN=...
MAIL_ADDRESS_NOTIFICATION_TO=...
SMTP_HOST=...
SMTP_PORT=587
SMTP_USER=...
SMTP_PASSWORD=...
SMTP_FROM=...
SMTP_TLS=true
GOOGLE_SHEET_URL=...
GOOGLE_SERVICE_ACCOUNT_FILE=...
```

Run:
```
python -m src.main --config config.yaml
```

## Configuration
All thresholds and switches live in `config.yaml`.

- `filters.tolerance` (default 0.005)
- `filters.drawdown_20d_max` (default 0.15)
- `filters.high_52w_max_multiple` (default 1.05)
- `triggers.pullback_25.enabled`
- `triggers.pullback_50.enabled`
- `triggers.breakout_20d.enabled`
- `triggers.breakout_volume_mult` (default 1.2)
- `notifications.slack_enabled` / `notifications.pushover_enabled`
- `notifications.email_enabled`
- `data.rate_limit.enabled` / `data.rate_limit.min_interval_seconds` (default 8.0)
Google Sheets logging (optional):
- `GOOGLE_SHEET_URL`
- `GOOGLE_SERVICE_ACCOUNT_FILE` (service account JSON path)

## Market Regime Logic
Regime is scored daily using NFCI (weekly forward-filled) and QQQ trend:
- NFCI level and short-term changes (1w/4w) build a 0-100 score
- QQQ MA50/MA200 defines PriceScore (0/5/15/30)
- Score maps to state and max_exposure, with risk-off trigger tightening exposure

Notification behavior:
- allow_new_entries = True: signals are considered
- allow_new_entries = False: summary only

## NFCI
`nfci.csv_url` points to Chicago Fed NFCI data. Latest row is used, and the NFCI date is included in notifications.

## GitHub Actions
`.github/workflows/daily.yml` runs the batch daily via cron.
- cron is `0 22 * * *` (UTC), which is 07:00 JST.
- GitHub Actions schedules can be delayed; this is expected behavior per GitHub.

Add secrets in GitHub repo settings:
- TWELVE_DATA_API_KEY
- ALPHA_VANTAGE_API_KEY
- SLACK_WEBHOOK_URL
- PUSHOVER_USER_KEY
- PUSHOVER_APP_TOKEN

## Notifications
If Slack/Pushover credentials are not set, the system prints formatted output to stdout.
Email is sent when SMTP settings and `MAIL_ADDRESS_NOTIFICATION_TO` are set.

## Google Sheets Logging
When `GOOGLE_SHEET_URL` and `GOOGLE_SERVICE_ACCOUNT_FILE` are set, each run appends a row
including RegimeScore and any hit tickers with latest closes.

## Troubleshooting
- If you see `TWELVE_DATA_API_KEY not set`, set env var or add GitHub secret.
- API rate limits can happen; the fetcher retries with exponential backoff.
- If NFCI fetch fails, check the CSV URL in `config.yaml`.

## Tests
```
pytest
```
