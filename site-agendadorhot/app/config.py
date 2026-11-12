import os
from pathlib import Path
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

# Diretório raiz do projeto
BASE_DIR = Path(__file__).resolve().parent.parent

# Carrega variáveis de ambiente do arquivo .env
load_dotenv(dotenv_path=BASE_DIR / ".env")

# Credenciais MTProto do Telegram
TELEGRAM_API_ID_RAW = os.getenv("TELEGRAM_API_ID", "38038737").strip()
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "825a5e23a53d5991ba488adfec3da147").strip()

# As credenciais do .env são o PADRÃO (opcional). Cada conta pode usar o próprio
# api_id/api_hash, informados na tela de conexão e guardados criptografados.
TELEGRAM_API_ID = None
if TELEGRAM_API_ID_RAW:
    try:
        TELEGRAM_API_ID = int(TELEGRAM_API_ID_RAW)
    except ValueError:
        raise ValueError("TELEGRAM_API_ID deve ser um número inteiro válido no .env.")

# Chave de criptografia Fernet para salvar a sessão do Telegram
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "2STLzwYdbeRLSJwTvBDa5S2sFJ7K_HMCxE6ptXGBlsU=").strip()
if not ENCRYPTION_KEY:
    # Gera uma chave temporária caso não esteja definida (mas avisa)
    from cryptography.fernet import Fernet
    ENCRYPTION_KEY = Fernet.generate_key().decode()

# Configurações do Banco de Dados (SQLite local ou PostgreSQL na nuvem)
_raw_db_url = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'scheduler.db'}").strip()
if _raw_db_url.startswith("postgres://"):
    _raw_db_url = _raw_db_url.replace("postgres://", "postgresql://", 1)
DATABASE_URL = _raw_db_url

# Fuso horário padrão do sistema (America/Fortaleza)
TIMEZONE_STR = os.getenv("TIMEZONE", "America/Fortaleza")
try:
    APP_TIMEZONE = ZoneInfo(TIMEZONE_STR)
except Exception:
    APP_TIMEZONE = ZoneInfo("America/Fortaleza")

# Diretório de uploads e limites de arquivo
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

AVATARS_DIR = DATA_DIR / "avatars"
AVATARS_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov"}

# Servidor Web
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
APP_ENV = os.getenv("APP_ENV", "production")
