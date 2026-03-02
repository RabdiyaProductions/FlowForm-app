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


## Journey 7 — Full backup download works
**Steps**
1. Open `/exports`.
2. Click **Download full backup**.
3. Open downloaded ZIP and inspect contents.

**Accept if**
- ZIP contains `flowform.db`, `flowform_backup.json`, `settings.json`, and `manifest.json`,
- ZIP contains `media/` files when media exists,
- backup can be created in one click without app errors.

Exact click steps:
1. Create a plan and complete at least one session.
2. Open `/exports`.
3. Click **Download Full Backup (ZIP)**.
4. Click **Export History (CSV)**.
5. Click **Download Plan HTML** and **Download plan PDF**.


## Journey 8 — Restore requires confirmation and overwrites safely
**Steps**
1. Open `/restore`.
2. Select backup ZIP.
3. Click **Preview restore summary** and verify counts/warning.
4. Click **Confirm and restore** and accept confirmation prompt.

**Accept if**
- preview shows counts and explicit overwrite warning,
- restore only runs after confirmation,
- restore failure returns error with no partial apply,
- successful restore replaces current DB/media with backup state.

Recovery drill:
1. Create a plan, complete one session, and submit one recovery check-in.
2. Backup from `/exports` using **Download Full Backup (ZIP)**.
3. Stop app and remove/rename local DB file.
4. Start app, open `/restore`, preview summary, confirm restore.
5. Open `/plan/current` and verify plan/completion/recovery data reappears.
1. Backup from `/exports`.
2. Stop app and remove/rename local DB file.
3. Start app, open `/restore`, preview summary, confirm restore.
4. Open `/plan/current` and verify plan/completion/recovery data reappears.


## Journey 9 — PDF exports are readable and complete
**Steps**
1. From `/exports`, export a plan PDF with `/api/export/plan_pdf/<plan_id>`.
2. Export a session summary PDF with `/api/export/session_summary/<completion_id>`.

**Accept if**
- plan PDF shows 4-week schedule details,
- session PDF shows blocks, RPE, notes, and completion details,
- both return `application/pdf` and download successfully.


## Journey 10 — Multi-user signup/login with isolated plans
**Steps**
1. Set `ENABLE_AUTH=true` in `.env` (or env var for test runtime).
2. Sign up User A and create a plan.
3. Log out.
4. Sign up User B and create a separate plan.
5. Log back in as User A and open `/plan/current`.

**Accept if**
- each user can log in successfully,
- User A sees only User A’s plan data,
- User B sees only User B’s plan data.


## Journey 11 — Subscription gating works for free tier
**Steps**
1. Sign up a new free user.
2. Create one plan successfully.
3. Attempt to create a second active plan.

**Accept if**
- first plan succeeds,
- second plan is blocked with free-tier message,
- response includes paid benefits and no live pay link (`pay_now_link` is null).


## Journey 12 — Auth can be disabled for single-user mode
**Steps**
1. Set `ENABLE_AUTH=false`.
2. Start app and open founder routes directly.

**Accept if**
- no login/signup required,
- single-founder flow remains functional.


## Journey 13 — Studio Hub ZIP contract is complete and gated
**Steps**
1. Attempt `GET /api/export/zip` before approval.
2. Confirm request is blocked with a clear approval message.
3. Approve via `POST /api/approve` (or retry with `?force=true`).
4. Download ZIP and inspect files + manifest.

**Accept if**
- unapproved export returns `project_not_approved` and guidance to approve or force,
- ZIP always includes `issue_ref.txt`, `project.json`, `pilot_pack.json`, `export_meta.json`, `WORKFLOW.md`, `manifest.json`,
- `manifest.json` includes every ZIP file and includes `export_meta.json`,
- each manifest item includes `path`, `bytes`, and `sha256`.


## Journey 14 — Assistant works with and without API key
**Steps**
1. Open `/assistant`.
2. Click each preset button and send a prompt.
3. Verify a response appears with the safety disclaimer.
4. Test an injury/symptom prompt (for example chest pain/dizziness).
5. Run without `OPENAI_API_KEY` and repeat one prompt.

**Accept if**
- presets are available for plan tweak/substitution/recovery/motivation,
- responses are returned without crashes/hangs,
- responses always include the disclaimer,
- severe symptom prompts include escalation language to seek medical advice,
- fallback rules engine provides useful guidance when API key is missing or provider fails.


## Journey 15 — Media upload and block attachment works
**Steps**
1. Open `/media` and upload an image/audio/video file with tags.
2. Open `/templates`, click **Template Builder** for a template, and attach the media to block 1.
3. Create/refresh plan and open `/session/start/<plan_day_id>` that uses that template.

**Accept if**
- upload persists in media library with metadata/tags,
- template block saves linked media selection,
- session player shows linked media for the active block.

## Journey 16 — Portable Content Pack ZIP export works
**Steps**
1. Call `GET /content-packs` and select one or more template IDs.
2. Call `POST /content-packs/export` with selected `template_ids`.
3. Open the returned ZIP.

**Accept if**
- response is a downloadable ZIP,
- ZIP includes `content_pack.json`,
- `content_pack.json` includes selected templates and export metadata (`app_version`, `exported_at`),
- ZIP includes `media/*` files only for media referenced by selected templates.

## Journey 17 — Block media attachments render during playback
**Steps**
1. Open template builder for an existing template.
2. Attach media to at least one block and save.
3. Open session player page for that template.

**Accept if**
- block-level `media_id` is persisted in template blocks,
- player page shows attached media details,
- player provides preview/play/download controls for attached media.
