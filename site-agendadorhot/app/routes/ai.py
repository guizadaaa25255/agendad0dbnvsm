from typing import List, Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field
from app.ai_caption import generate_story_captions

router = APIRouter(prefix="/api/ai", tags=["Inteligência Artificial"])


class GenerateCaptionRequest(BaseModel):
    topic: Optional[str] = Field("", description="Assunto da foto ou vídeo (ex: praia, treino, novidade)")
    tone: Optional[str] = Field("academia", description="academia, praia_piscina, interacao_pv, selfie_beleza, relax_casa, sair_rolê, dia_semana")
    use_emojis: bool = Field(True, description="Incluir emojis na legenda")
    use_hashtags: bool = Field(False, description="Incluir hashtags")
    include_cta: bool = Field(True, description="Incluir pergunta ou chamada para interação")
    scheduled_time: Optional[str] = Field(None, description="Data/hora agendada para capturar o dia correto da semana")


class GenerateCaptionResponse(BaseModel):
    captions: List[str]


@router.post("/generate-captions", response_model=GenerateCaptionResponse)
def generate_captions(payload: GenerateCaptionRequest):
    """Gera 3 opções criativas e naturais de legendas com o dia da semana REAL."""
    captions = generate_story_captions(
        topic=payload.topic,
        tone=payload.tone,
        use_emojis=payload.use_emojis,
        use_hashtags=payload.use_hashtags,
        include_cta=payload.include_cta,
        scheduled_time=payload.scheduled_time
    )
    return GenerateCaptionResponse(captions=captions)
