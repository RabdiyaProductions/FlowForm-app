# FlowForm App

This repo provides a minimal Flask service with health/readiness endpoints and smoke tests.

## Python version

Use **Python 3.10**.

## Setup (virtualenv)

```bash
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install Flask pytest
```

## `.env` template values

Create `.env` in the repository root:

```env
FLASK_APP=app.py
FLASK_ENV=development
HOST=127.0.0.1
PORT=5000
DATABASE_PATH=instance/flowform.db
OPENAI_API_KEY=your_openai_api_key_here
LOG_LEVEL=INFO
```

Notes:
- Leave `OPENAI_API_KEY` empty (`OPENAI_API_KEY=`) to disable AI features gracefully.
- If `DATABASE_PATH` is not set, `instance/flowform.db` is used.

## DB initialization behavior

On startup (`create_app()`), the app automatically:
1. Creates the database directory if missing.
2. Creates the SQLite DB file if missing.
3. Creates table `app_metadata` if missing.
4. Inserts `initialized=true` once using `INSERT OR IGNORE`.

No separate migration/init command is required for local smoke tests.

## Run command and default URLs

Run the service:

```bash
flask --app app:create_app run --host 127.0.0.1 --port 5000
```

Default URLs:
- Home: `http://127.0.0.1:5000/`
- Health: `http://127.0.0.1:5000/api/health`
- Ready: `http://127.0.0.1:5000/ready`

## CI-ready test command

```bash
pytest -q
```

Optional stricter CI command:

```bash
pytest -q --maxfail=1 --disable-warnings
```
