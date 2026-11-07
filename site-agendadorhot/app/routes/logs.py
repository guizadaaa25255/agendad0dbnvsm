from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.config import APP_TIMEZONE
from app.database import get_db
from app.models import StoryLog
from app.schemas import StoryLogResponse

router = APIRouter(prefix="/api/logs", tags=["Logs"])


@router.get("", response_model=List[StoryLogResponse])
def list_logs(limit: int = Query(50, le=200), db: Session = Depends(get_db)):
    """Lista os logs mais recentes de tentativas de publicação de stories."""
    logs = db.query(StoryLog).order_by(StoryLog.created_at.desc()).limit(limit).all()
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
