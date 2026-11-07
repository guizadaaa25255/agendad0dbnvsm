import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from app.config import APP_TIMEZONE
from app.database import SessionLocal
from app.models import ScheduledStory, StoryLog
from app.scheduler import execute_story_publish, reload_pending_jobs, scheduler


@pytest.mark.asyncio
async def test_scheduler_publish_success():
    db = SessionLocal()
    story_id = None
    try:
        story = ScheduledStory(
            media_path="fake_path.jpg",
            media_type="photo",
            caption="Test story success",
            scheduled_time=datetime.now(APP_TIMEZONE) + timedelta(minutes=1),
            period=86400,
            pinned=True,
            privacy="all",
            status="SCHEDULED"
        )
        db.add(story)
        db.commit()
        db.refresh(story)
        story_id = story.id

        # Simula publicação bem-sucedida no Telegram
        with patch("app.scheduler.publish_story_to_telegram", new_callable=AsyncMock) as mock_pub:
            mock_pub.return_value = 998877

            await execute_story_publish(story_id)

            db.refresh(story)
            assert story.status == "PUBLISHED"
            assert story.telegram_story_id == 998877
            assert story.published_at is not None

            # Verifica log gravado
            logs = db.query(StoryLog).filter(StoryLog.story_id == story_id).all()
            assert any(l.status == "SUCCESS" and "998877" in l.message for l in logs)

    finally:
        if story_id:
            db.query(StoryLog).filter(StoryLog.story_id == story_id).delete()
            db.query(ScheduledStory).filter(ScheduledStory.id == story_id).delete()
            db.commit()
        db.close()


@pytest.mark.asyncio
async def test_scheduler_retry_mechanism_and_max_failures():
    db = SessionLocal()
    story_id = None
    try:
        story = ScheduledStory(
            media_path="fake_path.jpg",
            media_type="photo",
            caption="Test retry story",
            scheduled_time=datetime.now(APP_TIMEZONE) + timedelta(minutes=1),
            period=86400,
            pinned=False,
            privacy="all",
            status="SCHEDULED",
            retry_count=0
        )
        db.add(story)
        db.commit()
        db.refresh(story)
        story_id = story.id

        # Falha 1
        with patch("app.scheduler.publish_story_to_telegram", side_effect=RuntimeError("Simulated Telegram error 1")):
            await execute_story_publish(story_id)
            db.refresh(story)
            assert story.status == "SCHEDULED"
            assert story.retry_count == 1

        # Falha 2
        with patch("app.scheduler.publish_story_to_telegram", side_effect=RuntimeError("Simulated Telegram error 2")):
            await execute_story_publish(story_id)
            db.refresh(story)
            assert story.status == "SCHEDULED"
            assert story.retry_count == 2

        # Falha 3 (atinge o limite de 3 tentativas)
        with patch("app.scheduler.publish_story_to_telegram", side_effect=RuntimeError("Simulated Telegram error 3")):
            await execute_story_publish(story_id)
            db.refresh(story)
            assert story.status == "FAILED"
            assert story.retry_count == 3
            assert "Simulated Telegram error 3" in story.error_message

            logs = db.query(StoryLog).filter(StoryLog.story_id == story_id).all()
            assert len(logs) == 3

    finally:
        if story_id:
            db.query(StoryLog).filter(StoryLog.story_id == story_id).delete()
            db.query(ScheduledStory).filter(ScheduledStory.id == story_id).delete()
            db.commit()
        db.close()


@pytest.mark.asyncio
async def test_reload_pending_jobs():
    db = SessionLocal()
    future_id = None
    try:
        future_story = ScheduledStory(
            media_path="test.jpg",
            media_type="photo",
            caption="Story futuro para recarga",
            scheduled_time=datetime.now(APP_TIMEZONE) + timedelta(hours=2),
            period=86400,
            pinned=True,
            status="SCHEDULED"
        )
        db.add(future_story)
        db.commit()
        db.refresh(future_story)
        future_id = future_story.id

        if not scheduler.running:
            scheduler.start()

        reload_pending_jobs()

        job = scheduler.get_job(f"story_{future_story.id}")
        assert job is not None

    finally:
        if future_id:
            db.query(ScheduledStory).filter(ScheduledStory.id == future_id).delete()
            db.commit()
        db.close()
