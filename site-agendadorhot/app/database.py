from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import DATABASE_URL, BASE_DIR

# Configura engine para SQLite local ou PostgreSQL na nuvem
is_sqlite = "sqlite" in DATABASE_URL
engine_kwargs = {
    "echo": False,
}
if is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["connect_args"] = {"connect_timeout": 10}
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_recycle"] = 180
    engine_kwargs["pool_size"] = 5
    engine_kwargs["max_overflow"] = 5

engine = create_engine(DATABASE_URL, **engine_kwargs)

# expire_on_commit=False evita DetachedInstanceError ao acessar atributos após commit
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

Base = declarative_base()


def get_db():
    """Dependência do FastAPI para fornecer uma sessão do banco por requisição."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """Cria todas as tabelas caso não existam e aplica migrações leves."""
    import app.models  # Importa para registrar os modelos no Base
    Base.metadata.create_all(bind=engine)
    _migrate()
    if not is_sqlite:
        _seed_accounts_from_sqlite_if_empty()


def _migrate():
    """Migração leve: adiciona colunas novas em bancos já existentes."""
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    binary_type = "BLOB" if is_sqlite else "BYTEA"
    wanted = {
        "telegram_accounts": [
            ("encrypted_api_id", "TEXT"),
            ("encrypted_api_hash", "TEXT"),
            ("avatar_data", binary_type),
        ],
        "scheduled_stories": [("account_id", "INTEGER"), ("media_data", binary_type)],
    }
    with engine.begin() as conn:
        for table, cols in wanted.items():
            if not insp.has_table(table):
                continue
            existing = {c["name"] for c in insp.get_columns(table)}
            for name, typ in cols:
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {typ}"))


def _seed_accounts_from_sqlite_if_empty():
    """
    Ao migrar para PostgreSQL pela primeira vez, importa automaticamente as contas do Telegram
    já conectadas no SQLite local para o usuário não precisar logar tudo de novo.
    """
    import sqlite3
    from sqlalchemy import text
    from app.models import TelegramAccount

    sqlite_path = BASE_DIR / "data" / "scheduler.db"
    if not sqlite_path.exists():
        return

    db = SessionLocal()
    try:
        if db.query(TelegramAccount).count() > 0:
            return

        src = sqlite3.connect(str(sqlite_path))
        src.row_factory = sqlite3.Row
        try:
            rows = src.execute("SELECT * FROM telegram_accounts WHERE is_active = 1").fetchall()
        except Exception:
            rows = []
        finally:
            src.close()

        if not rows:
            return

        for r in rows:
            acc = TelegramAccount(
                id=r["id"],
                phone=r["phone"],
                user_id=r["user_id"],
                first_name=r["first_name"],
                username=r["username"],
                is_premium=bool(r["is_premium"]),
                encrypted_session=r["encrypted_session"],
                encrypted_api_id=r["encrypted_api_id"],
                encrypted_api_hash=r["encrypted_api_hash"],
                is_active=bool(r["is_active"]),
            )
            db.add(acc)
        db.commit()

        # Ajusta a sequência de IDs no PostgreSQL para evitar colisão em novos logins
        try:
            db.execute(
                text(
                    "SELECT setval(pg_get_serial_sequence('telegram_accounts', 'id'), "
                    "COALESCE((SELECT MAX(id) FROM telegram_accounts), 1))"
                )
            )
            db.commit()
        except Exception:
            db.rollback()
    except Exception:
        db.rollback()
    finally:
        db.close()
