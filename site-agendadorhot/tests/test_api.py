import io
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.config import APP_TIMEZONE

client = TestClient(app)


def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["timezone"] == "America/Fortaleza"


def test_auth_status_initially_disconnected():
    response = client.get("/api/auth/status")
    assert response.status_code == 200
    data = response.json()
    assert "connected" in data


def test_reject_story_with_past_datetime(account_id):
    # Tenta agendar para 1 hora atrás
    past_time = datetime.now(APP_TIMEZONE) - timedelta(hours=1)
    file_content = b"fake image bytes"

    response = client.post(
        "/api/stories",
        data={
            "account_id": account_id,
            "scheduled_time": past_time.strftime("%Y-%m-%dT%H:%M"),
            "period": 86400,
            "pinned": True,
            "privacy": "all",
            "caption": "Test past story"
        },
        files={"file": ("test.jpg", io.BytesIO(file_content), "image/jpeg")}
    )

    assert response.status_code == 400
    assert "já passou" in response.json()["detail"]


def test_reject_invalid_file_extension(account_id):
    future_time = datetime.now(APP_TIMEZONE) + timedelta(minutes=10)
    file_content = b"dummy content"

    response = client.post(
        "/api/stories",
        data={
            "account_id": account_id,
            "scheduled_time": future_time.strftime("%Y-%m-%dT%H:%M"),
            "period": 86400,
            "pinned": False,
            "privacy": "all"
        },
        files={"file": ("bad_script.sh", io.BytesIO(file_content), "text/plain")}
    )

    assert response.status_code == 400
    assert "não permitida" in response.json()["detail"]


def test_reject_invalid_period(account_id):
    future_time = datetime.now(APP_TIMEZONE) + timedelta(minutes=10)
    file_content = b"fake image"

    response = client.post(
        "/api/stories",
        data={
            "account_id": account_id,
            "scheduled_time": future_time.strftime("%Y-%m-%dT%H:%M"),
            "period": 99999,  # Período não suportado
            "pinned": False,
            "privacy": "all"
        },
        files={"file": ("photo.png", io.BytesIO(file_content), "image/png")}
    )

    assert response.status_code == 400
    assert "Duração inválida" in response.json()["detail"]


def test_create_and_manage_story_lifecycle(account_id):
    # 1. Criação com pinned=True e 48h (172800)
    future_time = datetime.now(APP_TIMEZONE) + timedelta(minutes=5)
    file_content = b"\xff\xd8\xff\xe0\x00\x10JFIF"  # Header JPEG mínimo

    res = client.post(
        "/api/stories",
        data={
            "account_id": account_id,
            "scheduled_time": future_time.strftime("%Y-%m-%dT%H:%M"),
            "period": 172800,  # 48h Premium
            "pinned": True,
            "privacy": "contacts",
            "caption": "Story de teste automatizado com pinned=True"
        },
        files={"file": ("story.jpg", io.BytesIO(file_content), "image/jpeg")}
    )

    assert res.status_code == 201
    created = res.json()
    story_id = created["id"]
    assert created["pinned"] is True
    assert created["period"] == 172800
    assert created["period_hours"] == 48
    assert created["privacy"] == "contacts"
    assert created["status"] == "SCHEDULED"

    # 2. Listagem de stories
    list_res = client.get("/api/stories")
    assert list_res.status_code == 200
    stories = list_res.json()
    assert any(s["id"] == story_id for s in stories)

    # 3. Consulta individual e logs
    get_res = client.get(f"/api/stories/{story_id}")
    assert get_res.status_code == 200
    assert get_res.json()["caption"] == "Story de teste automatizado com pinned=True"

    logs_res = client.get(f"/api/stories/{story_id}/logs")
    assert logs_res.status_code == 200
    assert len(logs_res.json()) >= 1

    # 4. Atualização (PUT)
    update_res = client.put(
        f"/api/stories/{story_id}",
        json={"caption": "Legenda atualizada com sucesso", "pinned": False}
    )
    assert update_res.status_code == 200
    assert update_res.json()["caption"] == "Legenda atualizada com sucesso"
    assert update_res.json()["pinned"] is False

    # 5. Cancelamento
    cancel_res = client.post(f"/api/stories/{story_id}/cancel")
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "CANCELLED"

    # 6. Exclusão
    del_res = client.delete(f"/api/stories/{story_id}")
    assert del_res.status_code == 200

    # Confirma que foi excluído
    not_found_res = client.get(f"/api/stories/{story_id}")
    assert not_found_res.status_code == 404


def test_reject_story_without_connected_account():
    future_time = datetime.now(APP_TIMEZONE) + timedelta(minutes=10)
    response = client.post(
        "/api/stories",
        data={"account_id": 999999, "scheduled_time": future_time.strftime("%Y-%m-%dT%H:%M"),
              "period": 86400, "pinned": False, "privacy": "all"},
        files={"file": ("photo.png", io.BytesIO(b"x"), "image/png")}
    )
    assert response.status_code == 400
    assert "Conta" in response.json()["detail"]


def test_status_never_exposes_credentials(account_id):
    body = client.get("/api/auth/status").text
    assert "api_hash" not in body and "api_id" not in body and "session" not in body


def test_account_avatar_url_and_endpoint(account_id):
    from app.telegram_client import get_avatar_path

    status_res = client.get("/api/auth/status")
    assert status_res.status_code == 200
    accounts = status_res.json()["accounts"]
    acc = next(a for a in accounts if a["id"] == account_id)
    assert acc["avatar_url"] == f"/api/auth/avatar/{account_id}"

    avatar_file = get_avatar_path(account_id)
    avatar_file.unlink(missing_ok=True)
    # Sem foto no cache/sessão fake -> retorna 404 graciosamente
    missing_res = client.get(acc["avatar_url"])
    assert missing_res.status_code == 404

    # Com foto salva no cache -> serve a imagem JPEG
    avatar_file.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg-data")
    try:
        ok_res = client.get(acc["avatar_url"])
        assert ok_res.status_code == 200
        assert ok_res.headers["content-type"].startswith("image/jpeg")
        assert ok_res.content == b"\xff\xd8\xff\xe0fake-jpeg-data"
    finally:
        avatar_file.unlink(missing_ok=True)


def test_media_restores_from_db_when_disk_wiped(account_id):
    from pathlib import Path
    from app.config import UPLOAD_DIR

    future_time = datetime.now(APP_TIMEZONE) + timedelta(minutes=20)
    payload_bytes = b"fake-jpeg-cloud-persistence-test"

    res = client.post(
        "/api/stories",
        data={
            "account_id": account_id,
            "scheduled_time": future_time.strftime("%Y-%m-%dT%H:%M"),
            "period": 172800,
            "pinned": True,
            "privacy": "all",
        },
        files={"file": ("persist.jpg", io.BytesIO(payload_bytes), "image/jpeg")},
    )
    assert res.status_code == 201
    story_data = res.json()
    media_url = story_data["media_url"]
    disk_path = UPLOAD_DIR / Path(media_url).name
    assert disk_path.exists()

    # Simula reinício do disco efêmero na nuvem apagando o arquivo do disco
    disk_path.unlink()
    assert not disk_path.exists()

    # Ao requisitar /media/..., deve restaurar automaticamente do banco e servir 200
    media_res = client.get(media_url)
    assert media_res.status_code == 200
    assert media_res.content == payload_bytes
    assert disk_path.exists()

    # Limpeza
    client.delete(f"/api/stories/{story_data['id']}")
