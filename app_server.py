from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request

APP_NAME = "FlowForm Vitality Master Suite"
APP_VERSION = "0.2.0"

ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
LOG_DIR = ROOT_DIR / "logs"
DEFAULT_DB_PATH = DATA_DIR / "flowform.db"


SEED_SESSIONS = [
    {
        "title": "Mobility Reset 30",
        "duration_minutes": 30,
        "intensity": "Low",
        "steps": [
            {"name": "Breath primer", "seconds": 300},
            {"name": "Spine mobility flow", "seconds": 600},
            {"name": "Hip + ankle sequence", "seconds": 600},
            {"name": "Core control", "seconds": 600},
            {"name": "Down-regulation", "seconds": 300},
        ],
    },
    {
        "title": "Strength Foundation 40",
        "duration_minutes": 40,
        "intensity": "Moderate",
        "steps": [
            {"name": "Warm-up", "seconds": 480},
            {"name": "Lower-body strength", "seconds": 900},
            {"name": "Upper-body strength", "seconds": 900},
            {"name": "Finisher", "seconds": 600},
            {"name": "Cool down", "seconds": 420},
        ],
    },
    {
        "title": "Recovery Breath 20",
        "duration_minutes": 20,
        "intensity": "Very Low",
        "steps": [
            {"name": "Parasympathetic breathing", "seconds": 480},
            {"name": "Gentle mobility", "seconds": 420},
            {"name": "Supine recovery", "seconds": 300},
        ],
    },
]


def load_env_file(env_path: Path) -> None:
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
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    root_logger.setLevel(level)

    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    file_handler = RotatingFileHandler(LOG_DIR / "flowform.log", maxBytes=1_000_000, backupCount=3)
    file_handler.setFormatter(formatter)

    root_logger.addHandler(console)
    root_logger.addHandler(file_handler)


def get_db_connection(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def ensure_schema_and_seed(db_path: Path) -> None:
    conn = get_db_connection(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL,
                intensity TEXT NOT NULL,
                steps_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS session_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_id INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                completed INTEGER NOT NULL DEFAULT 0,
                duration_seconds INTEGER DEFAULT 0,
                notes TEXT DEFAULT '',
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                logged_at TEXT NOT NULL,
                weight_kg REAL,
                sleep_hours REAL,
                mood INTEGER,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            """
        )

        user = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        if user is None:
            conn.execute(
                "INSERT INTO users(name, created_at) VALUES(?, ?)",
                ("Local FlowForm User", datetime.utcnow().isoformat()),
            )
            user_id = int(conn.execute("SELECT id FROM users LIMIT 1").fetchone()["id"])
        else:
            user_id = int(user["id"])

        existing_sessions = conn.execute("SELECT COUNT(*) AS c FROM sessions").fetchone()["c"]
        if existing_sessions == 0:
            now = datetime.utcnow().isoformat()
            for item in SEED_SESSIONS:
                conn.execute(
                    """
                    INSERT INTO sessions(user_id, title, duration_minutes, intensity, steps_json, created_at, updated_at)
                    VALUES(?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        item["title"],
                        item["duration_minutes"],
                        item["intensity"],
                        json.dumps(item["steps"]),
                        now,
                        now,
                    ),
                )

        conn.commit()
    finally:
        conn.close()


def parse_session_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "duration_minutes": row["duration_minutes"],
        "intensity": row["intensity"],
        "steps": json.loads(row["steps_json"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def create_app(port: int | None = None) -> Flask:
    load_env_file(ROOT_DIR / ".env")
    configure_logging()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db_path = Path(os.getenv("DB_PATH", str(DEFAULT_DB_PATH))).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    ensure_schema_and_seed(db_path)

    app = Flask(__name__)
    resolved_port = int(port if port is not None else os.getenv("PORT", "5400"))
    app.config.update(APP_NAME=APP_NAME, VERSION=APP_VERSION, PORT=resolved_port, DB_PATH=str(db_path))
    app.logger.info("FlowForm initialized on port=%s db=%s", resolved_port, db_path)

    def db_ok() -> bool:
        try:
            conn = get_db_connection(db_path)
            conn.execute("SELECT 1")
            conn.close()
            return True
        except sqlite3.Error:
            app.logger.exception("DB health query failed")
            return False

    def local_user_id() -> int:
        conn = get_db_connection(db_path)
        try:
            row = conn.execute("SELECT id FROM users ORDER BY id ASC LIMIT 1").fetchone()
            if row is None:
                raise RuntimeError("No local user configured")
            return int(row["id"])
        finally:
            conn.close()

    @app.errorhandler(404)
    def not_found(_: Exception):
        return jsonify({"error": "not_found"}), 404

    @app.errorhandler(500)
    def server_error(error: Exception):
        app.logger.exception("Unhandled server error: %s", error)
        return jsonify({"error": "internal_server_error"}), 500

    @app.get("/")
    @app.get("/dashboard")
    def dashboard_page():
        conn = get_db_connection(db_path)
        try:
            sessions = conn.execute("SELECT COUNT(*) AS c FROM sessions").fetchone()["c"]
            runs = conn.execute("SELECT COUNT(*) AS c FROM session_runs WHERE completed = 1").fetchone()["c"]
            minutes = conn.execute(
                "SELECT COALESCE(SUM(duration_seconds),0) AS s FROM session_runs WHERE completed = 1"
            ).fetchone()["s"]
        finally:
            conn.close()

        return render_template(
            "dashboard.html",
            sessions_count=sessions,
            completed_runs=runs,
            total_minutes=int(minutes // 60),
        )

    @app.get("/sessions")
    def sessions_page():
        conn = get_db_connection(db_path)
        try:
            rows = conn.execute("SELECT * FROM sessions ORDER BY id DESC").fetchall()
            sessions = [parse_session_row(row) for row in rows]
        finally:
            conn.close()
        return render_template("sessions.html", sessions=sessions)

    @app.get("/player/<int:session_id>")
    def player_page(session_id: int):
        conn = get_db_connection(db_path)
        try:
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
            if row is None:
                return jsonify({"error": "session_not_found"}), 404
            session_data = parse_session_row(row)
        finally:
            conn.close()
        return render_template("player.html", session=session_data)

    @app.get("/progress")
    def progress_page():
        conn = get_db_connection(db_path)
        try:
            rows = conn.execute(
                """
                SELECT sr.id, s.title, sr.started_at, sr.finished_at, sr.duration_seconds, sr.notes
                FROM session_runs sr
                JOIN sessions s ON s.id = sr.session_id
                WHERE sr.completed = 1
                ORDER BY sr.id DESC
                """
            ).fetchall()
        finally:
            conn.close()
        return render_template("progress.html", runs=rows)

    @app.get("/settings")
    def settings_page():
        return render_template("settings.html", db_path=str(db_path), version=APP_VERSION)

    @app.get("/ready")
    def ready():
        return render_template("ready.html")

    @app.get("/api/health")
    def api_health():
        return jsonify(
            {
                "status": "ok" if db_ok() else "degraded",
                "port": app.config["PORT"],
                "db_ok": db_ok(),
                "version": app.config["VERSION"],
            }
        )

    @app.route("/api/sessions", methods=["GET", "POST"])
    def api_sessions():
        if request.method == "GET":
            conn = get_db_connection(db_path)
            try:
                rows = conn.execute("SELECT * FROM sessions ORDER BY id DESC").fetchall()
                return jsonify([parse_session_row(row) for row in rows])
            finally:
                conn.close()

        payload = request.get_json(silent=True) or {}
        title = str(payload.get("title", "")).strip()
        duration_minutes = int(payload.get("duration_minutes", 0))
        intensity = str(payload.get("intensity", "Moderate")).strip() or "Moderate"
        steps = payload.get("steps", [])

        if not title:
            return jsonify({"error": "title_required"}), 400
        if duration_minutes <= 0:
            return jsonify({"error": "duration_minutes_invalid"}), 400
        if not isinstance(steps, list) or not steps:
            return jsonify({"error": "steps_required"}), 400

        now = datetime.utcnow().isoformat()
        conn = get_db_connection(db_path)
        try:
            cursor = conn.execute(
                """
                INSERT INTO sessions(user_id, title, duration_minutes, intensity, steps_json, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (local_user_id(), title, duration_minutes, intensity, json.dumps(steps), now, now),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return jsonify(parse_session_row(row)), 201
        finally:
            conn.close()

    @app.route("/api/session_runs", methods=["GET", "POST"])
    def api_session_runs():
        if request.method == "GET":
            conn = get_db_connection(db_path)
            try:
                rows = conn.execute(
                    """
                    SELECT sr.id, sr.session_id, s.title, sr.started_at, sr.finished_at,
                           sr.completed, sr.duration_seconds, sr.notes
                    FROM session_runs sr
                    JOIN sessions s ON s.id = sr.session_id
                    ORDER BY sr.id DESC
                    """
                ).fetchall()
                result = [dict(row) for row in rows]
                return jsonify(result)
            finally:
                conn.close()

        payload = request.get_json(silent=True) or {}
        session_id = int(payload.get("session_id", 0))
        completed = 1 if bool(payload.get("completed", True)) else 0
        duration_seconds = int(payload.get("duration_seconds", 0))
        notes = str(payload.get("notes", "")).strip()

        if session_id <= 0:
            return jsonify({"error": "session_id_invalid"}), 400
        if duration_seconds < 0:
            return jsonify({"error": "duration_seconds_invalid"}), 400

        started_at = payload.get("started_at") or datetime.utcnow().isoformat()
        finished_at = payload.get("finished_at") or datetime.utcnow().isoformat()

        conn = get_db_connection(db_path)
        try:
            exists = conn.execute("SELECT id FROM sessions WHERE id = ?", (session_id,)).fetchone()
            if exists is None:
                return jsonify({"error": "session_not_found"}), 404

            cursor = conn.execute(
                """
                INSERT INTO session_runs(user_id, session_id, started_at, finished_at, completed, duration_seconds, notes)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (local_user_id(), session_id, started_at, finished_at, completed, duration_seconds, notes),
            )
            conn.commit()
            row = conn.execute(
                """
                SELECT sr.id, sr.session_id, s.title, sr.started_at, sr.finished_at,
                       sr.completed, sr.duration_seconds, sr.notes
                FROM session_runs sr
                JOIN sessions s ON s.id = sr.session_id
                WHERE sr.id = ?
                """,
                (cursor.lastrowid,),
            ).fetchone()
            return jsonify(dict(row)), 201
        finally:
            conn.close()

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
