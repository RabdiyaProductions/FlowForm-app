import json
import os
import json
import sqlite3
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request, send_file, render_template_string, redirect, url_for
from werkzeug.utils import secure_filename
from flask import Flask, jsonify, request, send_file
from flask import Flask, jsonify, send_file, request


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def blocks_from_json(raw: str) -> list[dict]:
    try:
        payload = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return []
    blocks = payload.get("blocks") if isinstance(payload, dict) else None
    return blocks if isinstance(blocks, list) else []


def table_exists(connection: sqlite3.Connection, name: str) -> bool:
    row = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone()
    return row is not None


NAV_ITEMS = [
    ("Templates", "/templates"),
    ("Media", "/media"),
    ("Content Packs", "/content-packs/ui"),
]


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO app_metadata (key, value)
            VALUES ('initialized', 'true')
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS session_template (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                discipline TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL,
                json_blocks TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS media_item (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                media_type TEXT NOT NULL,
                tags TEXT NOT NULL DEFAULT ''
            )
            """
        )


def parse_blocks(raw: str) -> list[dict]:
    try:
        payload = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return []
    blocks = payload.get("blocks") if isinstance(payload, dict) else None
    return blocks if isinstance(blocks, list) else []


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)

    app.config.update(
        DB_PATH=os.getenv("DATABASE_PATH", "instance/flowform.db"),
        MEDIA_DIR=os.getenv("MEDIA_DIR", "instance/media"),
        VERSION=os.getenv("APP_VERSION", "0.1.0"),
        OPENAI_API_KEY=os.getenv("OPENAI_API_KEY", ""),
        VERSION=os.getenv("APP_VERSION", "0.1.0"),
    )

    if test_config:
        app.config.update(test_config)

    db_path = Path(app.config["DB_PATH"])
    media_dir = Path(app.config["MEDIA_DIR"])
    media_dir.mkdir(parents=True, exist_ok=True)
    init_db(db_path)

    def render_page(title: str, content_html: str, **context):
        return render_template_string(
            """
            <!doctype html>
            <html>
              <head>
                <meta charset="utf-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1" />
                <title>{{ title }}</title>
                <style>
                  body { font-family: Arial, sans-serif; margin: 0; background: #f8fafc; }
                  .nav { display: flex; gap: 8px; padding: 12px; background: #0f172a; flex-wrap: wrap; }
                  .nav a { color: white; text-decoration: none; padding: 8px 12px; border-radius: 8px; }
                  .nav a.active { background: #2563eb; }
                  .shell { max-width: 980px; margin: 0 auto; padding: 16px; }
                  .card { background: white; border-radius: 10px; padding: 14px; margin-bottom: 12px; }
                  .cta { display: inline-block; background: #2563eb; color: white; padding: 8px 12px; border-radius: 8px; text-decoration: none; border: none; }
                  .muted { color: #64748b; }
                  .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
                  @media (max-width: 640px) {
                    .shell { padding: 10px; }
                    .nav { gap: 6px; padding: 10px; }
                    .nav a { flex: 1 1 auto; text-align: center; }
                  }
                </style>
              </head>
              <body>
                <nav class="nav">
                  {% for name, href in nav_items %}
                    <a href="{{ href }}" class="{% if href == active_path %}active{% endif %}">{{ name }}</a>
                  {% endfor %}
                </nav>
                <main class="shell">{{ content_html|safe }}</main>
              </body>
            </html>
            """,
            title=title,
            nav_items=NAV_ITEMS,
            active_path=request.path,
            content_html=content_html,
            **context,
        )

    @app.get("/api/health")
    def api_health():
        api_key = app.config.get("OPENAI_API_KEY", "")
        ai_enabled = bool(api_key)
        return jsonify(
            {
                "status": "healthy",
                "service": "flowform-app",
                "ai": {
                    "enabled": ai_enabled,
                    "reason": None if ai_enabled else "OPENAI_API_KEY missing; AI features disabled",
                },
            }
        )

    @app.get("/ready")
    def ready():
        return jsonify(
            {
                "status": "ready",
                "db": {
                    "path": str(db_path),
                    "initialized": db_path.exists(),
                },
                "module": {
                    "flask": "ok",
                    "sqlite3": "ok",
                },
                "log": {
                    "level": os.getenv("LOG_LEVEL", "INFO"),
                },
            }
        )

    @app.get("/content-packs")
    def content_packs_index():
    def list_content_packs():
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, name, discipline, duration_minutes FROM session_template ORDER BY id ASC"
            ).fetchall()
        return jsonify(
            {
                "templates": [
                    {
                        "id": int(r["id"]),
                        "name": r["name"],
                        "discipline": r["discipline"],
                        "duration": int(r["duration_minutes"]),
                    }
                    for r in rows
                ]
            }
        )

    @app.get("/content-packs/ui")
    def content_packs_ui():
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT id, name, discipline, duration_minutes FROM session_template ORDER BY id ASC").fetchall()
        if not rows:
            return render_page(
                "Content Packs",
                """
                <div class='card'>
                  <h1>Content Packs</h1>
                  <p class='muted'>No templates yet. Import a pack or create your first template to start exporting premium packs.</p>
                  <div class='row'>
                    <form method='post' action='/content-packs/import' enctype='multipart/form-data'>
                      <input name='file' type='file' required />
                      <button class='cta' type='submit'>Import Pack ZIP</button>
                    </form>
                    <a class='cta' href='/templates'>Create Template</a>
                  </div>
                </div>
                """,
            )

        items = "".join(
            f"<label class='card'><input type='checkbox' name='template_ids' value='{int(r['id'])}' /> "
            f"{r['name']} · {r['discipline']} · {int(r['duration_minutes'])} min</label>"
            for r in rows
        )
        return render_page(
            "Content Packs",
            f"""
            <h1>Content Packs</h1>
            <p class='muted'>Select templates, then export only the media those templates reference.</p>
            <form method='post' action='/content-packs/export/form'>
              {items}
              <button class='cta' type='submit'>Export Content Pack ZIP</button>
            </form>
            <div class='card'>
              <form method='post' action='/content-packs/import' enctype='multipart/form-data'>
                <input name='file' type='file' required />
                <button class='cta' type='submit'>Import Pack ZIP</button>
              </form>
            </div>
            """,
        )

    @app.post("/content-packs/export/form")
    def content_packs_export_form():
        ids = request.form.getlist("template_ids")
        return content_packs_export_internal(ids)

    def content_packs_export_internal(raw_ids):
                        "id": int(row["id"]),
                        "name": row["name"],
                        "discipline": row["discipline"],
                        "duration": int(row["duration_minutes"]),
                    }
                    for row in rows
                ]
            }
        )

    @app.post("/content-packs/export")
    def content_packs_export():
        payload = request.get_json(silent=True) or {}
        raw_ids = payload.get("template_ids") or []
        if not isinstance(raw_ids, list):
            raw_ids = [raw_ids]

        template_ids = []
        for item in raw_ids:
    def export_content_pack():
        payload = request.get_json(silent=True) or {}
        ids = payload.get("template_ids") or []
        if not isinstance(ids, list):
            ids = [ids]

        template_ids = []
        for item in ids:
            try:
                template_ids.append(int(item))
            except (TypeError, ValueError):
                continue
        template_ids = sorted(set(template_ids))
        if not template_ids:
            return jsonify({"error": "template_ids_required"}), 400

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            placeholders = ",".join("?" for _ in template_ids)
            template_rows = conn.execute(
            templates = conn.execute(
                f"SELECT id, name, discipline, duration_minutes, json_blocks FROM session_template WHERE id IN ({placeholders}) ORDER BY id ASC",
                tuple(template_ids),
            ).fetchall()

            media_ids = set()
            templates_payload = []
            for row in template_rows:
                for block in blocks_from_json(row["json_blocks"]):
                    block_ref = block.get("media_id")
                    if block_ref is None:
                        block_ref = block.get("media_item_id")
                    try:
                        media_id = int(block_ref) if block_ref is not None else None
                    try:
                        media_id = int(block.get("media_item_id")) if block.get("media_item_id") is not None else None
            template_payload = []
            for row in templates:
                blocks = parse_blocks(row["json_blocks"])
                for block in blocks:
                    try:
                        media_id = int(block.get("media_item_id"))
                    except (TypeError, ValueError):
                        media_id = None
                    if media_id:
                        media_ids.add(media_id)
                templates_payload.append(
                template_payload.append(
                    {
                        "id": int(row["id"]),
                        "name": row["name"],
                        "discipline": row["discipline"],
                        "duration": int(row["duration_minutes"]),
                        "json_blocks": row["json_blocks"],
                    }
                )

            media_rows = []
            if media_ids:
                media_placeholders = ",".join("?" for _ in media_ids)
                media_rows = conn.execute(
                    f"SELECT id, filename, media_type, tags FROM media_item WHERE id IN ({media_placeholders}) ORDER BY id ASC",
                    tuple(sorted(media_ids)),
                ).fetchall()

        content_pack = {
            "version": {"app_version": app.config["VERSION"], "exported_at": utc_now_iso()},
            "templates": templates_payload,
            "templates": template_payload,
            "media": [
                {
                    "id": int(row["id"]),
                    "filename": row["filename"],
                    "type": row["media_type"],
                    "tags": [tag.strip() for tag in str(row["tags"] or "").split(",") if tag.strip()],
                    "tags": row["tags"],
                }
                for row in media_rows
            ],
        }

        temp = tempfile.NamedTemporaryFile(prefix="flowform_content_pack_", suffix=".zip", delete=False)
        temp_path = Path(temp.name)
        temp.close()

        with zipfile.ZipFile(temp_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("content_pack.json", json.dumps(content_pack, indent=2))
            for row in media_rows:
                path = media_dir / row["filename"]
                if path.exists() and path.is_file():
                    zf.write(path, arcname=f"media/{row['filename']}")
        temp_file = tempfile.NamedTemporaryFile(prefix="content_pack_", suffix=".zip", delete=False)
        temp_path = Path(temp_file.name)
        temp_file.close()

        with zipfile.ZipFile(temp_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("content_pack.json", json.dumps(content_pack, indent=2))
            for row in media_rows:
                media_path = media_dir / row["filename"]
                if media_path.exists() and media_path.is_file():
                    archive.write(media_path, arcname=f"media/{row['filename']}")

        response = send_file(temp_path, mimetype="application/zip", as_attachment=True, download_name="content_pack.zip")

        @response.call_on_close
        def _cleanup_temp_export() -> None:
        def _cleanup() -> None:
            temp_path.unlink(missing_ok=True)

        return response

    @app.post("/content-packs/export")
    def content_packs_export():
        payload = request.get_json(silent=True) or {}
        return content_packs_export_internal(payload.get("template_ids") or [])

    @app.post("/content-packs/import")
    def content_packs_import():
        upload = request.files.get("file")
        if upload is None or not upload.filename:
            return jsonify({"ok": False, "error": "file_required"}), 400
        with tempfile.TemporaryDirectory(prefix="content_pack_import_") as temp_dir:
            archive_path = Path(temp_dir) / "pack.zip"
            upload.save(archive_path)
            with zipfile.ZipFile(archive_path, "r") as zf:
                if "content_pack.json" not in zf.namelist():
                    return jsonify({"ok": False, "error": "content_pack_json_missing"}), 400
                payload = json.loads(zf.read("content_pack.json"))

                with sqlite3.connect(db_path) as conn:
                    for t in payload.get("templates") or []:
                        conn.execute(
                            "INSERT INTO session_template (name, discipline, duration_minutes, json_blocks) VALUES (?, ?, ?, ?)",
                            (t.get("name") or "Imported Template", t.get("discipline") or "general", int(t.get("duration") or 0), t.get("json_blocks") or "{\"blocks\":[]}"),
                        )
                    for m in payload.get("media") or []:
                        filename = secure_filename(str(m.get("filename") or ""))
                        if not filename:
                            continue
                        if f"media/{filename}" in zf.namelist():
                            (media_dir / filename).write_bytes(zf.read(f"media/{filename}"))
                        conn.execute(
                            "INSERT INTO media_item (filename, media_type, tags) VALUES (?, ?, ?)",
                            (filename, str(m.get("type") or "other"), ", ".join(m.get("tags") or [])),
                        )
                    conn.commit()
        return redirect(url_for("content_packs_ui"))

    @app.get("/media")
    def media_library():
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT id, filename, media_type FROM media_item ORDER BY id DESC").fetchall()
        if not rows:
            return render_page(
                "Media",
                """
                <div class='card'>
                  <h1>Media Library</h1>
                  <p class='muted'>No media uploaded yet. Upload media to attach it to template blocks.</p>
                  <form method='post' action='/media/upload' enctype='multipart/form-data'>
                    <input type='file' name='file' required />
                    <button class='cta' type='submit'>Upload Media</button>
                  </form>
                </div>
                """,
            )
        items = "".join(f"<li>{r['filename']} ({r['media_type']})</li>" for r in rows)
        return render_page(
            "Media",
            f"""
            <h1>Media Library</h1>
            <div class='card'>
              <form method='post' action='/media/upload' enctype='multipart/form-data'>
                <input type='file' name='file' required />
                <button class='cta' type='submit'>Upload More</button>
              </form>
            </div>
            <div class='card'><ul>{items}</ul></div>
            """,
        )

    @app.post("/media/upload")
    def media_upload():
        upload = request.files.get("file")
        if upload is None or not upload.filename:
            return redirect(url_for("media_library"))
        filename = secure_filename(upload.filename)
        if not filename:
            return redirect(url_for("media_library"))
        (media_dir / filename).write_bytes(upload.read())
        media_type = "video" if filename.lower().endswith((".mp4", ".webm")) else "audio" if filename.lower().endswith((".mp3", ".wav")) else "image"
        with sqlite3.connect(db_path) as conn:
            conn.execute("INSERT INTO media_item (filename, media_type, tags) VALUES (?, ?, ?)", (filename, media_type, ""))
            conn.commit()
        return redirect(url_for("media_library"))

    @app.get("/templates")
    def templates_page():
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT id, name, discipline, duration_minutes FROM session_template ORDER BY id DESC").fetchall()
        if not rows:
            return render_page(
                "Templates",
                """
                <div class='card'>
                  <h1>Templates</h1>
                  <p class='muted'>No templates yet. Create one now or import a Content Pack.</p>
                  <div class='row'>
                    <form method='post' action='/templates/create'>
                      <input name='name' placeholder='Template name' required />
                      <button class='cta' type='submit'>Create Template</button>
                    </form>
                    <a class='cta' href='/content-packs/ui'>Import Content Pack</a>
                  </div>
                </div>
                """,
            )
        items = "".join(
            f"<li><a href='/templates/builder/{int(r['id'])}'>{r['name']}</a> · {r['discipline']} · {int(r['duration_minutes'])} min</li>"
            for r in rows
        )
        return render_page("Templates", f"<h1>Templates</h1><div class='card'><ul>{items}</ul></div>")

    @app.post("/templates/create")
    def templates_create():
        name = (request.form.get("name") or "New Template").strip()
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT INTO session_template (name, discipline, duration_minutes, json_blocks) VALUES (?, ?, ?, ?)",
                (name, "general", 30, json.dumps({"blocks": [{"name": "Block 1", "minutes": 30}]})),
            )
            template_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            conn.commit()
        return redirect(url_for("template_builder", template_id=template_id))

    @app.get("/api/export/backup")
    def export_backup():
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            templates = conn.execute(
                "SELECT id, name, discipline, duration_minutes, json_blocks FROM session_template ORDER BY id ASC"
            ).fetchall()
            media_items = conn.execute(
                "SELECT id, filename, media_type, tags FROM media_item ORDER BY id ASC"
            ).fetchall()
            packs_history_rows = []
            if table_exists(conn, "packs_history"):
                packs_history_rows = conn.execute("SELECT * FROM packs_history ORDER BY id ASC").fetchall()

        snapshot = {
            "exported_at": utc_now_iso(),
            "templates": [dict(r) for r in templates],
            "media": [dict(r) for r in media_items],
            "packs_history": [dict(r) for r in packs_history_rows],
        }

        temp = tempfile.NamedTemporaryFile(prefix="flowform_backup_", suffix=".zip", delete=False)
        temp_path = Path(temp.name)
        temp.close()
        with zipfile.ZipFile(temp_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            if db_path.exists():
                zf.write(db_path, arcname="flowform.db")
            zf.writestr("flowform_backup.json", json.dumps(snapshot, indent=2))
            if snapshot["packs_history"]:
                zf.writestr("packs_history.json", json.dumps(snapshot["packs_history"], indent=2))
            if media_dir.exists():
                for item in media_dir.iterdir():
                    if item.is_file():
                        zf.write(item, arcname=f"media/{item.name}")

        response = send_file(temp_path, mimetype="application/zip", as_attachment=True, download_name="flowform_full_backup.zip")

        @response.call_on_close
        def _cleanup_backup_temp() -> None:
            temp_path.unlink(missing_ok=True)

        return response

    @app.post("/api/import/backup")
    def import_backup():
        upload = request.files.get("file")
        if upload is None or not upload.filename:
            return jsonify({"ok": False, "error": "file_required"}), 400

        temp_dir = Path(tempfile.mkdtemp(prefix="flowform_restore_"))
        archive_path = temp_dir / "backup.zip"
        upload.save(archive_path)

        warnings = []
        try:
            with zipfile.ZipFile(archive_path, "r") as zf:
                zf.extractall(temp_dir / "unzipped")

            unzipped = temp_dir / "unzipped"
            restored_db = unzipped / "flowform.db"
            restored_media = unzipped / "media"
            if restored_db.exists():
                shutil.copy2(restored_db, db_path)

            if media_dir.exists():
                shutil.rmtree(media_dir)
            media_dir.mkdir(parents=True, exist_ok=True)
            if restored_media.exists():
                for item in restored_media.iterdir():
                    if item.is_file():
                        shutil.copy2(item, media_dir / item.name)

            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                media_rows = conn.execute("SELECT id, filename FROM media_item").fetchall()
                media_lookup = {int(r["id"]): str(r["filename"]) for r in media_rows}
                templates = conn.execute("SELECT id, json_blocks FROM session_template").fetchall()

            missing = []
            for row in templates:
                for block in blocks_from_json(row["json_blocks"]):
                    if block.get("media_id") is None and block.get("media_item_id") is None:
                        continue
                    media_ref = block.get("media_id") if block.get("media_id") is not None else block.get("media_item_id")
                    if media_ref is None:
                        continue
                    try:
                        media_id = int(media_ref)
                    except (TypeError, ValueError):
                        missing.append({"template_id": int(row["id"]), "media_id": media_ref, "reason": "invalid_media_id"})
                        continue
                    filename = media_lookup.get(media_id)
                    if not filename:
                        missing.append({"template_id": int(row["id"]), "media_id": media_id, "reason": "media_row_missing"})
                        continue
                    if not (media_dir / filename).exists():
                        missing.append({"template_id": int(row["id"]), "media_id": media_id, "filename": filename, "reason": "media_file_missing"})

            if missing:
                warnings.append({"code": "missing_media_references", "items": missing})

            return jsonify({"ok": True, "warnings": warnings})
        except zipfile.BadZipFile:
            return jsonify({"ok": False, "error": "invalid_zip"}), 400
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @app.get("/templates/builder/<int:template_id>")
    def template_builder(template_id: int):
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            template = conn.execute(
                "SELECT id, name, json_blocks FROM session_template WHERE id = ?",
                (template_id,),
            ).fetchone()
            if template is None:
                return jsonify({"error": "template_not_found"}), 404
            media_items = conn.execute(
                "SELECT id, filename, media_type, tags FROM media_item ORDER BY id DESC"
            ).fetchall()

        blocks = blocks_from_json(template["json_blocks"])
        if not media_items:
            no_media_cta = "<p class='muted'>No media yet. <a class='cta' href='/media'>Upload media</a> before attaching it to blocks.</p>"
        else:
            no_media_cta = ""
        block_forms = "".join(
            f"""
            <div class='card'>
              <strong>{block.get('name', 'Block')}</strong>
              <select name='media_id_{idx}'>
                <option value=''>No media</option>
                {''.join([f"<option value='{int(item['id'])}' {'selected' if block.get('media_id') == item['id'] else ''}>{item['filename']} ({item['media_type']})</option>" for item in media_items])}
              </select>
            </div>
            """
            for idx, block in enumerate(blocks)
        )
        return render_page(
            "Template Builder",
            f"""
            <h1>Template Builder: {template['name']}</h1>
            {no_media_cta}
            <form method='post' action='/templates/builder/{int(template['id'])}/save'>
              {block_forms or "<p class='muted'>No blocks defined.</p>"}
              <button class='cta' type='submit'>Save Attachments</button>
            </form>
            """,
        return render_template_string(
            """
            <h1>Template Builder: {{ template['name'] }}</h1>
            <form method="post" action="{{ url_for('template_builder_save', template_id=template['id']) }}">
            {% for block in blocks %}
              <div>
                <strong>{{ block.get('name', 'Block') }}</strong>
                <select name="media_id_{{ loop.index0 }}">
                  <option value="">No media</option>
                  {% for item in media_items %}
                    <option value="{{ item['id'] }}" {% if block.get('media_id') == item['id'] %}selected{% endif %}>
                      {{ item['filename'] }} ({{ item['media_type'] }})
                    </option>
                  {% endfor %}
                </select>
              </div>
            {% endfor %}
              <button type="submit">Save</button>
            </form>
            """,
            template=template,
            blocks=blocks,
            media_items=media_items,
        )

    @app.post("/templates/builder/<int:template_id>/save")
    def template_builder_save(template_id: int):
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            template = conn.execute(
                "SELECT id, json_blocks FROM session_template WHERE id = ?",
                (template_id,),
            ).fetchone()
            if template is None:
                return jsonify({"error": "template_not_found"}), 404

            blocks = blocks_from_json(template["json_blocks"])
            for idx, block in enumerate(blocks):
                raw_media = request.form.get(f"media_id_{idx}")
                try:
                    block["media_id"] = int(raw_media) if raw_media else None
                except ValueError:
                    block["media_id"] = None

            conn.execute(
                "UPDATE session_template SET json_blocks = ? WHERE id = ?",
                (json.dumps({"blocks": blocks}), template_id),
            )
            conn.commit()

        return redirect(url_for("template_builder", template_id=template_id))

    @app.get("/media/file/<path:filename>")
    def media_file(filename: str):
        safe_name = secure_filename(filename)
        if not safe_name:
            return jsonify({"error": "invalid_filename"}), 400
        path = media_dir / safe_name
        if not path.exists() or not path.is_file():
            return jsonify({"error": "media_not_found"}), 404
        return send_file(path)

    @app.get("/session/player/<int:template_id>")
    def session_player(template_id: int):
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            template = conn.execute(
                "SELECT id, name, json_blocks FROM session_template WHERE id = ?",
                (template_id,),
            ).fetchone()
            if template is None:
                return jsonify({"error": "template_not_found"}), 404
            media_rows = conn.execute("SELECT id, filename, media_type FROM media_item").fetchall()
        media_map = {int(r["id"]): dict(r) for r in media_rows}
        blocks = blocks_from_json(template["json_blocks"])
        for block in blocks:
            media_id = block.get("media_id")
            block["media"] = media_map.get(int(media_id)) if media_id else None

        sections = []
        for block in blocks:
            media = block.get("media")
            media_html = "<p class='muted'>No media attached.</p>"
            if media:
                file_url = url_for("media_file", filename=media["filename"])
                media_html = f"<div>Attached media: {media['filename']}</div><a class='cta' href='{file_url}'>Download</a>"
                if media["media_type"] == "video":
                    media_html += f"<div><video controls width='320' src='{file_url}'></video></div>"
                elif media["media_type"] == "audio":
                    media_html += f"<div><audio controls src='{file_url}'></audio></div>"
                else:
                    media_html += f"<div><img alt='preview' width='240' src='{file_url}' /></div>"
            sections.append(f"<section class='card'><h2>{block.get('name', 'Block')}</h2>{media_html}</section>")

        return render_page(
            "Session Player",
            f"<h1>Session Player: {template['name']}</h1>{''.join(sections)}",
        return render_template_string(
            """
            <h1>Session Player: {{ template['name'] }}</h1>
            {% for block in blocks %}
              <section>
                <h2>{{ block.get('name', 'Block') }}</h2>
                {% if block.get('media') %}
                  <div>Attached media: {{ block['media']['filename'] }}</div>
                  <a href="{{ url_for('media_file', filename=block['media']['filename']) }}">Download</a>
                  {% if block['media']['media_type'] == 'video' %}
                    <video controls width="320" src="{{ url_for('media_file', filename=block['media']['filename']) }}"></video>
                  {% elif block['media']['media_type'] == 'audio' %}
                    <audio controls src="{{ url_for('media_file', filename=block['media']['filename']) }}"></audio>
                  {% else %}
                    <img alt="preview" width="240" src="{{ url_for('media_file', filename=block['media']['filename']) }}" />
                  {% endif %}
                {% endif %}
              </section>
            {% endfor %}
            """,
            template=template,
            blocks=blocks,
        )

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5000")))
