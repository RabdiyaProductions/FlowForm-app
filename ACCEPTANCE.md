# ACCEPTANCE

This file defines the **top 5 founder journeys** against what is currently implemented.

## Journey 1 — First setup to first ready screen
**Goal:** Fresh machine can install and boot deterministically.

**Steps**
1. Run `00_setup_all.bat` (or `_BAT/1_setup.bat`).
2. Run `01_run_all.bat` (or `_BAT/2_run.bat`).
3. Open `/ready`.

**Accept if**
- venv and dependencies install successfully.
- server starts on resolved port.
- `/ready` returns HTTP 200 and renders the ready template.

## Journey 2 — Founder checks operational health
**Goal:** Confirm app health before demos.

**Steps**
1. Visit `/health`.
2. Visit `/api/health`.
3. Visit `/diagnostics`.

**Accept if**
- `/health` includes `status`, `version`, `time`, `db_ok`, `provider_status`.
- `/api/health` returns status + db state.
- `/diagnostics` returns `PASS` and no missing required routes.

## Journey 3 — Founder validates product contract
**Goal:** Verify route surface matches expected CCE-flat API contract.

**Steps**
1. Call `/api/spec`.
2. Review route list and method signatures.

**Accept if**
- Spec endpoint returns HTTP 200.
- Core product routes are present (`timeline`, `critic`, `approve`, `import/export`, `projects`, `agents`).

## Journey 4 — Founder smoke-tests orchestration endpoints
**Goal:** Ensure command endpoints are callable even before full business logic is added.

**Steps**
1. POST each of:
   - `/api/timeline/update`
   - `/api/timeline/regenerate`
   - `/api/timeline/apply_global`
   - `/api/critic/run`
   - `/api/approve`
   - `/api/export`
   - `/api/import`
   - `/api/agents/enhance`
2. GET `/api/projects/<code>` with a sample code.

**Accept if**
- Endpoints return 200 with JSON acknowledgment payloads.
- Project endpoint returns provided `<code>` in response.

## Journey 5 — Founder runs repo guard + smoke suite
**Goal:** Keep repo CCE-flat and prevent structural drift.

**Steps**
1. Run `_BAT/6_run_tests.bat`.
2. (Equivalent) run `python tools/run_full_tests.py`.

**Accept if**
- `tools/check_structure.py` passes.
- smoke tests pass.
- run exits 0.

---

## Current non-goals (still true)
- No committed MP4/render pipeline requirement.
- Timeline/critic/import/export flows are currently stub acknowledgments, not full stateful workflow execution.
