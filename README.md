# FlowForm Vitality Master Suite

Standalone Flask app for session management MVP with SQLite persistence.

## Run (Windows)

1. `00_setup_all.bat`
2. Optional: set `PORT` in `.env` (default `5400`)
3. `01_run_all.bat`

## Implemented routes

- `GET /dashboard`
- `GET /sessions`
- `GET /sessions/new`
- `POST /sessions/create`
- `GET /sessions/<id>`
- `POST /sessions/<id>/complete`
- `GET /api/health`

## SQLite tables

- `users(id, name, created_at)`
- `sessions(id, title, category, intensity, duration_minutes, notes, created_at, completed_at)`
- `metrics(id, session_id, heart_rate_avg, calories, perceived_exertion)`
