import pytest
from app.telegram_client import resolve_credentials, account_credentials
from app.models import TelegramAccount
from app.security import encrypt_session


def test_custom_credentials_valid():
    assert resolve_credentials("12345", "a" * 32) == (12345, "a" * 32)


def test_default_credentials_from_env():
    api_id, api_hash = resolve_credentials("", "")
    assert isinstance(api_id, int) and len(api_hash) == 32


@pytest.mark.parametrize("api_id,api_hash", [("abc", "a" * 32), ("123", "short"), ("123", "z" * 32), ("123", "")])
def test_invalid_credentials_rejected(api_id, api_hash):
    with pytest.raises(ValueError):
        resolve_credentials(api_id, api_hash)


def test_account_credentials_roundtrip_encrypted():
    acc = TelegramAccount(phone="+1", encrypted_session="x",
                          encrypted_api_id=encrypt_session("777"), encrypted_api_hash=encrypt_session("b" * 32))
    assert "777" not in acc.encrypted_api_id
    assert account_credentials(acc) == (777, "b" * 32)
