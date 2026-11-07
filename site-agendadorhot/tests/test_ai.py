import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_generate_ai_captions_endpoint():
    payload = {
        "topic": "praia de ferias",
        "tone": "engaging",
        "use_emojis": True,
        "use_hashtags": False,
        "include_cta": True
    }
    response = client.post("/api/ai/generate-captions", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "captions" in data
    assert len(data["captions"]) == 3
    for cap in data["captions"]:
        assert isinstance(cap, str)
        assert len(cap) > 10


def test_generate_ai_captions_different_tones():
    tones = ["lifestyle", "aesthetic", "inspirational", "funny", "mysterious"]
    for tone in tones:
        res = client.post("/api/ai/generate-captions", json={"topic": "teste", "tone": tone})
        assert res.status_code == 200
        assert len(res.json()["captions"]) == 3
