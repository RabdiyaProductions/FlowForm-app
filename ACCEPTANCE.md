# ACCEPTANCE

This file defines the **top 5 founder journeys** against what is currently implemented.

## Journey 1 — First setup to first ready screen
**Goal:** Fresh machine can install and boot deterministically.

**Click steps**
1. Run `00_setup_all.bat` (or `_BAT/1_setup.bat`).
2. Run `01_run_all.bat` (or `_BAT/2_run.bat`).
3. Open `/ready` in browser.

**Accept if**
- venv and dependencies install successfully.
- server starts on resolved port.
- `/ready` returns HTTP 200 and renders the ready template.

## Journey 2 — Founder creates a 4-week plan from wizard
**Goal:** Build and persist a plan from UI inputs.

**Click steps**
1. Open `/plan/wizard`.
2. Select goal (`strength`, `fat_loss`, `mobility`, `stress`, or `hybrid`).
3. Set days/week (2–6) and minutes/session (30–75).
4. Rank 5 discipline preferences.
5. Add injury flags, equipment, and constraints.
6. Click **Create 4-week plan**.

**Accept if**
- Browser redirects to `/plan/current`.
- New `plan` row is saved with `weeks=4` and `status=active`.
- `plan_day` rows exist for all planned days.

## Journey 3 — Founder reviews plan and today selection
**Goal:** View the saved plan in calendar style and identify today.

**Click steps**
1. Open `/plan/current`.
2. Review Week/Day table cards.
3. Confirm row marked **Today**.

**Accept if**
- Plan survives refresh (`/plan/current` still populated).
- Week/day list is shown in calendar-style table layout.
- Today’s week/day indicator appears.

## Journey 4 — Founder starts session or regenerates next week
**Goal:** Use plan CTAs without losing completion history.

**Click steps**
1. On `/plan/current`, click **Start today's session**.
2. Return and click **Regenerate next week**.

**Accept if**
- Start CTA is available from current plan view.
- Regenerate CTA refreshes only the upcoming week schedule.
- Completed sessions are not deleted during regeneration.

## Journey 5 — Founder checks system health and guard rails
**Goal:** Ensure readiness + structure safety.

**Click steps**
1. Open `/health`, `/api/health`, and `/diagnostics`.
2. Run `_BAT/6_run_tests.bat` (or `python tools/run_full_tests.py`).

**Accept if**
- `/api/health` returns `db_ok=true` and `template_count>0`.
- `/diagnostics` shows `PASS`.
- structure guard and smoke tests pass.
