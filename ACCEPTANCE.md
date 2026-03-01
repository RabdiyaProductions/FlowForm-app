# ACCEPTANCE

## Journey 1 — Setup and boot
**Steps**
1. Run `_BAT/1_setup.bat`.
2. Run `_BAT/2_run.bat`.
3. Open `/ready`.

**Accept if**
- app boots and responds on resolved port
- `/ready` and `/api/health` return 200

## Journey 2 — Create founder plan
**Steps**
1. Open `/plan/wizard`.
2. Choose goal.
3. Set days/week (2–6).
4. Set minutes/session (30–75).
5. Rank disciplines 1–5.
6. Add injury/equipment constraints.
7. Click **Create 4-week plan**.

**Accept if**
- redirect to `/plan/current`
- refresh `/plan/current` and plan remains visible

## Journey 3 — Start and run a session
**Steps**
1. On `/plan/current`, click **Start today’s session**.
2. On `/session/start/<plan_day_id>`, verify block list and timer.
3. Use **Start / Pause / Next / Back**.

**Accept if**
- blocks render in order
- timer updates for timed blocks

## Journey 4 — Finish and capture completion
**Steps**
1. Click **Finish** in session player.
2. Enter RPE (1–10), notes, minutes_done.
3. Click **Save completion**.

**Accept if**
- `session_completion` row is written
- redirect to `/session/summary/<completion_id>`
- summary shows captured values

## Journey 5 — Completion reflected in current plan
**Steps**
1. Open `/plan/current` after finishing.
2. Find the session row just completed.

**Accept if**
- row displays **Completed**
- app still exposes `/diagnostics` and `/api/diagnostics`


## Journey 6 — Recovery check-in drives daily suggestion
**Steps**
1. Open `/recovery`.
2. Fill sleep/stress/soreness/mood and submit check-in.
3. Confirm latest check-in appears in last-14-days list.
4. Open `/plan/current`.

**Accept if**
- check-in persists and is visible in `/recovery` history
- readiness badge appears on `/plan/current`
- when readiness is low, a lighter-template suggestion appears without auto-overwriting the plan
- safety disclaimer is visible on `/recovery` (not medical advice)
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
