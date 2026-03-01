# FlowForm Vitality Master Suite — Hardened Boot MVP

## Boot entrypoints (authoritative)

- `00_setup_all.bat`
  - Creates `.venv` if missing
  - Upgrades pip tooling
  - Installs `requirements.txt`
  - Resolves runtime port and writes `ACTIVE_PORTS.json`
- `01_run_all.bat`
  - Resolves runtime port with `boot_port.py`
  - Starts the Flask server with **venv python only**
  - Waits for the port to become reachable
  - Opens browser to `/ready`

## Port resolution

Implemented in `boot_port.py`:
1. Prefer port from `PORTS.json` key `FlowForm-app` (or `apps.FlowForm-app`) when present.
2. If preferred port is busy or missing, choose first free port in `5400–5499`.
3. Write selected port to `ACTIVE_PORTS.json`.

## API/Ready endpoints

- `GET /api/health` → JSON:
  - `status`
  - `port`
  - `db_ok`
  - `version`
- `GET /ready` → dark-themed readiness page that fetches `/api/health`.

## Local run (Windows)

1. Run `00_setup_all.bat`
2. Run `01_run_all.bat`

## Local run (any OS for development)

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python run_server.py --port 5410
```

Then open: `http://127.0.0.1:5410/ready`

## Environment config

Copy `.env.example` to `.env` and adjust as needed.

```env
HOST=127.0.0.1
PORT=5410
DB_PATH=./data/flowform.db
```

Note: explicit `--port` on `run_server.py` takes precedence over `.env` `PORT`.

## Smoke test

```bash
pytest tests_smoke.py
```


Additional runtime smoke:

```bash
pytest smoke_test.py
```
