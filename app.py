import os
import json
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request, send_file


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


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)

    app.config.update(
        DB_PATH=os.getenv("DATABASE_PATH", "instance/flowform.db"),
        MEDIA_DIR=os.getenv("MEDIA_DIR", "instance/media"),
        VERSION=os.getenv("APP_VERSION", "0.1.0"),
        OPENAI_API_KEY=os.getenv("OPENAI_API_KEY", ""),
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

    @app.post("/content-packs/export")
    def content_packs_export():
        payload = request.get_json(silent=True) or {}
        raw_ids = payload.get("template_ids") or []
        if not isinstance(raw_ids, list):
            raw_ids = [raw_ids]

        template_ids = []
        for item in raw_ids:
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
                f"SELECT id, name, discipline, duration_minutes, json_blocks FROM session_template WHERE id IN ({placeholders}) ORDER BY id ASC",
                tuple(template_ids),
            ).fetchall()

            media_ids = set()
            templates_payload = []
            for row in template_rows:
                for block in blocks_from_json(row["json_blocks"]):
                    try:
                        media_id = int(block.get("media_item_id")) if block.get("media_item_id") is not None else None
                    except (TypeError, ValueError):
                        media_id = None
                    if media_id:
                        media_ids.add(media_id)
                templates_payload.append(
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
            "media": [
                {
                    "id": int(row["id"]),
                    "filename": row["filename"],
                    "type": row["media_type"],
                    "tags": [tag.strip() for tag in str(row["tags"] or "").split(",") if tag.strip()],
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

        response = send_file(temp_path, mimetype="application/zip", as_attachment=True, download_name="content_pack.zip")

        @response.call_on_close
        def _cleanup_temp_export() -> None:
            temp_path.unlink(missing_ok=True)

        return response

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5000")))
