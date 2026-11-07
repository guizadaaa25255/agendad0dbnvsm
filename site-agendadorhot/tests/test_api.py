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
