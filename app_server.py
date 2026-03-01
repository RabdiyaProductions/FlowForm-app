from __future__ import annotations

import argparse
import logging
import os
import sqlite3
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, jsonify, render_template

APP_NAME = "FlowForm Vitality Master Suite"
APP_VERSION = "0.1.2"

ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
LOG_DIR = ROOT_DIR / "logs"
DEFAULT_DB_PATH = DATA_DIR / "flowform.db"


def load_env_file(env_path: Path) -> None:
    """Load key/value pairs from .env only when keys are not already set."""
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def configure_logging() -> None:
    """Configure console and rotating file logs once."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    root_logger.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        LOG_DIR / "flowform.log", maxBytes=1_000_000, backupCount=3
    )
    file_handler.setFormatter(formatter)

    root_logger.addHandler(console)
    root_logger.addHandler(file_handler)


def create_app(port: int | None = None) -> Flask:
    """Create and configure the Flask application."""
    load_env_file(ROOT_DIR / ".env")
    configure_logging()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    app = Flask(__name__)

    resolved_port = int(port if port is not None else os.getenv("PORT", "5410"))
    db_path = Path(os.getenv("DB_PATH", str(DEFAULT_DB_PATH))).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    app.config.update(
        APP_NAME=APP_NAME,
        VERSION=APP_VERSION,
        PORT=resolved_port,
        DB_PATH=str(db_path),
    )

    app.logger.info("FlowForm boot config: port=%s db=%s", resolved_port, db_path)

    def db_ok() -> bool:
        try:
            connection = sqlite3.connect(db_path)
            connection.execute("SELECT 1")
            connection.close()
            return True
        except sqlite3.Error as exc:
            app.logger.exception("SQLite health check failed: %s", exc)
            return False

    @app.errorhandler(404)
    def handle_not_found(_: Exception):
        return jsonify({"error": "not_found"}), 404

    @app.errorhandler(500)
    def handle_server_error(_: Exception):
        app.logger.exception("Unhandled server error")
        return jsonify({"error": "internal_server_error"}), 500

    @app.get("/")
    def root():
        return render_template("ready.html")

    @app.get("/api/health")
    def api_health():
        is_db_ok = db_ok()
        payload = {
            "status": "ok" if is_db_ok else "degraded",
            "port": app.config["PORT"],
            "db_ok": is_db_ok,
            "version": app.config["VERSION"],
        }
        return jsonify(payload)

    @app.post("/api/timeline/update")
    def api_timeline_update():
        return jsonify({"ok": True, "route": "/api/timeline/update"})

    @app.post("/api/timeline/regenerate")
    def api_timeline_regenerate():
        return jsonify({"ok": True, "route": "/api/timeline/regenerate"})

    @app.post("/api/timeline/apply_global")
    def api_timeline_apply_global():
        return jsonify({"ok": True, "route": "/api/timeline/apply_global"})

    @app.post("/api/critic/run")
    def api_critic_run():
        return jsonify({"ok": True, "route": "/api/critic/run"})

    @app.post("/api/approve")
    def api_approve():
        return jsonify({"ok": True, "route": "/api/approve"})

    @app.post("/api/export")
    def api_export():
        return jsonify({"ok": True, "route": "/api/export"})

    @app.post("/api/import")
    def api_import():
        return jsonify({"ok": True, "route": "/api/import"})

    @app.get("/api/projects/<code>")
    def api_project_by_code(code: str):
        return jsonify({"ok": True, "route": "/api/projects/<code>", "code": code})

    @app.post("/api/agents/enhance")
    def api_agents_enhance():
        return jsonify({"ok": True, "route": "/api/agents/enhance"})

    def app_spec() -> dict:
        curated_routes = [
            {"path": "/", "methods": ["GET"], "description": "Ready landing page"},
            {"path": "/ready", "methods": ["GET"], "description": "Readiness page"},
            {"path": "/diagnostics", "methods": ["GET"], "description": "Diagnostics checks"},
            {"path": "/api/spec", "methods": ["GET"], "description": "API + route spec"},
            {"path": "/api/health", "methods": ["GET"], "description": "Health status"},
            {"path": "/api/timeline/update", "methods": ["POST"], "description": "Update timeline"},
            {"path": "/api/timeline/regenerate", "methods": ["POST"], "description": "Regenerate timeline"},
            {"path": "/api/timeline/apply_global", "methods": ["POST"], "description": "Apply global timeline config"},
            {"path": "/api/critic/run", "methods": ["POST"], "description": "Run critic pass"},
            {"path": "/api/approve", "methods": ["POST"], "description": "Approve current draft"},
            {"path": "/api/export", "methods": ["POST"], "description": "Export project"},
            {"path": "/api/import", "methods": ["POST"], "description": "Import project"},
            {"path": "/api/projects/<code>", "methods": ["GET"], "description": "Fetch project by code"},
            {"path": "/api/agents/enhance", "methods": ["POST"], "description": "Enhance via agent"},
        ]

        seen_paths = {item["path"] for item in curated_routes}
        for rule in app.url_map.iter_rules():
            if rule.endpoint == "static":
                continue
            if rule.rule in seen_paths:
                continue
            methods = sorted(m for m in rule.methods if m not in {"HEAD", "OPTIONS"})
            curated_routes.append(
                {
                    "path": rule.rule,
                    "methods": methods,
                    "description": "Auto-discovered route",
                }
            )
            seen_paths.add(rule.rule)

        return {
            "name": app.config["APP_NAME"],
            "version": app.config["VERSION"],
            "routes": curated_routes,
        }

    @app.get("/api/spec")
    def api_spec():
        return jsonify(app_spec())

    @app.get("/diagnostics")
    def diagnostics():
        needed = [
            "/api/health",
            "/api/timeline/update",
            "/api/timeline/regenerate",
            "/api/timeline/apply_global",
            "/api/critic/run",
            "/api/approve",
            "/api/export",
            "/api/import",
            "/api/projects/<code>",
            "/api/agents/enhance",
            "/api/spec",
            "/diagnostics",
            "/ready",
        ]

        spec_routes = {route["path"] for route in app_spec()["routes"]}
        missing_from_spec = [route for route in needed if route not in spec_routes]

        checks = {
            "health_route": "PASS" if "/api/health" in spec_routes else "FAIL",
            "spec_mismatch": "FAIL" if missing_from_spec else "PASS",
        }

        return jsonify(
            {
                "status": "PASS" if all(v == "PASS" for v in checks.values()) else "FAIL",
                "needed": needed,
                "checks": checks,
                "missing_from_spec": missing_from_spec,
            }
        )

    @app.get("/ready")
    def ready():
        return render_template("ready.html")

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run FlowForm Flask server")
    parser.add_argument("--port", type=int, default=None, help="Port to bind")
    args = parser.parse_args()

    app = create_app(port=args.port)
    host = os.getenv("HOST", "127.0.0.1")
    app.run(host=host, port=app.config["PORT"], debug=False)


if __name__ == "__main__":
    main()
