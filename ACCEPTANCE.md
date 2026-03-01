# ACCEPTANCE (True Ready Definition)

This acceptance definition reflects the **current repository state**.

## 1) Boot determinism
Required flow:
1. Run `_BAT/1_setup.bat`
2. Run `_BAT/2_run.bat`
3. Open `/diagnostics`

Pass criteria:
- App starts deterministically on configured/default port.
- Startup must remain non-blocking (no startup blocking first-run gate).
- `/diagnostics` returns `PASS`.

## 2) Regression gate
Required flow:
- Run `python tools/run_full_tests.py` (or `_BAT/6_run_tests.bat`).

Pass criteria:
- Runner exits with code `0`.
- Both smoke suites pass.

## 3) Critical path (product readiness target)
Target path:
1. Create project
2. Generate pilot
3. Critic run
4. Approve
5. Export

Pass criteria:
- Each step completes with valid state transitions and artifacts.

Current snapshot note:
- Timeline/critic/approve/import/export endpoints are present as lightweight ack-style APIs; full end-to-end stateful pipeline is not fully implemented yet.

## 4) Export quality
Required for true ready:
- Export ZIP is produced.
- ZIP includes `manifest.json` and required payload files.

Current snapshot note:
- `/api/export` currently returns JSON ack; ZIP/manifest artifact quality gate is not yet implemented.

## 5) Error handling and gating
Required for true ready:
- Missing required fields return clear actionable messages.
- Approval gating is enforced.

Current snapshot note:
- Robust field-level validation/gating for the full pipeline is not fully implemented.

## 6) Explicit non-goal
- Final MP4 rendering is **NOT required yet**.
- Current expected engine output is specs/packs and workflow orchestration readiness.
