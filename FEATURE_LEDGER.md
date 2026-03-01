# FEATURE_LEDGER

## Repository reality map (CCE-flat baseline)

### 1) Entrypoints that exist now
- **Primary app module (minimal health app):** `app.py`
  - Flask factory: `create_app(test_config=None)`
  - Process entrypoint: `python app.py` (`__main__`)
- **Primary server module (full route surface):** `app_server.py`
  - Flask factory: `create_app(port=None)`
  - Process entrypoint: `python app_server.py` (`main`)
- **Thin launcher entrypoint:** `run_server.py` delegates to `app_server.main()`
- **Port/bootstrap utility entrypoint:** `boot_port.py` (`main`) resolves/waits/writes active port files

### 2) Routes that exist now

#### In `app.py`
- `GET /api/health`
- `GET /ready`

#### In `app_server.py`
- `GET /`
- `GET /health`
- `GET /api/health`
- `GET /version`
- `POST /api/timeline/update`
- `POST /api/timeline/regenerate`
- `POST /api/timeline/apply_global`
- `POST /api/critic/run`
- `POST /api/approve`
- `POST /api/export`
- `POST /api/import`
- `GET /api/projects/<code>`
- `POST /api/agents/enhance`
- `GET /api/spec`
- `GET /diagnostics`
- `GET /ready`

### 3) Templates/static assets in repo
- **Flask templates directory:**
  - `templates/base.html`
  - `templates/dashboard.html`
  - `templates/first_run_error.html`
  - `templates/player.html`
  - `templates/progress.html`
  - `templates/ready.html`
  - `templates/session_detail.html`
  - `templates/session_new.html`
  - `templates/sessions.html`
  - `templates/settings.html`
- **Top-level static/site pages:**
  - `index.html`, `app.html`, `about.html`, `contact.html`, `faq.html`, `dashboard.html`, `plans.html`, `subscriptions.html`, `terms.html`, `privacy.html`, `success.html`, `cancel.html`, `classes.html`, `launch-checklist.html`, `sales-chat.html`, `sitemap.html`, `redirect.html`, `404.html`
- **Top-level static assets:**
  - `styles.css`, `script.js`

### 4) DB usage and schema (current)
- **`app.py` DB behavior**
  - Uses SQLite path from `DATABASE_PATH` (default `instance/flowform.db`) and creates table `app_metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL)`.
  - Seeds row: `('initialized', 'true')`.
- **`app_server.py` DB behavior**
  - Uses SQLite path from `DB_PATH` (default `data/flowform.db`).
  - Creates `_healthcheck(id INTEGER PRIMARY KEY, checked_at TEXT NOT NULL)` and appends timestamp rows for startup health checks.

### 5) Boot scripts and test runners
- Root boot stack:
  - `00_setup_all.bat` (venv + deps + active port write)
  - `01_run_all.bat` (resolve port, launch server, wait, open browser)
- `_BAT` compatibility stack:
  - `_BAT/1_setup.bat` → calls `00_setup_all.bat`
  - `_BAT/2_run.bat` → launches `run_server.py`
  - `_BAT/3_open_browser.bat` → opens diagnostics URL
  - `_BAT/6_run_tests.bat` → structure check + full tests
- Python test orchestrator:
  - `tools/run_full_tests.py` (runs structure guard + smoke suites)

## Route purpose ledger (implemented surface)

| Route | Purpose | Status |
|---|---|---|
| `GET /` | Ready landing page (or first-run error template) | Implemented |
| `GET /ready` | Readiness page render | Implemented |
| `GET /health` | Operational health JSON with db/provider signals | Implemented |
| `GET /api/health` | API health JSON for automation | Implemented |
| `GET /version` | Build metadata/version response | Implemented |
| `GET /api/spec` | Route manifest/spec output | Implemented |
| `GET /diagnostics` | Spec coverage + route checks | Implemented |
| `POST /api/timeline/update` | Timeline update stub ack | Stub/ack |
| `POST /api/timeline/regenerate` | Timeline regenerate stub ack | Stub/ack |
| `POST /api/timeline/apply_global` | Global timeline apply stub ack | Stub/ack |
| `POST /api/critic/run` | Critic pass stub ack | Stub/ack |
| `POST /api/approve` | Approval stub ack | Stub/ack |
| `POST /api/export` | Export stub ack | Stub/ack |
| `POST /api/import` | Import stub ack | Stub/ack |
| `GET /api/projects/<code>` | Project lookup stub echo | Stub/ack |
| `POST /api/agents/enhance` | Agent enhance stub ack | Stub/ack |

