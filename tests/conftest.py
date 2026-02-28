import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app


@pytest.fixture()
def client(tmp_path):
    test_db = tmp_path / "test.db"
    app = create_app({"TESTING": True, "DB_PATH": str(test_db), "OPENAI_API_KEY": "test-key"})
    return app.test_client()
