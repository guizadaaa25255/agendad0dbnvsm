import pytest
from app.security import encrypt_session, decrypt_session


def test_session_encryption_and_decryption():
    raw_session = "1Bfb5c-telethon-dummy-string-session-abcdef1234567890"
    encrypted = encrypt_session(raw_session)

    assert encrypted != raw_session
    assert len(encrypted) > 20

    decrypted = decrypt_session(encrypted)
    assert decrypted == raw_session


def test_empty_session_handling():
    assert encrypt_session("") == ""
    assert decrypt_session("") == ""


def test_invalid_session_decryption():
    with pytest.raises(ValueError):
        decrypt_session("not-a-valid-fernet-token")
