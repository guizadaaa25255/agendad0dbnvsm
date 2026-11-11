import os
import uuid
import asyncio
import aiofiles
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form,
    Query,
    status
)
from sqlalchemy.orm import Session

from app.config import (
    UPLOAD_DIR,
    MAX_UPLOAD_SIZE_MB,
    ALLOWED_EXTENSIONS,
    APP_TIMEZONE
)
from app.database import get_db
from app.models import ScheduledStory, StoryLog, TelegramAccount
from app.schemas import StoryResponse, StoryUpdateRequest, StoryLogResponse
from app.scheduler import schedule_story_job, cancel_story_job
from app.telegram_client import toggle_story_pinned_on_telegram
from app.media_utils import prepare_story_video

router = APIRouter(prefix="/api/stories", tags=["Stories"])

VALID_PERIODS = {21600: 6, 43200: 12, 86400: 24, 172800: 48}
VALID_PRIVACIES = {"all", "contacts", "close_friends"}


def _serialize_story(story: ScheduledStory, db: Session = None) -> dict:
    """Formata o story para a resposta da API com URLs e datas legíveis."""
    filename = Path(story.media_path).name
    media_url = f"/media/{filename}"
    period_hours = VALID_PERIODS.get(story.period, story.period // 3600)

    # Formatação de fuso horário
    st = story.scheduled_time
    if st.tzinfo is None:
        st_localized = st.replace(tzinfo=APP_TIMEZONE)
    else:
        st_localized = st.astimezone(APP_TIMEZONE)

    formatted_time = st_localized.strftime("%d/%m/%Y às %H:%M")

    logs_data = []
    if story.logs:
        for l in story.logs:
            created_loc = l.created_at.replace(tzinfo=APP_TIMEZONE) if l.created_at.tzinfo is None else l.created_at.astimezone(APP_TIMEZONE)
            logs_data.append({
                "id": l.id,
                "story_id": l.story_id,
                "attempt_number": l.attempt_number,
                "status": l.status,
                "message": l.message,
                "created_at": l.created_at,
                "created_at_formatted": created_loc.strftime("%d/%m/%Y %H:%M:%S")
            })

    account_label = None
    if db is not None and story.account_id:
        acc = db.query(TelegramAccount).filter(TelegramAccount.id == story.account_id).first()
        if acc:
            account_label = f"{acc.first_name or acc.username or ''} ({acc.phone})".strip()

    return {
        "id": story.id,
        "account_id": story.account_id,
        "account_label": account_label,
        "media_url": media_url,
        "media_type": story.media_type,
        "caption": story.caption,
        "scheduled_time": story.scheduled_time,
        "scheduled_time_formatted": formatted_time,
        "period": story.period,
        "period_hours": period_hours,
        "pinned": story.pinned,
        "privacy": story.privacy,
        "status": story.status,
        "retry_count": story.retry_count,
        "error_message": story.error_message,
        "telegram_story_id": story.telegram_story_id,
        "published_at": story.published_at,
        "created_at": story.created_at,
        "logs": logs_data
    }


@router.post("", response_model=StoryResponse, status_code=status.HTTP_201_CREATED)
async def create_story(
    account_id: int = Form(..., description="Conta do Telegram que vai publicar"),
    file: UploadFile = File(..., description="Arquivo de foto ou vídeo"),
    caption: Optional[str] = Form(None, description="Legenda do story"),
    scheduled_time: str = Form(..., description="Data e hora no formato ISO (ex: 2026-11-02T16:00)"),
    period: int = Form(86400, description="Duração em segundos: 21600 (6h), 43200 (12h), 86400 (24h) ou 172800 (48h)"),
    pinned: bool = Form(False, description="Fixar no perfil do Telegram"),
    privacy: str = Form("all", description="Privacidade: all, contacts ou close_friends"),
    remove_audio: bool = Form(False, description="Remover faixa de áudio caso seja vídeo"),
    db: Session = Depends(get_db)
):
    """
    Cria e agenda um novo story para publicação automática no horário marcado.
    """
    # 0. A conta escolhida precisa existir e estar conectada
    account = db.query(TelegramAccount).filter(TelegramAccount.id == account_id, TelegramAccount.is_active == True).first()
    if not account:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Conta do Telegram inválida ou desconectada. Conecte/escolha uma conta.")

    # 1. Validação da extensão do arquivo
    file_ext = Path(file.filename or "").suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Extensão de arquivo não permitida ({file_ext}). Use: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    media_type = "photo" if file_ext in {".jpg", ".jpeg", ".png", ".webp"} else "video"

    # 2. Validação da duração
    if period not in VALID_PERIODS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Duração inválida ({period}s). As opções permitidas são: 21600 (6h), 43200 (12h), 86400 (24h) ou 172800 (48h)."
        )

    # 3. Validação da privacidade
    if privacy not in VALID_PRIVACIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Privacidade inválida ({privacy}). Opções permitidas: all, contacts, close_friends."
        )

    # 4. Validação da data e hora agendada (fuso America/Fortaleza)
    try:
        # Suporta formatos ISO como 2026-11-02T15:30 ou 2026-11-02 15:30
        clean_dt_str = scheduled_time.replace("Z", "").strip()
        parsed_dt = datetime.fromisoformat(clean_dt_str)
        if parsed_dt.tzinfo is None:
            scheduled_dt_fortaleza = parsed_dt.replace(tzinfo=APP_TIMEZONE)
        else:
            scheduled_dt_fortaleza = parsed_dt.astimezone(APP_TIMEZONE)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato de data e hora inválido. Utilize o formato ISO (ex: YYYY-MM-DDTHH:MM)."
        )

    now_fortaleza = datetime.now(APP_TIMEZONE)
    if scheduled_dt_fortaleza <= now_fortaleza:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é permitido agendar para um horário que já passou. Escolha um horário futuro."
        )

    # 5. Salva o arquivo de mídia no disco
    safe_filename = f"{uuid.uuid4().hex}{file_ext}"
    dest_path = UPLOAD_DIR / safe_filename

    total_bytes = 0
    max_bytes = MAX_UPLOAD_SIZE_MB * 1024 * 1024

    async with aiofiles.open(dest_path, "wb") as out_file:
        while content := await file.read(1024 * 1024):  # 1MB chunks
            total_bytes += len(content)
            if total_bytes > max_bytes:
                await out_file.close()
                if dest_path.exists():
                    dest_path.unlink()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Arquivo excede o tamanho máximo permitido de {MAX_UPLOAD_SIZE_MB}MB."
                )
            await out_file.write(content)

    # 5.1 Prepara/normaliza o vídeo para o padrão oficial de Stories do Telegram (MP4 H.264 720x1280 + remove áudio se solicitado)
    audio_removed = False
    if media_type == "video":
        try:
            dest_path = await asyncio.to_thread(prepare_story_video, dest_path, remove_audio=remove_audio)
            audio_removed = bool(remove_audio)
        except Exception as exc:
            if dest_path.exists():
                dest_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Não foi possível processar o vídeo para o Telegram: {exc}"
            )

    # 6. Registra no banco de dados SQLite
    story = ScheduledStory(
        account_id=account_id,
        media_path=str(dest_path),
        media_type=media_type,
        caption=caption.strip() if caption else None,
        scheduled_time=scheduled_dt_fortaleza,
        period=period,
        pinned=pinned,
        privacy=privacy,
        status="SCHEDULED",
        retry_count=0
    )
    db.add(story)
    db.commit()
    db.refresh(story)

    # 7. Adiciona log inicial
    audio_note = " Áudio removido do vídeo conforme selecionado." if audio_removed else ""
    init_log = StoryLog(
        story_id=story.id,
        attempt_number=0,
        status="INFO",
        message=f"Story criado e agendado para {scheduled_dt_fortaleza.strftime('%d/%m/%Y às %H:%M:%S')} (Fuso: America/Fortaleza).{audio_note}"
    )
    db.add(init_log)
    db.commit()

    # 8. Agenda tarefa no APScheduler
    schedule_story_job(story.id, scheduled_dt_fortaleza)

    return _serialize_story(story, db)


@router.get("", response_model=List[StoryResponse])
def list_stories(
    status_filter: Optional[str] = Query(None, alias="status", description="Filtrar por status: all, scheduled, published, failed"),
    account_id: Optional[int] = Query(None, description="Filtrar por conta específica"),
    db: Session = Depends(get_db)
):
    """Lista todos os stories cadastrados, ordenados por data."""
    query = db.query(ScheduledStory)

    if account_id is not None:
        query = query.filter(ScheduledStory.account_id == account_id)

    if status_filter and status_filter.upper() != "ALL":
        query = query.filter(ScheduledStory.status == status_filter.upper())

    stories = query.order_by(ScheduledStory.scheduled_time.desc()).all()
    return [_serialize_story(s, db) for s in stories]


@router.get("/{story_id}", response_model=StoryResponse)
def get_story(story_id: int, db: Session = Depends(get_db)):
    """Obtém detalhes de um story específico e seu histórico de tentativas."""
    story = db.query(ScheduledStory).filter(ScheduledStory.id == story_id).first()
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story não encontrado.")
    return _serialize_story(story, db)


@router.put("/{story_id}", response_model=StoryResponse)
def update_story(story_id: int, payload: StoryUpdateRequest, db: Session = Depends(get_db)):
    """Edita um story pendente (legenda, horário, duração, fixado, privacidade)."""
    story = db.query(ScheduledStory).filter(ScheduledStory.id == story_id).first()
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story não encontrado.")

    if story.status in ("PUBLISHED", "PUBLISHING"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível alterar um story que já foi publicado ou está em processo de publicação."
        )

    if payload.caption is not None:
        story.caption = payload.caption.strip() if payload.caption else None

    if payload.period is not None:
        if payload.period not in VALID_PERIODS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Duração inválida.")
        story.period = payload.period

    if payload.pinned is not None:
        story.pinned = payload.pinned

    if payload.privacy is not None:
        if payload.privacy not in VALID_PRIVACIES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Privacidade inválida.")
        story.privacy = payload.privacy

    if payload.scheduled_time is not None:
        new_time = payload.scheduled_time
        if new_time.tzinfo is None:
            new_time_fortaleza = new_time.replace(tzinfo=APP_TIMEZONE)
        else:
            new_time_fortaleza = new_time.astimezone(APP_TIMEZONE)

        now_fortaleza = datetime.now(APP_TIMEZONE)
        if new_time_fortaleza <= now_fortaleza:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="O novo horário deve ser futuro.")

        story.scheduled_time = new_time_fortaleza
        story.status = "SCHEDULED"
        schedule_story_job(story.id, new_time_fortaleza)

        log_entry = StoryLog(
            story_id=story.id,
            attempt_number=story.retry_count,
            status="INFO",
            message=f"Horário de agendamento alterado para {new_time_fortaleza.strftime('%d/%m/%Y às %H:%M')}."
        )
        db.add(log_entry)

    story.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(story)
    return _serialize_story(story, db)


@router.post("/{story_id}/cancel")
def cancel_story(story_id: int, db: Session = Depends(get_db)):
    """Cancela o agendamento de um story pendente."""
    story = db.query(ScheduledStory).filter(ScheduledStory.id == story_id).first()
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story não encontrado.")

    if story.status == "PUBLISHED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Não é possível cancelar um story já publicado.")

    cancel_story_job(story.id)
    story.status = "CANCELLED"
    story.updated_at = datetime.now(timezone.utc)

    log_entry = StoryLog(
        story_id=story.id,
        attempt_number=story.retry_count,
        status="INFO",
        message="Agendamento cancelado pelo usuário."
    )
    db.add(log_entry)
    db.commit()

    return {"message": "Story cancelado com sucesso.", "status": "CANCELLED"}


@router.post("/{story_id}/toggle-grid")
async def toggle_story_grid(story_id: int, db: Session = Depends(get_db)):
    """Fixa ou desafixa um story já publicado na grade do perfil no Telegram."""
    story = db.query(ScheduledStory).filter(ScheduledStory.id == story_id).first()
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story não encontrado.")

    if story.status != "PUBLISHED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Apenas stories já publicados podem ser fixados ou removidos da grade."
        )

    target_pinned = not story.pinned
    try:
        await toggle_story_pinned_on_telegram(db, story, target_pinned)
        story.pinned = target_pinned
        story.updated_at = datetime.now(timezone.utc)

        log_entry = StoryLog(
            story_id=story.id,
            attempt_number=1,
            status="SUCCESS",
            message=f"Story {'adicionado à grade do perfil' if target_pinned else 'removido da grade do perfil'} pelo usuário."
        )
        db.add(log_entry)
        db.commit()
        db.refresh(story)

        return _serialize_story(story, db)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao alterar fixação na grade do Telegram: {str(e)}"
        )


@router.delete("/{story_id}")
def delete_story(story_id: int, db: Session = Depends(get_db)):
    """Exclui o story, remove a tarefa do agendador e deleta o arquivo de mídia."""
    story = db.query(ScheduledStory).filter(ScheduledStory.id == story_id).first()
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story não encontrado.")

    # Remove do agendador
    cancel_story_job(story.id)

    # Remove arquivo de mídia do disco
    try:
        if os.path.exists(story.media_path):
            os.remove(story.media_path)
    except Exception:
        pass

    # Exclui do banco de dados (logs são excluídos em cascata)
    db.delete(story)
    db.commit()

    return {"message": "Story excluído com sucesso."}


@router.get("/{story_id}/logs", response_model=List[StoryLogResponse])
def get_story_logs(story_id: int, db: Session = Depends(get_db)):
    """Retorna todo o histórico de logs de tentativas de publicação deste story."""
    story = db.query(ScheduledStory).filter(ScheduledStory.id == story_id).first()
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story não encontrado.")

    logs = db.query(StoryLog).filter(StoryLog.story_id == story_id).order_by(StoryLog.created_at.desc()).all()
    results = []
    for l in logs:
        created_loc = l.created_at.replace(tzinfo=APP_TIMEZONE) if l.created_at.tzinfo is None else l.created_at.astimezone(APP_TIMEZONE)
        results.append({
            "id": l.id,
            "story_id": l.story_id,
            "attempt_number": l.attempt_number,
            "status": l.status,
            "message": l.message,
            "created_at": l.created_at,
            "created_at_formatted": created_loc.strftime("%d/%m/%Y %H:%M:%S")
        })
    return results

