from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    LargeBinary
)
from sqlalchemy.orm import relationship
from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class TelegramAccount(Base):
    """
    Armazena a conta do Telegram conectada pelo usuário.
    A sessão é mantida exclusivamente de forma criptografada.
    """
    __tablename__ = "telegram_accounts"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(32), unique=True, index=True, nullable=False)
    user_id = Column(BigInteger, nullable=True)
    first_name = Column(String(128), nullable=True)
    username = Column(String(128), nullable=True)
    is_premium = Column(Boolean, default=False, nullable=False)
    encrypted_session = Column(Text, nullable=False)
    # api_id / api_hash próprios da conta (criptografados); vazio = usa o padrão do .env
    encrypted_api_id = Column(Text, nullable=True)
    encrypted_api_hash = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    connected_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class ScheduledStory(Base):
    """
    Armazena o story agendado para publicação automática no Telegram.
    """
    __tablename__ = "scheduled_stories"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, nullable=True, index=True)  # conta que vai publicar
    media_path = Column(String(512), nullable=False)
    media_type = Column(String(16), nullable=False)  # 'photo' ou 'video'
    media_data = Column(LargeBinary, nullable=True)  # Cópia binária para sobreviver a reinícios na nuvem
    caption = Column(Text, nullable=True)
    scheduled_time = Column(DateTime, nullable=False, index=True)
    period = Column(Integer, nullable=False, default=86400)  # 21600 (6h), 43200 (12h), 86400 (24h), 172800 (48h)
    pinned = Column(Boolean, nullable=False, default=False)
    privacy = Column(String(32), nullable=False, default="all")  # 'all', 'contacts', 'close_friends'
    status = Column(String(32), nullable=False, default="SCHEDULED", index=True)  # SCHEDULED, PUBLISHING, PUBLISHED, FAILED, CANCELLED
    retry_count = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    telegram_story_id = Column(Integer, nullable=True)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    logs = relationship("StoryLog", back_populates="story", cascade="all, delete-orphan", order_by="StoryLog.created_at.desc()")


class StoryLog(Base):
    """
    Registros e histórico de execuções / tentativas de publicação de cada story.
    """
    __tablename__ = "story_logs"

    id = Column(Integer, primary_key=True, index=True)
    story_id = Column(Integer, ForeignKey("scheduled_stories.id", ondelete="CASCADE"), nullable=False, index=True)
    attempt_number = Column(Integer, nullable=False, default=1)
    status = Column(String(32), nullable=False)  # 'SUCCESS', 'FAILED', 'INFO'
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    story = relationship("ScheduledStory", back_populates="logs")
