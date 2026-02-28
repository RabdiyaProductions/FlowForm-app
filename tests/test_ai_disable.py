from app import create_app


def test_missing_openai_api_key_disables_ai(tmp_path):
    test_db = tmp_path / 'test.db'
    app = create_app({'TESTING': True, 'DB_PATH': str(test_db), 'OPENAI_API_KEY': ''})
    client = app.test_client()

    response = client.get('/api/health')

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['ai']['enabled'] is False
    assert payload['ai']['reason'] == 'OPENAI_API_KEY missing; AI features disabled'
