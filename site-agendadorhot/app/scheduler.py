import logging
import asyncio
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.base import JobLookupError
from sqlalchemy.orm import Session

from app.config import APP_TIMEZONE
from app.database import SessionLocal
from app.models import ScheduledStory, StoryLog
from app.telegram_client import publish_story_to_telegram

logger = logging.getLogger("telegram_scheduler")

# Instância do agendador APScheduler configurado com o fuso America/Fortaleza
scheduler = AsyncIOScheduler(timezone=APP_TIMEZONE)


def get_job_id(story_id: int) -> str:
    return f"story_{story_id}"


def _ensure_scheduler_loop():
    try:
        loop = asyncio.get_running_loop()
        if scheduler.running and scheduler._eventloop != loop:
            scheduler._eventloop = loop
    except RuntimeError:
        pass


def schedule_story_job(story_id: int, run_time: datetime):
    """
    Agenda um story no APScheduler para a data/hora especificada.
    Garante que a data possua o fuso horário correto (America/Fortaleza).
    """
    _ensure_scheduler_loop()
    if run_time.tzinfo is None:
        run_time = run_time.replace(tzinfo=APP_TIMEZONE)
    else:
        run_time = run_time.astimezone(APP_TIMEZONE)

    job_id = get_job_id(story_id)
    scheduler.add_job(
        execute_story_publish,
        "date",
        run_date=run_time,
        args=[story_id],
        id=job_id,
        replace_existing=True,
        misfire_grace_time=300
    )
    logger.info(f"[Scheduler] Story #{story_id} agendado para {run_time.isoformat()}")


def cancel_story_job(story_id: int) -> bool:
    """Cancela o job do story no agendador se estiver pendente."""
    _ensure_scheduler_loop()
    job_id = get_job_id(story_id)
    try:
        scheduler.remove_job(job_id)
        logger.info(f"[Scheduler] Story #{story_id} removido da fila de execução.")
        return True
    except JobLookupError:
        return False


async def execute_story_publish(story_id: int):
    """
    Função assíncrona executada no momento exato agendado.
    Publica o story e gerencia retentativas automáticas (até 3 vezes).
    """
    db: Session = SessionLocal()
    try:
        story = db.query(ScheduledStory).filter(ScheduledStory.id == story_id).first()
        if not story:
            logger.warning(f"[Scheduler] Story #{story_id} não encontrado no banco.")
            return

        if story.status in ("CANCELLED", "PUBLISHED"):
            logger.info(f"[Scheduler] Story #{story_id} já está {story.status}. Abortando execução.")
            return

        story.status = "PUBLISHING"
        db.commit()

        attempt = story.retry_count + 1
        logger.info(f"[Scheduler] Publicando Story #{story_id} (Tentativa {attempt}/3)...")

        try:
            telegram_story_id = await publish_story_to_telegram(db, story)

            story.status = "PUBLISHED"
            story.published_at = datetime.now(timezone.utc)
            story.telegram_story_id = telegram_story_id
            grid_warning = getattr(story, "_grid_warning", None)
            # Aviso da grade fica visível no card, mas o story continua PUBLISHED
            story.error_message = grid_warning

            log_entry = StoryLog(
                story_id=story.id,
                attempt_number=attempt,
                status="SUCCESS",
                message=f"Story publicado com sucesso no Telegram (ID MTProto: {telegram_story_id})."
                        + (" Colocado na grade do perfil." if story.pinned and not grid_warning else "")
                        + (f" ATENÇÃO: {grid_warning}" if grid_warning else "")
            )
            db.add(log_entry)
            db.commit()
            logger.info(f"[Scheduler] Story #{story_id} publicado com sucesso!")

        except Exception as e:
            error_msg = str(e)
            story.retry_count += 1
            story.error_message = error_msg

            log_entry = StoryLog(
                story_id=story.id,
                attempt_number=story.retry_count,
                status="FAILED",
                message=f"Falha na tentativa {story.retry_count}/3: {error_msg}"
            )
            db.add(log_entry)

            # Lógica de retentativa automática (máximo 3 tentativas) com delay aleatório curto (não fixo)
            if story.retry_count < 3:
                import random
                story.status = "SCHEDULED"
                retry_delay_sec = round(random.uniform(14.0, 26.0) + random.uniform(0.15, 0.85), 2)
                retry_time = datetime.now(APP_TIMEZONE) + timedelta(seconds=retry_delay_sec)
                schedule_story_job(story.id, retry_time)
                logger.warning(
                    f"[Scheduler] Tentativa {story.retry_count} falhou para Story #{story_id}. "
                    f"Nova tentativa agendada para daqui a {retry_delay_sec}s: {error_msg}"
                )
            else:
                story.status = "FAILED"
                logger.error(f"[Scheduler] Story #{story_id} falhou definitivamente após 3 tentativas: {error_msg}")

            db.commit()

    finally:
        db.close()


def reload_pending_jobs():
    """
    Ao iniciar o servidor, busca todos os agendamentos pendentes no SQLite
    e recarrega no APScheduler para evitar perda de tarefas caso o servidor seja reiniciado.
    """
    db: Session = SessionLocal()
    try:
        pending_stories = (
            db.query(ScheduledStory)
            .filter(ScheduledStory.status.in_(["SCHEDULED", "PUBLISHING"]))
            .all()
        )
        now_fortaleza = datetime.now(APP_TIMEZONE)
        count = 0

        for story in pending_stories:
            if story.status == "PUBLISHING":
                story.status = "SCHEDULED"
                db.commit()
            run_time = story.scheduled_time
            if run_time.tzinfo is None:
                run_time = run_time.replace(tzinfo=APP_TIMEZONE)
            else:
                run_time = run_time.astimezone(APP_TIMEZONE)

            if run_time > now_fortaleza:
                # Agendado para o futuro: recarrega normalmente
                schedule_story_job(story.id, run_time)
                count += 1
            else:
                # O horário passou enquanto o servidor estava offline
                diff_minutes = (now_fortaleza - run_time).total_seconds() / 60.0
                if diff_minutes <= 15:
                    # Se atrasou menos de 15 minutos, executa com delay aleatório curto (nunca fixo)
                    import random
                    short_jitter = round(random.uniform(2.2, 5.4) + random.uniform(0.11, 0.49), 2)
                    immediate_time = now_fortaleza + timedelta(seconds=short_jitter)
                    schedule_story_job(story.id, immediate_time)
                    logger.info(f"[Scheduler] Story #{story.id} atrasado por {int(diff_minutes)}m recarregado para execução imediata.")
                    count += 1
                else:
                    story.status = "FAILED"
                    story.error_message = "O horário programado expirou enquanto o servidor estava offline."
                    log_entry = StoryLog(
                        story_id=story.id,
                        attempt_number=1,
                        status="FAILED",
                        message="Não foi possível publicar: servidor estava offline no horário marcado."
                    )
                    db.add(log_entry)
                    db.commit()

        logger.info(f"[Scheduler] {count} agendamento(s) pendente(s) recarregado(s) com sucesso na inicialização.")
    finally:
        db.close()
