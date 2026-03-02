import json
import os
import json
import sqlite3
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
