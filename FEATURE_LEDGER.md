# FEATURE_LEDGER

## Founder-critical flows (implemented)

### 1) Create plan flow
#### UI: `GET /plan/wizard`
Fields:
- goal (`strength`, `fat_loss`, `mobility`, `stress`, `hybrid`)
- days/week (`2`–`6`)
- minutes/session (`30`–`75`)
- discipline preference rank 1–5
- injury flags, equipment, constraints

#### API: `POST /api/plan/create`
Behavior:
- validates/clamps inputs
- computes discipline ordering + progressive 4-week structure
- persists `profile`, `plan`, `plan_day`

#### UI: `GET /plan/current`
Behavior:
- calendar-style week/day list
- Today marker
- completion badge when a `session_completion` exists
- CTA **Start today’s session**
- CTA **Regenerate next week** (preserves completed sessions)

Exact click steps:
1. Open `/plan/wizard`.
2. Fill wizard fields and click **Create 4-week plan**.
3. App redirects to `/plan/current` and shows persisted plan.

---

### 2) Do session flow
#### UI: `GET /session/start/<plan_day_id>`
Behavior:
- ordered blocks loaded from `session_template.json_blocks`
- controls: **Start / Pause / Next / Back / Finish**
- timer per block (countdown)

#### Finish API: `POST /api/session/finish`
Payload:
- `plan_day_id`
- `rpe` (1–10)
- `notes`
- `minutes_done`

Persistence:
- inserts `session_completion`
- writes `audit_log` event
- returns redirect to `/session/summary/<completion_id>`

#### UI: `GET /session/summary/<completion_id>`
Behavior:
- shows completion fields (RPE, notes, minutes, timestamp)
- link back to `/plan/current`

Exact click steps:
1. Open `/plan/current`.
2. Click **Start today’s session**.
3. In player, use Start/Pause/Next/Back as needed.
4. Click **Finish**, enter RPE + notes + minutes.
5. Click **Save completion**.
6. Land on `/session/summary/<completion_id>`.
7. Return to `/plan/current` and confirm row shows **Completed**.

---

## Supporting endpoints still present
- `/health`, `/api/health`
- `/diagnostics` (HTML), `/api/diagnostics` (JSON)
- `/api/spec`
- timeline/critic/import/export stubs


---

### 3) Daily recovery loop
#### UI: `GET /recovery`
Behavior:
- daily check-in form (sleep/stress/soreness/mood/notes)
- list of last 14 days
- explicit safety disclaimer: not medical advice

#### API: `POST /api/recovery/checkin`
Behavior:
- upserts check-in for the day
- computes explainable readiness score from sleep/stress/soreness/mood
- persists readiness explanation in notes and emits readiness score in API response

#### Integration in `GET /plan/current`
Behavior:
- readiness badge shown from latest check-in
- if readiness is low, show non-destructive lighter-template suggestion for today
- plan is never auto-overwritten by readiness suggestion

Exact click steps:
1. Open `/recovery`.
2. Submit daily check-in.
3. Open `/plan/current`.
4. Verify readiness badge and low-readiness suggestion (when applicable).
