import pytest
from app.database import init_db, SessionLocal
from app.models import TelegramAccount
from app.security import encrypt_session


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Inicializa as tabelas do SQLite antes dos testes executarem."""
    init_db()


@pytest.fixture
def account_id():
    """Conta de teste conectada, com credenciais próprias criptografadas."""
    db = SessionLocal()
    acc = TelegramAccount(
        phone="+5500000000000", first_name="Teste", is_active=True,
        encrypted_session=encrypt_session("fake-session"),
        encrypted_api_id=encrypt_session("12345"),
        encrypted_api_hash=encrypt_session("a" * 32),
    )
    db.add(acc)
    db.commit()
    acc_id = acc.id
    yield acc_id
    db.delete(acc)
    db.commit()
    db.close()
