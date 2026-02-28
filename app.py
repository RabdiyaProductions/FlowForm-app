import os
import sqlite3
from pathlib import Path

from flask import Flask, jsonify


def _init_db(db_path: Path) -> None:
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


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)

    app.config.update(
        DB_PATH=os.getenv("DATABASE_PATH", "instance/flowform.db"),
        OPENAI_API_KEY=os.getenv("OPENAI_API_KEY", ""),
    )

    if test_config:
        app.config.update(test_config)

    db_path = Path(app.config["DB_PATH"])
    _init_db(db_path)

    @app.get("/api/health")
    def api_health():
        return jsonify(
            {
                "status": "healthy",
                "service": "flowform-app",
                "ai": {
                    "enabled": bool(app.config.get("OPENAI_API_KEY")),
                    "reason": None
                    if app.config.get("OPENAI_API_KEY")
                    else "OPENAI_API_KEY missing; AI features disabled",
                },
            }
        )

    @app.get("/ready")
    def ready():
        module_status = {"flask": "ok", "sqlite3": "ok"}
        db_status = {"path": str(db_path), "initialized": db_path.exists()}
        log_status = {"level": os.getenv("LOG_LEVEL", "INFO")}

        return jsonify(
            {
                "status": "ready",
                "db": db_status,
                "module": module_status,
                "log": log_status,
            }
        )

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
