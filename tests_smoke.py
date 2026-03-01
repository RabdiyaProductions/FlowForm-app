
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
