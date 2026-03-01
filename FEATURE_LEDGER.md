# FEATURE_LEDGER

## Founder-critical plan flow (implemented)

### UI Route: `/plan/wizard` (GET)
Purpose: collect founder planning inputs and submit plan creation.

Fields implemented:
- goal (`strength`, `fat_loss`, `mobility`, `stress`, `hybrid`)
- days/week (`2` to `6`)
- minutes/session (`30` to `75`)
- discipline preferences (rank 1–5)
- constraints (injury flags, equipment, freeform constraints)

Exact click steps:
1. Open `/plan/wizard`.
2. Fill the required fields.
3. Click **Create 4-week plan**.
4. App posts to `POST /api/plan/create` and redirects to `/plan/current`.

### API Route: `/api/plan/create` (POST)
Purpose: generate and persist a 4-week plan.

Behavior implemented:
- Validates/clamps days/week and minutes/session ranges.
- Resolves ordered disciplines from ranked inputs + goal defaults.
- Upserts founder profile preferences.
- Archives existing active plan for same founder.
- Creates new active 4-week plan.
- Generates progressive week/day structure and inserts `plan_day` rows.
- Writes `audit_log` event `plan_created`.

Persistence targets:
- `profile`
- `plan`
- `plan_day`
- `audit_log`

### UI Route: `/plan/current` (GET)
Purpose: display persisted current plan with calendar-style week/day rows.

Implemented UI elements:
- Week cards with day rows, discipline, and duration.
- Today selector (`Week X, Day Y`) computed from plan start date.
- CTA: **Start today's session**.
- CTA: **Regenerate next week** (`POST /api/plan/regenerate-next-week`).

Regeneration behavior:
- Rebuilds next-week rows.
- Does not delete rows that already have `session_completion` records.

## Supporting schema (used by flow)
- `users`
- `profile`
- `plan`
- `plan_day`
- `session_template`
- `session_completion`
- `recovery_checkin`
- `audit_log`

All tables are created via safe migration rules (`CREATE TABLE IF NOT EXISTS` + checked `ALTER`).

## Health and diagnostics for this flow
- `/api/health` includes:
  - `db_ok`
  - `template_count`
- `/diagnostics` includes DB integrity checks and required route coverage for plan flow.

## Boot/test compatibility
- Existing boot scripts are unchanged.
- Structure guard remains integrated in `_BAT/6_run_tests.bat` and `tools/run_full_tests.py`.
