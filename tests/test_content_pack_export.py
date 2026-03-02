import io
import json
import sqlite3
import zipfile

from app import create_app


def test_export_returns_zip_and_content_pack_json(tmp_path):
    db_path = tmp_path / "test.db"
    media_dir = tmp_path / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    app = create_app(
        {
            "TESTING": True,
            "DB_PATH": str(db_path),
            "MEDIA_DIR": str(media_dir),
            "OPENAI_API_KEY": "test-key",
            "VERSION": "test-version",
        }
    )
    client = app.test_client()

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO media_item (filename, media_type, tags) VALUES (?, ?, ?)",
            ("clip.mp4", "video", "tag1,tag2"),
        )
        media_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn.execute(
            "INSERT INTO media_item (filename, media_type, tags) VALUES (?, ?, ?)",
            ("unused.mp4", "video", "unused"),
        )

        blocks = json.dumps({"blocks": [{"name": "warmup", "minutes": 10, "media_item_id": media_id}]})
        conn.execute(
            "INSERT INTO session_template (name, discipline, duration_minutes, json_blocks) VALUES (?, ?, ?, ?)",
            ("Template A", "strength", 10, blocks),
        )
        template_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn.commit()

    (media_dir / "clip.mp4").write_bytes(b"fake-media")
    (media_dir / "unused.mp4").write_bytes(b"unused-media")

    response = client.post("/content-packs/export", json={"template_ids": [template_id]})

    assert response.status_code == 200
    assert response.mimetype == "application/zip"

    with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
        assert "content_pack.json" in archive.namelist()
        assert "media/clip.mp4" in archive.namelist()
        assert "media/unused.mp4" not in archive.namelist()

        payload = json.loads(archive.read("content_pack.json"))
        assert payload["templates"][0]["id"] == template_id
        assert payload["media"][0]["filename"] == "clip.mp4"
        assert payload["version"]["app_version"] == "test-version"


def test_media_attachment_renders_on_player_page(tmp_path):
    db_path = tmp_path / "test.db"
    media_dir = tmp_path / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    app = create_app(
        {
            "TESTING": True,
            "DB_PATH": str(db_path),
            "MEDIA_DIR": str(media_dir),
        }
    )
    client = app.test_client()

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO media_item (filename, media_type, tags) VALUES (?, ?, ?)",
            ("demo.mp4", "video", "demo"),
        )
        media_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        blocks = json.dumps({"blocks": [{"name": "main", "minutes": 8}]})
        conn.execute(
            "INSERT INTO session_template (name, discipline, duration_minutes, json_blocks) VALUES (?, ?, ?, ?)",
            ("Template With Media", "cardio", 8, blocks),
        )
        template_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn.commit()

    (media_dir / "demo.mp4").write_bytes(b"demo")

    save_resp = client.post(
        f"/templates/builder/{template_id}/save",
        data={"media_id_0": str(media_id)},
        follow_redirects=True,
    )
    assert save_resp.status_code == 200

    player_resp = client.get(f"/session/player/{template_id}")
    assert player_resp.status_code == 200
    html = player_resp.get_data(as_text=True)
    assert "Attached media: demo.mp4" in html
    assert "/media/file/demo.mp4" in html
