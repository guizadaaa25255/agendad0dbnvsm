from cryptography.fernet import Fernet, InvalidToken
from app.config import ENCRYPTION_KEY

# Instância Fernet configurada com a chave do .env
try:
    _fernet = Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)
except Exception as e:
    raise RuntimeError(f"Chave de criptografia ENCRYPTION_KEY inválida: {e}")


def encrypt_session(session_string: str) -> str:
    """
    Criptografa a string de sessão do Telethon antes de salvar no banco de dados.
    Nunca permite que credenciais brutas fiquem expostas em texto puro.
    """
    if not session_string:
        return ""
    encrypted_bytes = _fernet.encrypt(session_string.encode("utf-8"))
    return encrypted_bytes.decode("utf-8")


def decrypt_session(encrypted_session: str) -> str:
    """
    Descriptografa a string de sessão do Telethon para inicializar o cliente MTProto.
    """
    if not encrypted_session:
        return ""
    try:
        decrypted_bytes = _fernet.decrypt(encrypted_session.encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except InvalidToken:
        raise ValueError("Falha ao descriptografar a sessão: chave de criptografia inválida ou sessão corrompida.")
