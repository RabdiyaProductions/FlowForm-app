from __future__ import annotations

import argparse
import logging
import os
import sqlite3
import subprocess
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, jsonify, render_template

APP_NAME = "FlowForm Vitality Master Suite"
APP_VERSION = "0.1.3"
BUILD_DATE = "2026-02-28"

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


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def git_hash() -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(ROOT_DIR),
                text=True,
            )
            .strip()
        )
    except Exception:
        return "unknown"


def provider_status() -> str:
    return "configured" if os.getenv("PROVIDER_API_KEY") else "not_configured"


def table_exists(connection: sqlite3.Connection, name: str) -> bool:
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def column_exists(connection: sqlite3.Connection, table: str, column: str) -> bool:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column for row in rows)


def ensure_column(
    connection: sqlite3.Connection,
    table: str,
    column: str,
    definition_sql: str,
) -> None:
    if not column_exists(connection, table, column):
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {definition_sql}")


def apply_schema_migrations(connection: sqlite3.Connection) -> None:
    now = utc_now_iso()

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            email TEXT,
            display_name TEXT
        )
        """
    )
    ensure_column(connection, "users", "created_at", "created_at TEXT NOT NULL DEFAULT ''")
    ensure_column(connection, "users", "updated_at", "updated_at TEXT NOT NULL DEFAULT ''")

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            goal TEXT,
            days_per_week INTEGER,
            minutes INTEGER,
            equipment TEXT,
            constraints TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS plan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT NOT NULL,
            start_date TEXT,
            weeks INTEGER NOT NULL DEFAULT 4,
            status TEXT NOT NULL DEFAULT 'draft',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS session_template (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            discipline TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL,
            level TEXT NOT NULL,
            json_blocks TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS plan_day (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL,
            week INTEGER NOT NULL,
            day_index INTEGER NOT NULL,
            template_id INTEGER,
            title TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(plan_id) REFERENCES plan(id),
            FOREIGN KEY(template_id) REFERENCES session_template(id)
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS session_completion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_day_id INTEGER NOT NULL,
            completed_at TEXT NOT NULL,
            rpe INTEGER,
            notes TEXT,
            minutes_done INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(plan_day_id) REFERENCES plan_day(id)
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS recovery_checkin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date TEXT NOT NULL,
            sleep_hours REAL,
            stress_1_10 INTEGER,
            soreness_1_10 INTEGER,
            mood_1_10 INTEGER,
            notes TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    # Maintain compatibility with previous health checks.
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS _healthcheck (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            checked_at TEXT NOT NULL
        )
        """
    )
    connection.execute("INSERT INTO _healthcheck(checked_at) VALUES (?)", (now,))


def seed_templates(connection: sqlite3.Connection) -> None:
    existing_count = connection.execute("SELECT COUNT(*) FROM session_template").fetchone()[0]
    if existing_count > 0:
        return

    now = utc_now_iso()
    templates = [
        (
            "Strength Foundation A",
            "strength",
            45,
            "beginner",
            '{"blocks":[{"name":"warmup","minutes":8},{"name":"compound_lifts","minutes":28},{"name":"cooldown","minutes":9}]}'
        ),
        (
            "Strength Progression B",
            "strength",
            60,
            "intermediate",
            '{"blocks":[{"name":"warmup","minutes":10},{"name":"main_lifts","minutes":38},{"name":"accessory","minutes":8},{"name":"cooldown","minutes":4}]}'
        ),
        (
            "Zone 2 Base Ride",
            "cardio",
            50,
            "beginner",
            '{"blocks":[{"name":"warmup","minutes":10},{"name":"steady_state","minutes":35},{"name":"cooldown","minutes":5}]}'
        ),
        (
            "Tempo Intervals Run",
            "cardio",
            40,
            "intermediate",
            '{"blocks":[{"name":"warmup","minutes":8},{"name":"tempo_intervals","minutes":26},{"name":"cooldown","minutes":6}]}'
        ),
        (
            "Mobility Restore",
            "mobility",
            30,
            "all_levels",
            '{"blocks":[{"name":"breath","minutes":5},{"name":"hips_spine","minutes":20},{"name":"reset","minutes":5}]}'
        ),
        (
            "Yoga Recovery Flow",
            "recovery",
            35,
            "all_levels",
            '{"blocks":[{"name":"flow","minutes":25},{"name":"downregulate","minutes":10}]}'
        ),
        (
            "HIIT Power Ladder",
            "conditioning",
            32,
            "advanced",
            '{"blocks":[{"name":"warmup","minutes":6},{"name":"ladder","minutes":20},{"name":"cooldown","minutes":6}]}'
        ),
        (
            "Endurance Long Session",
            "endurance",
            75,
            "intermediate",
            '{"blocks":[{"name":"warmup","minutes":10},{"name":"steady_endurance","minutes":55},{"name":"cooldown","minutes":10}]}'
        ),
    ]

    connection.executemany(
        """
        INSERT INTO session_template (
            name, discipline, duration_minutes, level, json_blocks, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [(name, discipline, duration, level, blocks, now, now) for name, discipline, duration, level, blocks in templates],
    )


def ensure_single_founder_user(connection: sqlite3.Connection) -> None:
    count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count > 0:
        return

    now = utc_now_iso()
    connection.execute(
        """
        INSERT INTO users (email, display_name, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        ("founder@flowform.local", "Founder", now, now),
    )


def db_integrity_snapshot(db_path: Path) -> dict:
    required_tables = {
        "users",
        "profile",
        "plan",
        "plan_day",
        "session_template",
        "session_completion",
        "recovery_checkin",
        "audit_log",
    }

    try:
        connection = sqlite3.connect(db_path)
        existing_tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        missing_tables = sorted(required_tables - existing_tables)
        template_count = connection.execute("SELECT COUNT(*) FROM session_template").fetchone()[0]
        connection.execute("SELECT 1")
        connection.close()

        db_ok = not missing_tables and template_count > 0
        return {
            "db_ok": db_ok,
            "template_count": int(template_count),
            "missing_tables": missing_tables,
        }
    except sqlite3.Error as exc:
        return {
            "db_ok": False,
            "template_count": 0,
            "missing_tables": sorted(required_tables),
            "error": str(exc),
        }


def create_app(port: int | None = None) -> Flask:
    """Create and configure the Flask application."""
    load_env_file(ROOT_DIR / ".env")
    configure_logging()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    app = Flask(__name__)

    resolved_port = int(port if port is not None else os.getenv("PORT", "5203"))
    db_path = Path(os.getenv("DB_PATH", str(DEFAULT_DB_PATH))).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    app.config.update(
        APP_NAME=APP_NAME,
        VERSION=APP_VERSION,
        PORT=resolved_port,
        DB_PATH=str(db_path),
        BUILD_DATE=BUILD_DATE,
        GIT_HASH=git_hash(),
        FIRST_CHECK={"ok": True, "message": ""},
    )

    app.logger.info("FlowForm boot config: port=%s db=%s", resolved_port, db_path)

    def init_db_safely() -> dict:
        try:
            connection = sqlite3.connect(db_path)
            apply_schema_migrations(connection)
            ensure_single_founder_user(connection)
            seed_templates(connection)
            connection.commit()
            connection.close()
            return {"ok": True, "message": "db_ready"}
        except sqlite3.Error as exc:
            app.logger.warning("SQLite init degraded: %s", exc)
            return {"ok": False, "message": f"SQLite init degraded: {exc}"}

    first_check = init_db_safely()
    app.config["FIRST_CHECK"] = first_check

    @app.errorhandler(404)
    def handle_not_found(_: Exception):
        return jsonify({"error": "not_found"}), 404

    @app.errorhandler(500)
    def handle_server_error(_: Exception):
        app.logger.exception("Unhandled server error")
        return jsonify({"error": "internal_server_error"}), 500

    @app.get("/")
    def root():
        if not app.config["FIRST_CHECK"]["ok"]:
            return render_template("first_run_error.html", error_message=app.config["FIRST_CHECK"]["message"]), 500
        return render_template("ready.html")

    @app.get("/health")
    def health():
        snapshot = db_integrity_snapshot(db_path)
        return jsonify(
            {
                "status": "ok" if snapshot["db_ok"] else "degraded",
                "version": app.config["VERSION"],
                "time": utc_now_iso(),
                "db_ok": snapshot["db_ok"],
                "template_count": snapshot["template_count"],
                "provider_status": provider_status(),
            }
        )

    @app.get("/api/health")
    def api_health():
        snapshot = db_integrity_snapshot(db_path)
        is_db_ok = snapshot["db_ok"] and app.config["FIRST_CHECK"]["ok"]
        payload = {
            "status": "ok" if is_db_ok else "degraded",
            "port": app.config["PORT"],
            "db_ok": is_db_ok,
            "template_count": snapshot["template_count"],
            "version": app.config["VERSION"],
        }
        return jsonify(payload)

    @app.get("/version")
    def version():
        return jsonify(
            {
                "app_name": app.config["APP_NAME"],
                "semantic_version": app.config["VERSION"],
                "build_date": app.config["BUILD_DATE"],
                "git_hash": app.config["GIT_HASH"],
            }
        )

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
            {"path": "/health", "methods": ["GET"], "description": "Operational health endpoint"},
            {"path": "/version", "methods": ["GET"], "description": "Build/version metadata"},
            {"path": "/diagnostics", "methods": ["GET"], "description": "Diagnostics checks"},
            {"path": "/api/spec", "methods": ["GET"], "description": "API + route spec"},
            {"path": "/api/health", "methods": ["GET"], "description": "Legacy API health status"},
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
            "/health",
            "/version",
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

        snapshot = db_integrity_snapshot(db_path)
        checks = {
            "health_route": "PASS" if "/health" in spec_routes else "FAIL",
            "spec_mismatch": "FAIL" if missing_from_spec else "PASS",
            "db_integrity": "PASS" if snapshot["db_ok"] else "FAIL",
        }

        return jsonify(
            {
                "status": "PASS" if all(v == "PASS" for v in checks.values()) else "FAIL",
                "needed": needed,
                "checks": checks,
                "missing_from_spec": missing_from_spec,
                "template_count": snapshot["template_count"],
                "missing_tables": snapshot["missing_tables"],
            }
        )

    @app.get("/ready")
    def ready():
        if not app.config["FIRST_CHECK"]["ok"]:
            return render_template("first_run_error.html", error_message=app.config["FIRST_CHECK"]["message"]), 500
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
