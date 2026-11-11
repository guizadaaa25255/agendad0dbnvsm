from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


# Schemas de Autenticação
class SendCodeRequest(BaseModel):
    phone: str = Field(..., description="Número de telefone internacional (ex: +5585999999999)")
    api_id: Optional[str] = Field(None, description="api_id desta conta (vazio = padrão do .env)")
    api_hash: Optional[str] = Field(None, description="api_hash desta conta (vazio = padrão do .env)")


class SendCodeResponse(BaseModel):
    session_token: str
    phone: str
    message: str


class VerifyCodeRequest(BaseModel):
    session_token: str
    code: str = Field(..., description="Código de confirmação recebido no Telegram/SMS")


class TwoFactorRequest(BaseModel):
    session_token: str
    password: str = Field(..., description="Senha da Verificação em Duas Etapas (2FA)")


class AccountItem(BaseModel):
    id: int
    phone: str
    first_name: Optional[str] = None
    username: Optional[str] = None
    is_premium: bool = False
    connected_at: Optional[datetime] = None
    avatar_url: Optional[str] = None


class AccountStatusResponse(BaseModel):
    connected: bool
    accounts: List[AccountItem] = []


# Schemas de Story
class StoryUpdateRequest(BaseModel):
    caption: Optional[str] = None
    scheduled_time: Optional[datetime] = None
    period: Optional[int] = Field(None, description="21600, 43200, 86400 ou 172800")
    pinned: Optional[bool] = None
    privacy: Optional[str] = Field(None, description="all, contacts ou close_friends")


class StoryLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    story_id: int
    attempt_number: int
    status: str
    message: str
    created_at: datetime
    created_at_formatted: Optional[str] = None


class StoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: Optional[int] = None
    account_label: Optional[str] = None
    media_url: str
    media_type: str
    caption: Optional[str] = None
    scheduled_time: datetime
    scheduled_time_formatted: Optional[str] = None
    period: int
    period_hours: int
    pinned: bool
    privacy: str
    status: str
    retry_count: int
    error_message: Optional[str] = None
    telegram_story_id: Optional[int] = None
    published_at: Optional[datetime] = None
    created_at: datetime
    logs: Optional[List[StoryLogResponse]] = []
