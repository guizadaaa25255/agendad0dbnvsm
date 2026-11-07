import os
import io
import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from app.config import APP_TIMEZONE
from app.database import SessionLocal
from app.models import ScheduledStory, StoryLog
from app.scheduler import schedule_story_job, execute_story_publish, scheduler


@pytest.mark.asyncio
async def test_schedule_story_2_minutes_with_pinned():
    """
    Simula o fluxo completo exigido no item 4:
    - Agendar um story para daqui a 2 minutos
    - Opção de fixar no perfil (pinned=True) ativada
    - Confirmar que foi publicado automaticamente no horário com sucesso
    """
    db = SessionLocal()
    story_id = None

    try:
        if not scheduler.running:
            scheduler.start()

        # 1. Criação do story programado para exatamente daqui a 2 minutos
        now_fortaleza = datetime.now(APP_TIMEZONE)
        scheduled_for_2min = now_fortaleza + timedelta(minutes=2)

        test_media_path = os.path.abspath("test_simulated_story.jpg")
        with open(test_media_path, "wb") as f:
            f.write(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C")

        story = ScheduledStory(
            media_path=test_media_path,
            media_type="photo",
            caption="Story teste 2 minutos com pinned=True",
            scheduled_time=scheduled_for_2min,
            period=172800,  # 48h Premium
            pinned=True,    # Fixado no perfil ativado!
            privacy="all",
            status="SCHEDULED",
            retry_count=0
        )
        db.add(story)
        db.commit()
        db.refresh(story)
        story_id = story.id

        # 2. Registra no agendador APScheduler
        schedule_story_job(story.id, scheduled_for_2min)

        # Confirma que o job está na fila do APScheduler
        job = scheduler.get_job(f"story_{story.id}")
        assert job is not None
        assert abs((job.next_run_time - scheduled_for_2min).total_seconds()) < 5

        # 3. Disparo da publicação simulando o momento exato em que o timer atinge os 2 minutos
        with patch("app.scheduler.publish_story_to_telegram", new_callable=AsyncMock) as mock_pub:
            # Configura mock para simular retorno com sucesso da API do Telegram
            mock_pub.return_value = 123456789

            # Executa a publicação agendada
            await execute_story_publish(story.id)

            # 4. Verificações no banco de dados
            db.refresh(story)

            # Confirma que o story foi publicado
            assert story.status == "PUBLISHED"
            assert story.pinned is True
            assert story.period == 172800
            assert story.telegram_story_id == 123456789
            assert story.published_at is not None
            assert story.error_message is None

            # Confirma chamada correta ao publicador MTProto
            assert mock_pub.call_count == 1
            call_story = mock_pub.call_args[0][1]
            assert call_story.pinned is True
            assert call_story.period == 172800
            assert call_story.id == story_id

            # Confirma gravação do log de auditoria
            logs = db.query(StoryLog).filter(StoryLog.story_id == story_id).all()
            assert len(logs) >= 1
            success_log = [l for l in logs if l.status == "SUCCESS"]
            assert len(success_log) == 1
            assert "123456789" in success_log[0].message

    finally:
        # Limpeza
        if os.path.exists("test_simulated_story.jpg"):
            os.remove("test_simulated_story.jpg")
        if story_id:
            db.query(StoryLog).filter(StoryLog.story_id == story_id).delete()
            db.query(ScheduledStory).filter(ScheduledStory.id == story_id).delete()
            db.commit()
        db.close()
