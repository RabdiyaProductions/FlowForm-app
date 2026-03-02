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
  - `settings.json` (runtime settings snapshot with app version/build metadata),
  - `settings.json` (runtime settings snapshot),
  - `manifest.json` (counts summary + warning),
- `media/*` files from `instance/media/`.
- Exports page includes:
  - **Download Full Backup (ZIP)**,
  - **Export Current Plan (PDF)** one-click button when a plan exists,
  - **Download Plan HTML**,
  - **Export History (CSV)** via `GET /api/export/history.csv`.
  - **Export Plan (PDF/HTML)**,
  - **Export History (CSV)** via `GET /api/export/history.csv`.
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
- backup ZIP validation rejects unsafe or unexpected entries (path traversal hardened).

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


#### Studio Hub ZIP contract: `GET /api/export/zip`
Behavior:
- export is blocked by default until project approval (`POST /api/approve`) unless `?force=true` is passed,
- ZIP always includes: `issue_ref.txt`, `project.json`, `pilot_pack.json`, `export_meta.json`, `WORKFLOW.md`, `manifest.json`,
- `manifest.json` lists every file in the ZIP with `path`, `bytes`, and `sha256` for downstream validation,
- `issue_ref` can be set with query arg (`/api/export/zip?issue_ref=FLOW-123`).

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


### 8) In-app assistant coach
#### UI route: `GET /assistant`
Behavior:
- prompt box plus preset actions: **Tweak my plan**, **Suggest today's substitute**, **Recovery advice**, **Motivate me**.
- shows recent assistant interactions (last 20).

#### API route: `POST /api/assistant/chat`
Behavior:
- if `OPENAI_API_KEY` is present, attempts provider response with a 10s timeout and safe coaching system prompt,
- on provider timeout/error, gracefully falls back to rules-based coaching (no crash/hang),
- without API key, uses rules-based suggestions from current plan + last recovery + recent completions,
- always prepends a safety disclaimer and escalates injury/severe symptom prompts with medical-advice language.


### 9) Personal media library + block attachments
#### UI route: `GET /media`
Behavior:
- upload personal image/audio/video files,
- edit tags and optional duration metadata,
- delete with confirmation,
- serves playable/previewable files from `instance/media/`.

#### Storage
- uploads are saved to `instance/media/`,
- metadata stored in `media_item` table: `filename`, `original_name`, `media_type`, `tags`, `duration_sec`, `uploaded_at`.

#### Template Builder attachment flow
- `GET /templates/builder/<template_id>` shows template blocks and media selector per block,
- `POST /templates/builder/<template_id>/save` links selected media to blocks (`media_item_id` in `json_blocks`).

#### Session Player integration
- `GET /session/start/<plan_day_id>` now hydrates block media and shows linked media (image/audio/video) while playing the block.
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

### 8) Portable Content Pack export
#### Discovery: `GET /content-packs`
Behavior:
- returns JSON list of available session templates (`id`, `name`, `discipline`, `duration`) for content-pack selection.

#### Export: `POST /content-packs/export`
Behavior:
- accepts selected `template_ids`,
- exports a ZIP containing:
  - `content_pack.json` with:
    - selected templates (`id`, `name`, `discipline`, `duration`, `json_blocks`),
    - referenced media metadata (`id`, `filename`, `type`, `tags`),
    - export version metadata (`app_version`, `exported_at`),
  - `media/*` payload files for referenced media only,
- ZIP is staged to a temp file and streamed as download.

Exact steps:
1. Call `GET /content-packs` and choose template IDs.
2. Call `POST /content-packs/export` with selected IDs.
3. Open ZIP and verify `content_pack.json` + referenced `media/*` files.

### 9) Template block media attachments in builder/player
#### Template Builder: `GET /templates/builder/<template_id>` + `POST /templates/builder/<template_id>/save`
Behavior:
- each template block can choose optional media from media library,
- selected media is persisted into `session_template.json_blocks` under `media_id` per block.

#### Session player: `GET /session/player/<template_id>`
Behavior:
- when a block has `media_id`, player shows attached media details and controls,
- includes preview/play UI by media type and a download link to `/media/file/<filename>`.

Exact steps:
1. Open template builder for a template.
2. Select media for one or more blocks and save.
3. Open session player for that template and confirm embedded media controls render.

### 10) Full-fidelity backup/restore for media and imported packs
#### Backup API: `GET /api/export/backup`
Behavior:
- backup ZIP includes database (`flowform.db`), media payload (`media/*`), and exported JSON snapshot (`flowform_backup.json`),
- includes `packs_history.json` when `packs_history` table is present.

#### Restore API: `POST /api/import/backup`
Behavior:
- restores DB and media from backup ZIP,
- performs post-restore media reference validation against template block `media_id`/`media_item_id`,
- missing media references are returned as warnings/report (no crash).
