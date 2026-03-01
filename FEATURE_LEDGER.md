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

### 4) One-click full backup + restore
#### Backup API: `GET /api/export/backup`
Behavior:
- returns ZIP containing:
  - `flowform.db` (SQLite database),
  - `flowform_backup.json` (full JSON snapshot),
  - `settings.json` (runtime settings snapshot),
  - `manifest.json` (counts summary + warning),
  - `media/*` files from `instance/media/`.

#### Restore UI: `GET /restore`
Behavior:
- file selector for backup ZIP,
- **Preview restore summary** calls restore endpoint in preview mode,
- explicit confirmation prompt before overwrite.

#### Restore API: `POST /api/import/backup`
Behavior:
- accepts backup ZIP upload,
- returns summary (`plans/templates/completions/recovery/media_files`) and overwrite warning,
- requires confirmation (`confirm_overwrite=true`) before applying restore,
- restore is staged and applied all-or-nothing; failures return error without partial apply.

Exact click steps:
1. Open `/exports`.
2. Click **Download full backup**.
3. Open `/restore`, select ZIP, click **Preview restore summary**.
4. Click **Confirm and restore** and accept confirmation prompt.

---

### 5) Richer exports (PDF)
#### Plan PDF: `GET /api/export/plan_pdf/<plan_id>`
Behavior:
- returns readable PDF with 4-week schedule details (week/day/title/discipline/minutes).

#### Session summary PDF: `GET /api/export/session_summary/<completion_id>`
Behavior:
- returns readable PDF for completed session (blocks, RPE, notes, minutes, completion timestamp).

#### Existing JSON export remains
- `GET /api/export/json` still returns full JSON backup for programmatic use.

---

### 6) Auth + multi-profile scaffolding (toggleable)
- Feature flag: set `ENABLE_AUTH=false` in `.env` to disable auth and keep single-founder mode behavior.
- Minimal auth routes:
  - `GET/POST /signup`
  - `GET/POST /login`
  - `GET /logout`
- Profile route: `GET/POST /settings/profile` for updating name + goal/preferences.
- Data model additions:
  - `users` now supports `email`, `password_hash`, `role`, `enabled`, `created_at`.
  - `subscriptions` stores `user_id`, `plan`, `status`, `start_date`, `end_date`.

### 7) Subscription gating + admin tooling
- Free tier gating:
  - max 1 non-archived plan,
  - template catalog limited to first 3 templates.
- Paid tier unlocks:
  - unlimited plans,
  - priority support,
  - early AI feature access.
- Billing integration stub: `GET /api/billing/checkout` returns provider metadata and `pay_now_link: null` (intentionally unimplemented for safety).
- Internal admin dashboard:
  - `GET /admin` shows users + subscription status,
  - `POST /admin/users/<user_id>/toggle` enables/disables accounts.


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
