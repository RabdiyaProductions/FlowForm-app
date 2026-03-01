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


def test_diagnostics_endpoints():
    app = create_app(port=5411)
    client = app.test_client()

    html = client.get('/diagnostics')
    assert html.status_code == 200
    assert b'Diagnostics' in html.data

    api = client.get('/api/diagnostics')
    assert api.status_code == 200
    payload = api.get_json()
    assert 'status' in payload
    assert 'checks' in payload


def test_session_start_finish_and_summary(tmp_path, monkeypatch):
    monkeypatch.setenv('DB_PATH', str(tmp_path / 'session.db'))
    app = create_app(port=5412)
    client = app.test_client()

    create = client.post('/api/plan/create', json={
        'goal': 'hybrid',
        'days_per_week': 3,
        'minutes_per_session': 45,
        'disciplines': ['strength', 'cardio', 'mobility', 'recovery', 'conditioning'],
    })
    assert create.status_code == 200

    current_before = client.get('/plan/current')
    assert current_before.status_code == 200
    assert b'/session/start/' in current_before.data

    import sqlite3
    con = sqlite3.connect(app.config['DB_PATH'])
    plan_day_id = con.execute('SELECT id FROM plan_day ORDER BY id LIMIT 1').fetchone()[0]
    con.close()

    start = client.get(f'/session/start/{plan_day_id}')
    assert start.status_code == 200
    assert b'Start' in start.data
    assert b'Finish' in start.data

    finish = client.post('/api/session/finish', json={
        'plan_day_id': plan_day_id,
        'rpe': 8,
        'notes': 'solid work',
        'minutes_done': 44,
    })
    assert finish.status_code == 200
    payload = finish.get_json()
    assert payload['ok'] is True
    completion_id = payload['completion_id']

    summary = client.get(f'/session/summary/{completion_id}')
    assert summary.status_code == 200
    assert b'Session Summary' in summary.data
    assert b'solid work' in summary.data

    current_after = client.get('/plan/current')
    assert current_after.status_code == 200
    assert b'Completed' in current_after.data


def test_recovery_checkin_persists_and_influences_plan(tmp_path, monkeypatch):
    monkeypatch.setenv('DB_PATH', str(tmp_path / 'recovery.db'))
    app = create_app(port=5413)
    client = app.test_client()

    create = client.post('/api/plan/create', json={
        'goal': 'hybrid',
        'days_per_week': 3,
        'minutes_per_session': 45,
        'disciplines': ['strength', 'cardio', 'mobility', 'recovery', 'conditioning'],
    })
    assert create.status_code == 200

    checkin = client.post('/api/recovery/checkin', json={
        'date': '2026-03-01',
        'sleep_hours': 4.5,
        'stress_1_10': 9,
        'soreness_1_10': 8,
        'mood_1_10': 3,
        'notes': 'rough day',
    })
    assert checkin.status_code == 200
    out = checkin.get_json()
    assert out['ok'] is True
    assert out['readiness_label'] == 'low'

    recovery = client.get('/recovery')
    assert recovery.status_code == 200
    assert b'Daily Recovery Check-in' in recovery.data
    assert b'not medical advice' in recovery.data

    plan = client.get('/plan/current')
    assert plan.status_code == 200
    assert b'Readiness:' in plan.data
    assert b'Suggestion:' in plan.data
