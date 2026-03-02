from flask import Flask, render_template
from pathlib import Path


def test_session_start_shows_media_button_logic_when_media_attached():
    root = Path(__file__).resolve().parents[1]
    app = Flask(__name__, template_folder=str(root / "templates"))
    app.config["TESTING"] = True

    session_payload = {
        "title": "Test Session",
        "week": 1,
        "day_index": 1,
        "template_name": "Template A",
        "plan_day_id": 7,
        "blocks": [
            {"name": "Block 1", "minutes": 5, "seconds": 300, "media_id": 12},
            {"name": "Block 2", "minutes": 5, "seconds": 300, "media_id": None},
        ],
    }

    with app.test_request_context("/session/start/7"):
        html = render_template("session_start.html", session=session_payload)

    assert "Open Block Media" in html
    assert "const mediaId = block.media_id || block.media_item_id;" in html
    assert "href=\"/media/${mediaId}\"" in html
