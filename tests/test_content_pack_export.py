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


def test_backup_zip_includes_database_media_and_snapshot(tmp_path):
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
            ("keep.mp4", "video", "backup"),
        )
        conn.execute(
            "INSERT INTO session_template (name, discipline, duration_minutes, json_blocks) VALUES (?, ?, ?, ?)",
            ("Backup Template", "strength", 12, json.dumps({"blocks": [{"name": "x", "minutes": 12}]})),
        )
        conn.commit()
    (media_dir / "keep.mp4").write_bytes(b"media")

    response = client.get("/api/export/backup")
    assert response.status_code == 200
    assert response.mimetype == "application/zip"

    with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
        names = set(archive.namelist())
        assert "flowform.db" in names
        assert "flowform_backup.json" in names
        assert "media/keep.mp4" in names


def test_restore_reports_missing_media_references_without_crash(tmp_path):
    source_db = tmp_path / "source.db"
    source_media = tmp_path / "source_media"
    source_media.mkdir(parents=True, exist_ok=True)
    source_app = create_app({"TESTING": True, "DB_PATH": str(source_db), "MEDIA_DIR": str(source_media)})
    source_client = source_app.test_client()

    with sqlite3.connect(source_db) as conn:
        conn.execute("INSERT INTO media_item (filename, media_type, tags) VALUES (?, ?, ?)", ("lost.mp4", "video", "x"))
        media_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        conn.execute(
            "INSERT INTO session_template (name, discipline, duration_minutes, json_blocks) VALUES (?, ?, ?, ?)",
            ("Broken Media Template", "cardio", 15, json.dumps({"blocks": [{"name": "b", "minutes": 15, "media_id": media_id}]})),
        )
        conn.commit()

    backup_response = source_client.get("/api/export/backup")
    backup_bytes = backup_response.data

    mutated = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(backup_bytes), "r") as zin:
        with zipfile.ZipFile(mutated, "w", zipfile.ZIP_DEFLATED) as zout:
            for info in zin.infolist():
                if info.filename.startswith("media/"):
                    continue
                zout.writestr(info, zin.read(info.filename))
    mutated.seek(0)

    restore_db = tmp_path / "restore.db"
    restore_media = tmp_path / "restore_media"
    restore_media.mkdir(parents=True, exist_ok=True)
    restore_app = create_app({"TESTING": True, "DB_PATH": str(restore_db), "MEDIA_DIR": str(restore_media)})
    restore_client = restore_app.test_client()

    response = restore_client.post(
        "/api/import/backup",
        data={"file": (mutated, "backup.zip")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["warnings"]
    assert payload["warnings"][0]["code"] == "missing_media_references"


def test_navigation_and_empty_state_ctas_are_visible(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "DB_PATH": str(tmp_path / "test.db"),
            "MEDIA_DIR": str(tmp_path / "media"),
        }
    )
    client = app.test_client()

    templates_html = client.get("/templates").get_data(as_text=True)
    assert "Content Packs" in templates_html
    assert "Import Content Pack" in templates_html

    media_html = client.get("/media").get_data(as_text=True)
    assert "Upload Media" in media_html

    packs_html = client.get("/content-packs/ui").get_data(as_text=True)
    assert "Import Pack ZIP" in packs_html
    assert 'name="viewport"' in packs_html
