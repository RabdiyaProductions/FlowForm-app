# FlowForm App

Minimal Flask service for health/readiness checks used by FlowForm tooling.

## Python version

- **Python 3.11** (recommended and tested)

## Setup (virtualenv)

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install flask pytest
```

## `.env` template

Create a `.env` file in the project root:

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
- Set `OPENAI_API_KEY=` (empty) to intentionally disable AI features.
- `DATABASE_PATH` defaults to `instance/flowform.db` if not provided.

## DB initialization behavior

On app startup, the service automatically:

1. Creates the DB parent directory if needed.
2. Creates the SQLite database file if it does not exist.
3. Creates `app_metadata` table if missing.
4. Inserts a one-time `initialized=true` marker row.

No separate migration/init command is required for local smoke testing.

## Run the app

```bash
flask --app app run --host ${HOST:-127.0.0.1} --port ${PORT:-5000}
```

Default URLs:

- App root: `http://127.0.0.1:5000/`
- Health: `http://127.0.0.1:5000/api/health`
- Ready: `http://127.0.0.1:5000/ready`

## CI-ready test commands

```bash
pytest -q
```

Optional stricter CI command:

```bash
pytest -q --maxfail=1 --disable-warnings
```
