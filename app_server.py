from __future__ import annotations

import argparse
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, jsonify, render_template, request

APP_NAME = "FlowForm Vitality Master Suite"
APP_VERSION = "0.2.1"

ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
DEFAULT_DB_PATH = DATA_DIR / "flowform.db"


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


@contextmanager
def get_db_connection(db_path: Path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def ensure_schema(db_path: Path) -> None:
    with get_db_connection(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                intensity INTEGER NOT NULL,
                duration_minutes INTEGER NOT NULL,
                training_load INTEGER NOT NULL DEFAULT 0,
                notes TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                heart_rate_avg INTEGER,
                calories INTEGER,
                perceived_exertion INTEGER,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );
            """
        )

        columns = {row["name"] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()}
        if "training_load" not in columns:
            conn.execute("ALTER TABLE sessions ADD COLUMN training_load INTEGER NOT NULL DEFAULT 0")

        user_row = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        if user_row is None:
            conn.execute(
                "INSERT INTO users(name, created_at) VALUES(?, ?)",
                ("Local FlowForm User", datetime.utcnow().isoformat()),
            )

        conn.execute(
            "UPDATE sessions SET training_load = duration_minutes * CAST(intensity AS INTEGER) WHERE training_load IS NULL OR training_load = 0"
        )


def get_weekly_minutes(conn: sqlite3.Connection) -> int:
    week_start = (datetime.utcnow() - timedelta(days=7)).isoformat()
    row = conn.execute(
        "SELECT COALESCE(SUM(duration_minutes), 0) AS total FROM sessions WHERE completed_at IS NOT NULL AND completed_at >= ?",
        (week_start,),
    ).fetchone()
    return int(row["total"] if row and row["total"] is not None else 0)


def get_weekly_load(conn: sqlite3.Connection) -> int:
    week_start = (datetime.utcnow() - timedelta(days=7)).isoformat()
    row = conn.execute(
        "SELECT COALESCE(SUM(training_load), 0) AS total FROM sessions WHERE completed_at IS NOT NULL AND completed_at >= ?",
        (week_start,),
    ).fetchone()
    return int(row["total"] if row and row["total"] is not None else 0)


def get_current_streak(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        "SELECT DISTINCT DATE(completed_at) AS day FROM sessions WHERE completed_at IS NOT NULL ORDER BY day DESC"
    ).fetchall()
    if not rows:
        return 0

    completed_days = {row["day"] for row in rows if row["day"]}
    streak = 0
    cursor_day = datetime.utcnow().date()

    if cursor_day.isoformat() not in completed_days:
        cursor_day = cursor_day - timedelta(days=1)

    while cursor_day.isoformat() in completed_days:
        streak += 1
        cursor_day = cursor_day - timedelta(days=1)

    return streak


def validate_session_form(form: dict[str, str]) -> tuple[dict[str, str], str | None]:
    title = form.get("title", "").strip()
    category = form.get("category", "").strip()
    notes = form.get("notes", "").strip()

    try:
        intensity = int(form.get("intensity", "0").strip())
    except ValueError:
        intensity = 0

    try:
        duration_minutes = int(form.get("duration_minutes", "0").strip())
    except ValueError:
        duration_minutes = 0

    cleaned = {
        "title": title,
        "category": category,
        "intensity": str(intensity),
        "duration_minutes": str(duration_minutes),
        "notes": notes,
    }

    if not title or not category:
        return cleaned, "Title and category are required."
    if duration_minutes <= 0:
        return cleaned, "Duration must be greater than 0 minutes."
    if intensity < 1 or intensity > 10:
        return cleaned, "Intensity must be between 1 and 10."

    return cleaned, None


def create_app(port: int | None = None) -> Flask:
    load_env_file(ROOT_DIR / ".env")
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    db_path = Path(os.getenv("DB_PATH", str(DEFAULT_DB_PATH))).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    ensure_schema(db_path)

    app = Flask(__name__)
    resolved_port = int(port if port is not None else os.getenv("PORT", "5400"))
    app.config.update(APP_NAME=APP_NAME, VERSION=APP_VERSION, PORT=resolved_port, DB_PATH=str(db_path))

    def db_ok() -> bool:
        try:
            with get_db_connection(db_path) as conn:
                conn.execute("SELECT 1")
            return True
        except sqlite3.Error:
            return False

    @app.errorhandler(404)
    def not_found(_: Exception):
        return jsonify({"error": "not_found"}), 404

    @app.errorhandler(500)
    def server_error(_: Exception):
        return jsonify({"error": "internal_server_error"}), 500

    @app.get("/")
    @app.get("/dashboard")
    def dashboard_page():
        with get_db_connection(db_path) as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM sessions").fetchone()
            total_sessions = int(row["c"] if row else 0)
            weekly_minutes = get_weekly_minutes(conn)
            weekly_load = get_weekly_load(conn)
            streak = get_current_streak(conn)
            last_five = conn.execute(
                "SELECT id, title, category, intensity, duration_minutes, training_load, completed_at FROM sessions ORDER BY created_at DESC LIMIT 5"
            ).fetchall()

        return render_template(
            "dashboard.html",
            total_sessions=total_sessions,
            weekly_minutes=weekly_minutes,
            weekly_load=weekly_load,
            streak=streak,
            last_sessions=last_five,
        )

    @app.get("/sessions")
    def sessions_list():
        with get_db_connection(db_path) as conn:
            rows = conn.execute(
                "SELECT id, title, category, intensity, duration_minutes, training_load, created_at, completed_at FROM sessions ORDER BY created_at DESC"
            ).fetchall()
        return render_template("sessions.html", sessions=rows)

    @app.get("/sessions/new")
    def sessions_new():
        return render_template("session_new.html", error=None, form_data={})

    @app.post("/sessions/create")
    def sessions_create():
        form_data, error = validate_session_form(request.form)
        if error:
            return render_template("session_new.html", error=error, form_data=form_data), 400

        intensity = int(form_data["intensity"])
        duration_minutes = int(form_data["duration_minutes"])
        training_load = duration_minutes * intensity

        with get_db_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO sessions(title, category, intensity, duration_minutes, training_load, notes, created_at, completed_at)
                VALUES(?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    form_data["title"],
                    form_data["category"],
                    intensity,
                    duration_minutes,
                    training_load,
                    form_data["notes"] if form_data["notes"] else None,
                    datetime.utcnow().isoformat(),
                ),
            )
        return sessions_list()

    @app.get("/sessions/<int:session_id>")
    def sessions_detail(session_id: int):
        with get_db_connection(db_path) as conn:
            session_row = conn.execute(
                "SELECT id, title, category, intensity, duration_minutes, training_load, notes, created_at, completed_at FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            if session_row is None:
                return jsonify({"error": "session_not_found"}), 404

            metric_row = conn.execute(
                "SELECT id, heart_rate_avg, calories, perceived_exertion FROM metrics WHERE session_id = ? ORDER BY id DESC LIMIT 1",
                (session_id,),
            ).fetchone()

        return render_template("session_detail.html", session=session_row, metric=metric_row, error=None)

    @app.post("/sessions/<int:session_id>/complete")
    def sessions_complete(session_id: int):
        def optional_int(value: str) -> int | None:
            value = value.strip()
            if value == "":
                return None
            try:
                return int(value)
            except ValueError:
                return None

        heart_rate_avg = optional_int(request.form.get("heart_rate_avg", ""))
        calories = optional_int(request.form.get("calories", ""))
        perceived_exertion = optional_int(request.form.get("perceived_exertion", ""))

        with get_db_connection(db_path) as conn:
            session_row = conn.execute("SELECT id FROM sessions WHERE id = ?", (session_id,)).fetchone()
            if session_row is None:
                return jsonify({"error": "session_not_found"}), 404

            conn.execute("UPDATE sessions SET completed_at = ? WHERE id = ?", (datetime.utcnow().isoformat(), session_id))
            conn.execute(
                "INSERT INTO metrics(session_id, heart_rate_avg, calories, perceived_exertion) VALUES(?, ?, ?, ?)",
                (session_id, heart_rate_avg, calories, perceived_exertion),
            )

        return sessions_detail(session_id)

    @app.get("/ready")
    def ready_page():
        return render_template("ready.html")

    @app.get("/api/health")
    def api_health():
        ok = db_ok()
        return jsonify({"status": "ok" if ok else "degraded", "port": app.config["PORT"], "db_ok": ok, "version": APP_VERSION})

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
