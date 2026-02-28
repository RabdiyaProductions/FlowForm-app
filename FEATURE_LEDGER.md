# FEATURE_LEDGER

## Scope and evidence
This ledger is populated from files present in this repository snapshot.

Evidence used:
- `app_server.py` (implemented Flask routes)
- `tools/run_full_tests.py` (regression workflow)
- `_BAT/1_setup.bat`, `_BAT/2_run.bat`, `_BAT/3_open_browser.bat`, `_BAT/6_run_tests.bat` (boot/run/test flow)
- `README.md`, `BASELINE.md` (operational documentation)

Requested source files not found in this repo snapshot:
- `app.py` (missing; implementation lives in `app_server.py`)
- `QUICKSTART.md` (missing)
- `COMPLETION_MATRIX.md` (missing)

Status key:
- ✅ implemented and testable in current code
- 🟨 partial/stubbed
- ⬜ not implemented in current code

## Route/feature ledger

| Feature | UI entry point (page/button) | Endpoint(s) | Data store | Outputs / artifacts | Acceptance check (what I do, what must happen) | Status |
|---|---|---|---|---|---|---|
| API spec | API client / diagnostics tooling | `GET /api/spec` | In-memory route manifest built from Flask `app.url_map` | JSON with app/version/routes | Call `/api/spec`; must return 200 and include all implemented core routes | ✅ |
| Diagnostics | Browser/API client to `/diagnostics` | `GET /diagnostics` | In-memory checks + first-run DB check state | JSON status/checks/missing routes | Call `/diagnostics`; must return `status=PASS` with no missing routes | ✅ |
| App state (requested) | N/A in current UI | `/api/state` | N/A | N/A | Endpoint is requested but not present in app routes | ⬜ |
| Orders (requested) | N/A in current UI | `/api/orders` | N/A | N/A | Endpoint is requested but not present in app routes | ⬜ |
| Generate flow (requested) | N/A in current UI | `/api/generate/*` | N/A | N/A | Endpoint family is requested but not present in app routes | ⬜ |
| Timeline APIs | No dedicated button in current ready UI | `POST /api/timeline/update`, `POST /api/timeline/regenerate`, `POST /api/timeline/apply_global` | No persisted write behavior currently | JSON ack payloads | POST each endpoint; must return 200 JSON ack | 🟨 |
| Critic run | No dedicated button in current ready UI | `POST /api/critic/run` | No persisted write behavior currently | JSON ack payload | POST endpoint; must return 200 JSON ack | 🟨 |
| Approve | No dedicated button in current ready UI | `POST /api/approve` | No persisted write behavior currently | JSON ack payload | POST endpoint; must return 200 JSON ack | 🟨 |
| Export | No dedicated button in current ready UI | `POST /api/export`, `/exports` (requested route missing) | File artifact creation not yet implemented | Currently JSON ack only (no ZIP emitted yet) | POST `/api/export`; currently returns ack, but ZIP acceptance is not yet met | 🟨 |
| Import | No dedicated button in current ready UI | `POST /api/import`, `/imports` (requested route missing) | File import persistence not yet implemented | Currently JSON ack only | POST `/api/import`; currently returns ack, route `/imports` is not implemented | 🟨 |
| Project lookup helper | No dedicated button in current ready UI | `GET /api/projects/<code>` | No project DB query yet | JSON echo payload with code | GET endpoint with code; must return 200 and echo `code` | 🟨 |
| Health + readiness | Browser to `/ready` | `GET /health`, `GET /api/health`, `GET /ready`, `GET /` | SQLite (`data/flowform.db`) with first-run integrity check | JSON health payload + ready/error pages | Open `/health`; must include `status/version/time/db_ok/provider_status` | ✅ |

## Core workflows (from available docs/code)
1. **Boot path**: `_BAT/1_setup.bat` → `_BAT/2_run.bat` → validate `/diagnostics`.
2. **Regression gate**: `_BAT/6_run_tests.bat` or `python tools/run_full_tests.py`.
3. **Automated test sequence** (from `tools/run_full_tests.py`):
   - `python -m pytest tests_smoke.py`
   - `python -m pytest smoke_test.py`
   - pass only if both commands exit 0.
