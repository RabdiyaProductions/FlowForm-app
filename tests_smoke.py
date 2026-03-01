from app_server import create_app


def test_ready_and_health():
    app = create_app(port=5410)
    client = app.test_client()

    health = client.get('/api/health')
    assert health.status_code == 200
    payload = health.get_json()
    assert payload['status'] in {'ok', 'degraded'}
    assert payload['port'] == 5410
    assert isinstance(payload['db_ok'], bool)
    assert payload['version']

    ready = client.get('/ready')
    assert ready.status_code == 200
    assert b'/api/health' in ready.data


def test_cli_port_overrides_env_port(monkeypatch):
    monkeypatch.setenv('PORT', '5488')
    app = create_app(port=5444)
    client = app.test_client()

    payload = client.get('/api/health').get_json()
    assert payload['port'] == 5444


def test_plan_create_and_current_view(tmp_path, monkeypatch):
    monkeypatch.setenv('DB_PATH', str(tmp_path / 'plan.db'))
    app = create_app(port=5445)
    client = app.test_client()

    response = client.post(
        '/api/plan/create',
        json={
            'goal': 'hybrid',
            'days_per_week': 4,
            'minutes_per_session': 50,
            'disciplines': ['strength', 'cardio', 'mobility', 'recovery', 'conditioning'],
            'constraints': 'No jumping',
            'equipment': 'Dumbbells',
        },
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['ok'] is True
    assert payload['plan_id'] > 0

    current = client.get('/plan/current')
    assert current.status_code == 200
    body = current.data
    assert b'Current Plan' in body
    assert b'Week 1' in body
    assert b'Today' in body


def test_regenerate_next_week_preserves_completed_sessions(tmp_path, monkeypatch):
    import sqlite3

    monkeypatch.setenv('DB_PATH', str(tmp_path / 'regen.db'))
    app = create_app(port=5446)
    client = app.test_client()

    response = client.post(
        '/api/plan/create',
        json={
            'goal': 'hybrid',
            'days_per_week': 3,
            'minutes_per_session': 45,
            'disciplines': ['strength', 'cardio', 'mobility', 'recovery', 'conditioning'],
        },
    )
    assert response.status_code == 200

    db_path = app.config['DB_PATH']
    con = sqlite3.connect(db_path)
    plan_id = con.execute("SELECT id FROM plan ORDER BY id DESC LIMIT 1").fetchone()[0]

    week2_day = con.execute(
        "SELECT id FROM plan_day WHERE plan_id = ? AND week = 2 ORDER BY day_index LIMIT 1",
        (plan_id,),
    ).fetchone()[0]
    now = '2026-01-01T00:00:00+00:00'
    con.execute(
        """
        INSERT INTO session_completion (plan_day_id, completed_at, rpe, notes, minutes_done, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (week2_day, now, 7, 'done', 45, now, now),
    )
    con.commit()
    con.close()

    regen = client.post('/api/plan/regenerate-next-week', json={})
    assert regen.status_code == 200
    assert regen.get_json()['ok'] is True

    con = sqlite3.connect(db_path)
    completion_count = con.execute(
        "SELECT COUNT(*) FROM session_completion WHERE plan_day_id = ?",
        (week2_day,),
    ).fetchone()[0]
    plan_day_exists = con.execute(
        "SELECT COUNT(*) FROM plan_day WHERE id = ?",
        (week2_day,),
    ).fetchone()[0]
    con.close()

    assert completion_count == 1
    assert plan_day_exists == 1
