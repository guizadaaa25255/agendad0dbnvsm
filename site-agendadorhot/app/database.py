from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import DATABASE_URL

# Configura engine do SQLite permitindo concorrência multithreaded segura
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False
)

# expire_on_commit=False evita DetachedInstanceError ao acessar atributos após commit
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

Base = declarative_base()


def get_db():
    """Dependência do FastAPI para fornecer uma sessão do banco por requisição."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Cria todas as tabelas caso não existam."""
    import app.models  # Importa para registrar os modelos no Base
    Base.metadata.create_all(bind=engine)
    _migrate()


def _migrate():
    """Migração leve: adiciona colunas novas em bancos SQLite já existentes."""
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    wanted = {
        "telegram_accounts": [("encrypted_api_id", "TEXT"), ("encrypted_api_hash", "TEXT")],
        "scheduled_stories": [("account_id", "INTEGER")],
    }
    with engine.begin() as conn:
        for table, cols in wanted.items():
            existing = {c["name"] for c in insp.get_columns(table)}
            for name, typ in cols:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {typ}"))
