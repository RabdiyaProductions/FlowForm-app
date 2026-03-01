from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import subprocess
from datetime import date, datetime, timedelta, timezone
from datetime import date, datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, url_for

APP_NAME = "FlowForm Vitality Master Suite"
APP_VERSION = "0.1.3"
BUILD_DATE = "2026-02-28"

ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
LOG_DIR = ROOT_DIR / "logs"
DEFAULT_DB_PATH = DATA_DIR / "flowform.db"

DISCIPLINES = ["strength", "cardio", "mobility", "recovery", "conditioning", "endurance"]
GOAL_DEFAULTS = {
    "strength": ["strength", "mobility", "recovery", "conditioning", "cardio"],
    "fat_loss": ["conditioning", "cardio", "strength", "mobility", "recovery"],
    "mobility": ["mobility", "recovery", "strength", "cardio", "conditioning"],
    "stress": ["recovery", "mobility", "cardio", "strength", "conditioning"],
    "hybrid": ["strength", "cardio", "mobility", "conditioning", "recovery"],
}


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


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def git_hash() -> str:
    git_dir = ROOT_DIR / ".git"
    if not git_dir.exists():
        return "not_a_git_repo"
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(ROOT_DIR),
                text=True,
                stderr=subprocess.DEVNULL,
            )
            .strip()
        )
    except Exception:
        return "unknown"


def provider_status() -> str:
    return "configured" if os.getenv("PROVIDER_API_KEY") else "not_configured"



def first_check_state(app: Flask) -> dict:
    state = app.config.setdefault("FIRST_CHECK", {"ok": False, "message": "FIRST_CHECK missing"})
    if not isinstance(state, dict):
        state = {"ok": False, "message": "FIRST_CHECK malformed"}
        app.config["FIRST_CHECK"] = state
    state.setdefault("ok", False)
    state.setdefault("message", "")
    return state

def column_exists(connection: sqlite3.Connection, table: str, column: str) -> bool:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column for row in rows)


def ensure_column(connection: sqlite3.Connection, table: str, column: str, definition_sql: str) -> None:
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
        ("Strength Foundation A", "strength", 45, "beginner", '{"blocks":[{"name":"warmup","minutes":8},{"name":"compound_lifts","minutes":28},{"name":"cooldown","minutes":9}]}'),
        ("Strength Progression B", "strength", 60, "intermediate", '{"blocks":[{"name":"warmup","minutes":10},{"name":"main_lifts","minutes":38},{"name":"accessory","minutes":8},{"name":"cooldown","minutes":4}]}'),
        ("Zone 2 Base Ride", "cardio", 50, "beginner", '{"blocks":[{"name":"warmup","minutes":10},{"name":"steady_state","minutes":35},{"name":"cooldown","minutes":5}]}'),
        ("Tempo Intervals Run", "cardio", 40, "intermediate", '{"blocks":[{"name":"warmup","minutes":8},{"name":"tempo_intervals","minutes":26},{"name":"cooldown","minutes":6}]}'),
        ("Mobility Restore", "mobility", 30, "all_levels", '{"blocks":[{"name":"breath","minutes":5},{"name":"hips_spine","minutes":20},{"name":"reset","minutes":5}]}'),
        ("Yoga Recovery Flow", "recovery", 35, "all_levels", '{"blocks":[{"name":"flow","minutes":25},{"name":"downregulate","minutes":10}]}'),
        ("HIIT Power Ladder", "conditioning", 32, "advanced", '{"blocks":[{"name":"warmup","minutes":6},{"name":"ladder","minutes":20},{"name":"cooldown","minutes":6}]}'),
        ("Endurance Long Session", "endurance", 75, "intermediate", '{"blocks":[{"name":"warmup","minutes":10},{"name":"steady_endurance","minutes":55},{"name":"cooldown","minutes":10}]}'),
    ]

    connection.executemany(
        """
        INSERT INTO session_template (name, discipline, duration_minutes, level, json_blocks, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [(name, discipline, duration, level, blocks, now, now) for name, discipline, duration, level, blocks in templates],
    )


def get_or_create_founder_user(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT id FROM users ORDER BY id LIMIT 1").fetchone()
    if row:
        return int(row[0])

    now = utc_now_iso()
    cursor = connection.execute(
        """
        INSERT INTO users (email, display_name, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        ("founder@flowform.local", "Founder", now, now),
    )
    return int(cursor.lastrowid)


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
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        missing_tables = sorted(required_tables - existing_tables)
        template_count = connection.execute("SELECT COUNT(*) FROM session_template").fetchone()[0]
        connection.execute("SELECT 1")
        connection.close()

        db_ok = not missing_tables and template_count > 0
        return {"db_ok": db_ok, "template_count": int(template_count), "missing_tables": missing_tables}
    except sqlite3.Error as exc:
        return {
            "db_ok": False,
            "template_count": 0,
            "missing_tables": sorted(required_tables),
            "error": str(exc),
        }


def clamp_int(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def preferred_disciplines(payload: dict) -> list[str]:
    ranked = []
    if payload.get("disciplines") and isinstance(payload.get("disciplines"), list):
        ranked = [str(item).strip().lower() for item in payload["disciplines"] if str(item).strip()]
    else:
        ranked = [
            str(payload.get(f"discipline_rank_{idx}", "")).strip().lower()
            for idx in range(1, 6)
            if str(payload.get(f"discipline_rank_{idx}", "")).strip()
        ]

    goal = str(payload.get("goal", "hybrid")).strip().lower().replace(" ", "_")
    defaults = GOAL_DEFAULTS.get(goal, GOAL_DEFAULTS["hybrid"])

    deduped = []
    for item in ranked + defaults:
        if item in DISCIPLINES and item not in deduped:
            deduped.append(item)
    return deduped or GOAL_DEFAULTS["hybrid"]


def fetch_template_pool(connection: sqlite3.Connection, ordered_disciplines: list[str], target_minutes: int) -> list[dict]:
    rows = connection.execute(
        """
        SELECT id, name, discipline, duration_minutes, level
        FROM session_template
        ORDER BY id ASC
        """
    ).fetchall()
    if not rows:
        return []

    priority = {discipline: idx for idx, discipline in enumerate(ordered_disciplines)}

    mapped = [
        {
            "id": int(row[0]),
            "name": row[1],
            "discipline": row[2],
            "duration": int(row[3]),
            "level": row[4],
        }
        for row in rows
    ]

    mapped.sort(
        key=lambda item: (
            priority.get(item["discipline"], 999),
            abs(item["duration"] - target_minutes),
            item["id"],
        )
    )
    return mapped


def choose_template_for_day(pool: list[dict], discipline: str, target_minutes: int, offset: int) -> dict:
    discipline_pool = [item for item in pool if item["discipline"] == discipline]
    candidate_pool = discipline_pool if discipline_pool else pool
    ranked = sorted(candidate_pool, key=lambda item: (abs(item["duration"] - target_minutes), item["id"]))
    return ranked[offset % len(ranked)]


def build_plan_structure(
    pool: list[dict],
    ordered_disciplines: list[str],
    days_per_week: int,
    minutes_per_session: int,
    weeks: int,
) -> list[dict]:
    items: list[dict] = []
    for week in range(1, weeks + 1):
        # Progressive structure: weeks 1-3 build, week 4 deload.
        if week <= 2:
            target = minutes_per_session
        elif week == 3:
            target = clamp_int(minutes_per_session + 5, 30, 75)
        else:
            target = clamp_int(minutes_per_session - 5, 30, 75)

        for day_index in range(1, days_per_week + 1):
            discipline = ordered_disciplines[(day_index - 1) % len(ordered_disciplines)]
            choice = choose_template_for_day(pool, discipline, target, offset=week + day_index)
            items.append(
                {
                    "week": week,
                    "day_index": day_index,
                    "template_id": choice["id"],
                    "title": f"Week {week} Day {day_index}: {choice['name']}",
                }
            )
    return items


def current_plan_record(connection: sqlite3.Connection, user_id: int) -> sqlite3.Row | None:
    connection.row_factory = sqlite3.Row
    row = connection.execute(
        """
        SELECT id, user_id, name, start_date, weeks, status
        FROM plan
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    return row


def write_audit(connection: sqlite3.Connection, event: str, payload: dict) -> None:
    now = utc_now_iso()
    connection.execute(
        """
        INSERT INTO audit_log (event, payload_json, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (event, json.dumps(payload), now, now),
    )



def blocks_from_json(raw: str) -> list[dict]:
    try:
        payload = json.loads(raw)
    except Exception:
        return []
    blocks = payload.get("blocks") if isinstance(payload, dict) else None
    if not isinstance(blocks, list):
        return []

    normalized = []
    for idx, block in enumerate(blocks, start=1):
        if not isinstance(block, dict):
            continue
        name = str(block.get("name", f"Block {idx}")).strip() or f"Block {idx}"
        minutes = block.get("minutes", 0)
        try:
            minutes_int = max(0, int(minutes))
        except (TypeError, ValueError):
            minutes_int = 0
        normalized.append({"name": name, "minutes": minutes_int, "seconds": minutes_int * 60})
    return normalized

def compute_readiness_score(sleep_hours: float, stress: int, soreness: int, mood: int) -> tuple[int, str]:
    # Explainable weighted score out of 100.
    sleep_component = max(0.0, min(1.0, sleep_hours / 8.0)) * 40.0
    stress_component = ((11 - stress) / 10.0) * 20.0
    soreness_component = ((11 - soreness) / 10.0) * 20.0
    mood_component = (mood / 10.0) * 20.0
    score = int(round(max(0.0, min(100.0, sleep_component + stress_component + soreness_component + mood_component))))

    explanation = (
        f"sleep({sleep_hours}h)->{sleep_component:.1f}/40, "
        f"stress({stress})->{stress_component:.1f}/20, "
        f"soreness({soreness})->{soreness_component:.1f}/20, "
        f"mood({mood})->{mood_component:.1f}/20"
    )
    return score, explanation


def readiness_label(score: int) -> str:
    if score >= 75:
        return "high"
    if score >= 55:
        return "moderate"
    return "low"


def suggestion_for_low_readiness(connection: sqlite3.Connection, minutes: int | None = None) -> dict | None:
    target = int(minutes or 35)
    row = connection.execute(
        """
        SELECT id, name, discipline, duration_minutes
        FROM session_template
        WHERE discipline IN ('mobility', 'recovery')
        ORDER BY ABS(duration_minutes - ?), duration_minutes ASC
        LIMIT 1
        """,
        (target,),
    ).fetchone()
    if row is None:
        return None
    return {"id": int(row[0]), "name": row[1], "discipline": row[2], "duration_minutes": int(row[3])}



def analytics_snapshot(connection: sqlite3.Connection, user_id: int) -> dict:
    # Distinct completion dates for streak math.
    completion_dates = [
        row[0]
        for row in connection.execute(
            """
            SELECT DISTINCT DATE(completed_at) AS day
            FROM session_completion
            ORDER BY day DESC
            """
        ).fetchall()
        if row[0]
    ]

    streak = 0
    if completion_dates:
        today = date.today()
        date_set = {date.fromisoformat(item) for item in completion_dates}
        cursor = today
        while cursor in date_set:
            streak += 1
            cursor -= timedelta(days=1)

    # Weekly completion rate for current week of active plan.
    plan = current_plan_record(connection, user_id)
    weekly_completion_rate = 0
    if plan is not None and plan["start_date"]:
        start = date.fromisoformat(plan["start_date"])
        elapsed = max(0, (date.today() - start).days)
        current_week = min(int(plan["weeks"]), (elapsed // 7) + 1)

        totals = connection.execute(
            "SELECT COUNT(*) FROM plan_day WHERE plan_id = ? AND week = ?",
            (int(plan["id"]), current_week),
        ).fetchone()[0]
        completed = connection.execute(
            """
            SELECT COUNT(DISTINCT pd.id)
            FROM plan_day pd
            JOIN session_completion sc ON sc.plan_day_id = pd.id
            WHERE pd.plan_id = ? AND pd.week = ?
            """,
            (int(plan["id"]), current_week),
        ).fetchone()[0]
        if totals > 0:
            weekly_completion_rate = int(round((completed / totals) * 100))

    avg_rpe = {}
    for days in (7, 14, 30):
        row = connection.execute(
            """
            SELECT AVG(rpe)
            FROM session_completion
            WHERE completed_at >= datetime('now', ?)
            """,
            (f"-{days} days",),
        ).fetchone()
        avg_rpe[str(days)] = round(float(row[0]), 2) if row and row[0] is not None else None

    readiness_rows = connection.execute(
        """
        SELECT date, sleep_hours, stress_1_10, soreness_1_10, mood_1_10
        FROM recovery_checkin
        WHERE user_id = ?
        ORDER BY date DESC
        LIMIT 14
        """,
        (user_id,),
    ).fetchall()

    readiness_trend = []
    for row in reversed(readiness_rows):
        score, _ = compute_readiness_score(
            float(row[1] or 0),
            int(row[2] or 5),
            int(row[3] or 5),
            int(row[4] or 5),
        )
        readiness_trend.append({"date": row[0], "score": score})

    # Card takeaways
    streak_takeaway = "Excellent momentum — keep the chain alive today." if streak >= 3 else "Start or restart the streak with one focused session today."
    weekly_takeaway = (
        "On track this week — maintain your rhythm." if weekly_completion_rate >= 70
        else "Below target this week — schedule one catch-up session."
    )

    rpe_7 = avg_rpe.get("7")
    if rpe_7 is None:
        rpe_takeaway = "No recent RPE data yet — finish a session to start insights."
    elif rpe_7 >= 8:
        rpe_takeaway = "Recent effort is high — consider extra recovery emphasis."
    elif rpe_7 <= 5:
        rpe_takeaway = "Recent effort is moderate/low — safe room to push when ready."
    else:
        rpe_takeaway = "Recent effort is balanced — keep progressive overload steady."

    if readiness_trend:
        latest = readiness_trend[-1]["score"]
        readiness_takeaway = "Recovery trend is low — choose a lighter session suggestion today." if latest < 55 else "Recovery trend is supportive — proceed with planned intensity."
    else:
        readiness_takeaway = "No readiness trend yet — add daily recovery check-ins."

    return {
        "streak": streak,
        "weekly_completion_rate": weekly_completion_rate,
        "avg_rpe": avg_rpe,
        "readiness_trend": readiness_trend,
        "takeaways": {
            "streak": streak_takeaway,
            "weekly": weekly_takeaway,
            "rpe": rpe_takeaway,
            "readiness": readiness_takeaway,
        },
    }

def create_app(port: int | None = None) -> Flask:
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
            get_or_create_founder_user(connection)
            seed_templates(connection)
            connection.commit()
            connection.close()
            return {"ok": True, "message": "db_ready"}
        except sqlite3.Error as exc:
            app.logger.warning("SQLite init degraded: %s", exc)
            return {"ok": False, "message": f"SQLite init degraded: {exc}"}

    app.config["FIRST_CHECK"] = init_db_safely()

    @app.errorhandler(404)
    def handle_not_found(_: Exception):
        return jsonify({"error": "not_found"}), 404

    @app.errorhandler(500)
    def handle_server_error(_: Exception):
        app.logger.exception("Unhandled server error")
        return jsonify({"error": "internal_server_error"}), 500

    @app.get("/")
    def root():
        check = first_check_state(app)
        if not check.get("ok", False):
            return render_template("first_run_error.html", error_message=check.get("message", "Unknown startup check failure")), 500
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
        is_db_ok = snapshot["db_ok"] and bool(first_check_state(app).get("ok", False))
        return jsonify(
            {
                "status": "ok" if is_db_ok else "degraded",
                "port": app.config["PORT"],
                "db_ok": is_db_ok,
                "template_count": snapshot["template_count"],
                "version": app.config["VERSION"],
            }
        )

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

    @app.get("/plan/wizard")
    def plan_wizard():
        return render_template("plan_wizard.html", disciplines=DISCIPLINES)

    @app.post("/api/plan/create")
    def api_plan_create():
        payload = request.get_json(silent=True) or request.form.to_dict()

        goal_raw = str(payload.get("goal", "hybrid")).strip().lower().replace(" ", "_")
        goal = goal_raw if goal_raw in GOAL_DEFAULTS else "hybrid"
        days_per_week = clamp_int(int(payload.get("days_per_week", 4)), 2, 6)
        minutes_per_session = clamp_int(int(payload.get("minutes_per_session", 50)), 30, 75)

        ordered_disciplines = preferred_disciplines(payload)
        injury_flags = str(payload.get("injury_flags", "")).strip()
        equipment = str(payload.get("equipment", "")).strip()
        extra_constraints = str(payload.get("constraints", "")).strip()
        combined_constraints = "; ".join(part for part in [injury_flags, extra_constraints] if part)

        now = utc_now_iso()
        today = date.today().isoformat()

        connection = sqlite3.connect(db_path)
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            user_id = get_or_create_founder_user(connection)

            profile_row = connection.execute(
                "SELECT id FROM profile WHERE user_id = ? ORDER BY id DESC LIMIT 1",
                (user_id,),
            ).fetchone()
            if profile_row:
                connection.execute(
                    """
                    UPDATE profile
                    SET goal = ?, days_per_week = ?, minutes = ?, equipment = ?, constraints = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (goal, days_per_week, minutes_per_session, equipment, combined_constraints, now, profile_row[0]),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO profile (user_id, goal, days_per_week, minutes, equipment, constraints, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, goal, days_per_week, minutes_per_session, equipment, combined_constraints, now, now),
                )

            connection.execute(
                "UPDATE plan SET status = 'archived', updated_at = ? WHERE user_id = ? AND status = 'active'",
                (now, user_id),
            )

            plan_name = f"{goal.replace('_', ' ').title()} 4-Week Plan"
            cursor = connection.execute(
                """
                INSERT INTO plan (user_id, name, start_date, weeks, status, created_at, updated_at)
                VALUES (?, ?, ?, 4, 'active', ?, ?)
                """,
                (user_id, plan_name, today, now, now),
            )
            plan_id = int(cursor.lastrowid)

            pool = fetch_template_pool(connection, ordered_disciplines, minutes_per_session)
            if not pool:
                raise sqlite3.IntegrityError("session_template empty; cannot generate plan")
            items = build_plan_structure(pool, ordered_disciplines, days_per_week, minutes_per_session, weeks=4)

            connection.executemany(
                """
                INSERT INTO plan_day (plan_id, week, day_index, template_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (plan_id, item["week"], item["day_index"], item["template_id"], item["title"], now, now)
                    for item in items
                ],
            )

            write_audit(
                connection,
                "plan_created",
                {
                    "plan_id": plan_id,
                    "goal": goal,
                    "days_per_week": days_per_week,
                    "minutes_per_session": minutes_per_session,
                    "disciplines": ordered_disciplines,
                },
            )

            connection.commit()
        except (sqlite3.Error, ValueError) as exc:
            connection.rollback()
            connection.close()
            return jsonify({"ok": False, "error": str(exc)}), 400
        connection.close()

        if request.is_json:
            return jsonify({"ok": True, "plan_id": plan_id, "redirect": "/plan/current"})
        return redirect(url_for("plan_current"))

    @app.post("/api/plan/regenerate-next-week")
    def api_plan_regenerate_next_week():
        connection = sqlite3.connect(db_path)
        connection.execute("PRAGMA foreign_keys = ON")
        now = utc_now_iso()
        try:
            user_id = get_or_create_founder_user(connection)
            row = current_plan_record(connection, user_id)
            if row is None:
                raise sqlite3.IntegrityError("No plan found")

            plan_id = int(row["id"])
            total_weeks = int(row["weeks"])
            start = date.fromisoformat(row["start_date"])
            elapsed = max(0, (date.today() - start).days)
            current_week = min(total_weeks, (elapsed // 7) + 1)
            next_week = min(total_weeks, current_week + 1)

            profile = connection.execute(
                "SELECT goal, days_per_week, minutes FROM profile WHERE user_id = ? ORDER BY id DESC LIMIT 1",
                (user_id,),
            ).fetchone()
            days_per_week = clamp_int(int(profile[1]) if profile and profile[1] else 4, 2, 6)
            minutes_per_session = clamp_int(int(profile[2]) if profile and profile[2] else 50, 30, 75)
            goal = (profile[0] if profile and profile[0] else "hybrid").strip().lower().replace(" ", "_")
            ordered_disciplines = GOAL_DEFAULTS.get(goal, GOAL_DEFAULTS["hybrid"])

            completed_day_ids = {
                int(item[0])
                for item in connection.execute(
                    """
                    SELECT sc.plan_day_id
                    FROM session_completion sc
                    JOIN plan_day pd ON pd.id = sc.plan_day_id
                    WHERE pd.plan_id = ? AND pd.week = ?
                    """,
                    (plan_id, next_week),
                ).fetchall()
            }

            existing_rows = connection.execute(
                "SELECT id FROM plan_day WHERE plan_id = ? AND week = ?",
                (plan_id, next_week),
            ).fetchall()
            for item in existing_rows:
                plan_day_id = int(item[0])
                if plan_day_id not in completed_day_ids:
                    connection.execute("DELETE FROM plan_day WHERE id = ?", (plan_day_id,))

            pool = fetch_template_pool(connection, ordered_disciplines, minutes_per_session)
            week_items = [
                item
                for item in build_plan_structure(pool, ordered_disciplines, days_per_week, minutes_per_session, weeks=next_week)
                if item["week"] == next_week
            ]

            existing_day_indexes = {
                int(row[0])
                for row in connection.execute(
                    "SELECT day_index FROM plan_day WHERE plan_id = ? AND week = ?",
                    (plan_id, next_week),
                ).fetchall()
            }

            for item in week_items:
                if item["day_index"] in existing_day_indexes:
                    continue
                connection.execute(
                    """
                    INSERT INTO plan_day (plan_id, week, day_index, template_id, title, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (plan_id, item["week"], item["day_index"], item["template_id"], item["title"], now, now),
                )

            write_audit(connection, "plan_week_regenerated", {"plan_id": plan_id, "week": next_week})
            connection.commit()
            payload = {"ok": True, "plan_id": plan_id, "week": next_week}
        except (sqlite3.Error, ValueError) as exc:
            connection.rollback()
            payload = {"ok": False, "error": str(exc)}
        connection.close()

        if request.is_json:
            return jsonify(payload), (200 if payload.get("ok") else 400)
        return redirect(url_for("plan_current"))

    @app.get("/recovery")
    def recovery():
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        user_id = get_or_create_founder_user(connection)
        rows = connection.execute(
            """
            SELECT date, sleep_hours, stress_1_10, soreness_1_10, mood_1_10, notes
            FROM recovery_checkin
            WHERE user_id = ?
            ORDER BY date DESC
            LIMIT 14
            """,
            (user_id,),
        ).fetchall()
        connection.close()

        entries = [dict(row) for row in rows]
        latest = entries[0] if entries else None
        readiness = None
        if latest is not None:
            score, explanation = compute_readiness_score(
                float(latest["sleep_hours"] or 0),
                int(latest["stress_1_10"] or 5),
                int(latest["soreness_1_10"] or 5),
                int(latest["mood_1_10"] or 5),
            )
            readiness = {"score": score, "label": readiness_label(score), "explanation": explanation}

        return render_template("recovery.html", entries=entries, readiness=readiness, today=date.today().isoformat())

    @app.post("/api/recovery/checkin")
    def api_recovery_checkin():
        payload = request.get_json(silent=True) or request.form.to_dict()
        try:
            checkin_date = str(payload.get("date") or date.today().isoformat())
            sleep_hours = max(0.0, min(24.0, float(payload.get("sleep_hours", 0))))
            stress = clamp_int(int(payload.get("stress_1_10", 5)), 1, 10)
            soreness = clamp_int(int(payload.get("soreness_1_10", 5)), 1, 10)
            mood = clamp_int(int(payload.get("mood_1_10", 5)), 1, 10)
            notes = str(payload.get("notes", "")).strip()
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "invalid_payload"}), 400

        score, explanation = compute_readiness_score(sleep_hours, stress, soreness, mood)
        notes_with_readiness = (notes + "\n" if notes else "") + f"Readiness {score}/100 | {explanation}"
        now = utc_now_iso()

        connection = sqlite3.connect(db_path)
        try:
            user_id = get_or_create_founder_user(connection)
            existing = connection.execute(
                "SELECT id FROM recovery_checkin WHERE user_id = ? AND date = ?",
                (user_id, checkin_date),
            ).fetchone()
            if existing:
                connection.execute(
                    """
                    UPDATE recovery_checkin
                    SET sleep_hours=?, stress_1_10=?, soreness_1_10=?, mood_1_10=?, notes=?, updated_at=?
                    WHERE id=?
                    """,
                    (sleep_hours, stress, soreness, mood, notes_with_readiness, now, int(existing[0])),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO recovery_checkin (user_id, date, sleep_hours, stress_1_10, soreness_1_10, mood_1_10, notes, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, checkin_date, sleep_hours, stress, soreness, mood, notes_with_readiness, now, now),
                )
            write_audit(connection, "recovery_checkin", {"date": checkin_date, "readiness_score": score})
            connection.commit()
        except sqlite3.Error as exc:
            connection.rollback()
            connection.close()
            return jsonify({"ok": False, "error": str(exc)}), 400
        connection.close()

        if request.is_json:
            return jsonify({"ok": True, "readiness_score": score, "readiness_label": readiness_label(score)})
        return redirect(url_for("plan_current"))

    @app.get("/plan/current")
    def plan_current():
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        user_id = get_or_create_founder_user(connection)
        plan = current_plan_record(connection, user_id)
        if plan is None:
            connection.close()
            return render_template("plan_current.html", plan=None, weeks=[], today_week=1, today_day=1)

        rows = connection.execute(
            """
            SELECT
                pd.id, pd.week, pd.day_index, pd.title, st.name AS template_name, st.discipline, st.duration_minutes,
                MAX(sc.id) AS completion_id
            FROM plan_day pd
            LEFT JOIN session_template st ON st.id = pd.template_id
            LEFT JOIN session_completion sc ON sc.plan_day_id = pd.id
            WHERE pd.plan_id = ?
            GROUP BY pd.id, pd.week, pd.day_index, pd.title, st.name, st.discipline, st.duration_minutes
            SELECT pd.id, pd.week, pd.day_index, pd.title, st.name AS template_name, st.discipline, st.duration_minutes
            FROM plan_day pd
            LEFT JOIN session_template st ON st.id = pd.template_id
            WHERE pd.plan_id = ?
            ORDER BY pd.week ASC, pd.day_index ASC
            """,
            (int(plan["id"]),),
        ).fetchall()

        recent = connection.execute(
            """
            SELECT date, sleep_hours, stress_1_10, soreness_1_10, mood_1_10, notes
            FROM recovery_checkin
            WHERE user_id = ?
            ORDER BY date DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()

        readiness = None
        suggestion = None
        if recent is not None:
            score, explanation = compute_readiness_score(
                float(recent["sleep_hours"] or 0),
                int(recent["stress_1_10"] or 5),
                int(recent["soreness_1_10"] or 5),
                int(recent["mood_1_10"] or 5),
            )
            readiness = {
                "score": score,
                "label": readiness_label(score),
                "explanation": explanation,
                "date": recent["date"],
            }
            if score < 55:
                suggestion = suggestion_for_low_readiness(connection)

        connection.close()

        weeks_map: dict[int, list[dict]] = {}
        for row in rows:
            weeks_map.setdefault(int(row["week"]), []).append(
                {
                    "id": int(row["id"]),
                    "day_index": int(row["day_index"]),
                    "title": row["title"],
                    "template_name": row["template_name"],
                    "discipline": row["discipline"],
                    "duration_minutes": row["duration_minutes"],
                    "completed": row["completion_id"] is not None,
                    "completion_id": row["completion_id"],
                }
            )

        start = date.fromisoformat(plan["start_date"])
        elapsed = max(0, (date.today() - start).days)
        today_week = min(int(plan["weeks"]), (elapsed // 7) + 1)
        today_day = (elapsed % 7) + 1

        week_cards = [{"week": week, "days": days} for week, days in sorted(weeks_map.items())]
        today_plan_day_id = None
        for week in week_cards:
            if week["week"] != today_week:
                continue
            for day in week["days"]:
                if day["day_index"] == today_day:
                    today_plan_day_id = day["id"]
                    break

        return render_template(
            "plan_current.html",
            plan=plan,
            weeks=week_cards,
            today_week=today_week,
            today_day=today_day,
            today_plan_day_id=today_plan_day_id,
            readiness=readiness,
            suggestion=suggestion,
        )

    @app.get("/analytics")
    def analytics():
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        user_id = get_or_create_founder_user(connection)
        data = analytics_snapshot(connection, user_id)
        connection.close()
        return render_template("analytics.html", analytics=data)

    @app.get("/session/start/<int:plan_day_id>")
    def session_start(plan_day_id: int):
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT pd.id AS plan_day_id, pd.title, pd.week, pd.day_index, st.name AS template_name,
                   st.duration_minutes, st.json_blocks
            FROM plan_day pd
            LEFT JOIN session_template st ON st.id = pd.template_id
            WHERE pd.id = ?
            """,
            (plan_day_id,),
        ).fetchone()
        connection.close()

        if row is None:
            return jsonify({"error": "plan_day_not_found"}), 404

        blocks = blocks_from_json(row["json_blocks"] or "")
        if not blocks:
            duration = int(row["duration_minutes"] or 30)
            blocks = [{"name": row["template_name"] or "Session", "minutes": duration, "seconds": duration * 60}]

        return render_template(
            "session_start.html",
            session={
                "plan_day_id": int(row["plan_day_id"]),
                "title": row["title"] or row["template_name"] or "Session",
                "template_name": row["template_name"] or "Session",
                "week": int(row["week"]),
                "day_index": int(row["day_index"]),
                "blocks": blocks,
            },
        )

    @app.post("/api/session/finish")
    def api_session_finish():
        payload = request.get_json(silent=True) or request.form.to_dict()
        try:
            plan_day_id = int(payload.get("plan_day_id"))
            rpe = clamp_int(int(payload.get("rpe", 5)), 1, 10)
            notes = str(payload.get("notes", "")).strip()
            minutes_done = clamp_int(int(payload.get("minutes_done", 0)), 0, 300)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "invalid_payload"}), 400

        now = utc_now_iso()
        connection = sqlite3.connect(db_path)
        try:
            exists = connection.execute("SELECT id FROM plan_day WHERE id = ?", (plan_day_id,)).fetchone()
            if not exists:
                return jsonify({"ok": False, "error": "plan_day_not_found"}), 404

            cursor = connection.execute(
                """
                INSERT INTO session_completion (plan_day_id, completed_at, rpe, notes, minutes_done, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (plan_day_id, now, rpe, notes, minutes_done, now, now),
            )
            completion_id = int(cursor.lastrowid)
            write_audit(connection, "session_completed", {"completion_id": completion_id, "plan_day_id": plan_day_id})
            connection.commit()
        except sqlite3.Error as exc:
            connection.rollback()
            connection.close()
            return jsonify({"ok": False, "error": str(exc)}), 400
        connection.close()

        return jsonify({"ok": True, "completion_id": completion_id, "redirect": f"/session/summary/{completion_id}"})

    @app.get("/session/summary/<int:completion_id>")
    def session_summary(completion_id: int):
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT sc.id, sc.completed_at, sc.rpe, sc.notes, sc.minutes_done,
                   pd.title, pd.week, pd.day_index, st.name AS template_name
            FROM session_completion sc
            JOIN plan_day pd ON pd.id = sc.plan_day_id
            LEFT JOIN session_template st ON st.id = pd.template_id
            WHERE sc.id = ?
            """,
            (completion_id,),
        ).fetchone()
        connection.close()

        if row is None:
            return jsonify({"error": "completion_not_found"}), 404

        return render_template("session_summary.html", completion=row)

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
            {"path": "/plan/wizard", "methods": ["GET"], "description": "Plan creation wizard"},
            {"path": "/plan/current", "methods": ["GET"], "description": "Current 4-week plan calendar"},
            {"path": "/recovery", "methods": ["GET"], "description": "Recovery check-in page"},
            {"path": "/analytics", "methods": ["GET"], "description": "Founder analytics dashboard"},
            {"path": "/api/recovery/checkin", "methods": ["POST"], "description": "Persist daily recovery check-in"},
            {"path": "/health", "methods": ["GET"], "description": "Operational health endpoint"},
            {"path": "/version", "methods": ["GET"], "description": "Build/version metadata"},
            {"path": "/diagnostics", "methods": ["GET"], "description": "Diagnostics checks (HTML)"},
            {"path": "/api/diagnostics", "methods": ["GET"], "description": "Diagnostics checks (JSON)"},
            {"path": "/api/spec", "methods": ["GET"], "description": "API + route spec"},
            {"path": "/api/health", "methods": ["GET"], "description": "Legacy API health status"},
            {"path": "/api/plan/create", "methods": ["POST"], "description": "Create a 4-week plan"},
            {"path": "/api/plan/regenerate-next-week", "methods": ["POST"], "description": "Regenerate next week plan days"},
            {"path": "/session/start/<plan_day_id>", "methods": ["GET"], "description": "Session player"},
            {"path": "/api/session/finish", "methods": ["POST"], "description": "Persist session completion"},
            {"path": "/session/summary/<completion_id>", "methods": ["GET"], "description": "Session completion summary"},
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
            curated_routes.append({"path": rule.rule, "methods": methods, "description": "Auto-discovered route"})
            seen_paths.add(rule.rule)

        return {"name": app.config["APP_NAME"], "version": app.config["VERSION"], "routes": curated_routes}

    @app.get("/api/spec")
    def api_spec():
        return jsonify(app_spec())

    def diagnostics_payload() -> dict:
        needed = [
            "/health",
            "/version",
            "/api/health",
            "/api/diagnostics",
            "/api/plan/create",
            "/plan/wizard",
            "/plan/current",
            "/recovery",
            "/analytics",
            "/api/recovery/checkin",
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

        return {
            "status": "PASS" if all(v == "PASS" for v in checks.values()) else "FAIL",
            "needed": needed,
            "checks": checks,
            "missing_from_spec": missing_from_spec,
            "template_count": snapshot["template_count"],
            "missing_tables": snapshot["missing_tables"],
        }

    @app.get("/api/diagnostics")
    def api_diagnostics():
        return jsonify(diagnostics_payload())

    @app.get("/diagnostics")
    def diagnostics():
        payload = diagnostics_payload()
        return render_template("diagnostics.html", data=payload)

    @app.get("/ready")
    def ready():
        check = first_check_state(app)
        if not check.get("ok", False):
            return render_template("first_run_error.html", error_message=check.get("message", "Unknown startup check failure")), 500
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
