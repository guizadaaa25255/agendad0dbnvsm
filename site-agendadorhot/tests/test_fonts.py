from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_list_fonts():
    response = client.get("/api/fonts")
    assert response.status_code == 200
    data = response.json()
    assert "fonts" in data
    assert len(data["fonts"]) == 9
    font_ids = [f["id"] for f in data["fonts"]]
    assert font_ids == ["mfslots", "goxtosastyle", "pinkcandyy", "docelaranja", "isapurpleblue", "Mellowfont", "Pink_Wink", "isapinkblue", "mfslots2"]

def test_format_font_spaced():
    response = client.post("/api/fonts/format", json={
        "text": "BOA NOITE",
        "font": "mfslots",
        "spaced": True
    })
    assert response.status_code == 200
    data = response.json()
    assert "html" in data
    assert "preview" in data
    assert "<tg-emoji" in data["html"]
    # Verifica caractere alt 🔤
    assert "🔤" in data["html"]
    assert "B O A   N O I T E" in data["preview"]

def test_format_font_not_spaced():
    response = client.post("/api/fonts/format", json={
        "text": "BOA",
        "font": "mfslots",
        "spaced": False
    })
    assert response.status_code == 200
    data = response.json()
    assert "html" in data
    assert "<tg-emoji" in data["html"]
    assert data["preview"] == "BOA"

def test_pinkcandyy_boa_tarde():
    response = client.post("/api/fonts/format", json={
        "text": "BOA TARDE",
        "font": "pinkcandyy",
        "spaced": True
    })
    assert response.status_code == 200
    data = response.json()
    html = data["html"]
    # Garante que cada letra de BOA TARDE usa o ID correto do grid real
    assert 'emoji-id="5015133195851531287"' in html  # B (#1)
    assert 'emoji-id="5015059322414039797"' in html  # O (#13)
    assert 'emoji-id="5015163363701818454"' in html  # A (#0)
    assert 'emoji-id="5015085191002063892"' in html  # T (#18)
    assert 'emoji-id="5015318811453162576"' in html  # R (#16)
    assert 'emoji-id="5014912005035787330"' in html  # D (#42)
    assert 'emoji-id="5017204830377083728"' in html  # E (#3)

