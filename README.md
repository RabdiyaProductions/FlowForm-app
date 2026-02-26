# FlowForm Vitality Master Suite

Clean standalone Flask MVP with dashboard, sessions library, session player, progress log, settings, and readiness/health routes.

## Run in 3 steps (Windows)

1. `00_setup_all.bat`
2. Ensure `.env` has your preferred `PORT` (optional, default is `5400`).
3. `01_run_all.bat`

The app opens at `http://127.0.0.1:<PORT>/`.

## Required endpoint

- `GET /api/health` → `{ "status", "port", "db_ok", "version" }`

## .env example

```env
HOST=127.0.0.1
PORT=5400
DB_PATH=./data/flowform.db
LOG_LEVEL=INFO
```
