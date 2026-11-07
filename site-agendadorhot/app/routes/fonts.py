import json
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/fonts", tags=["Custom Fonts"])

FONTS_FILE = Path(__file__).resolve().parent.parent / "custom_fonts.json"

class FormatFontRequest(BaseModel):
    text: str
    font: str = "mfslots"
    spaced: bool = True

ACCENT_MAP = {
    'Á': 'A', 'À': 'A', 'Â': 'A', 'Ä': 'A',
    'É': 'E', 'È': 'E', 'Ê': 'E',
    'Í': 'I', 'Ì': 'I', 'Î': 'I',
    'Ó': 'O', 'Ò': 'O', 'Ô': 'O', 'Ö': 'O',
    'Ú': 'U', 'Ù': 'U', 'Û': 'U', 'Ü': 'U'
}

def _load_fonts() -> Dict[str, Any]:
    if not FONTS_FILE.exists():
        return {}
    with open(FONTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

@router.get("")
def list_fonts():
    """Retorna os 5 estilos de letras 3D oficiais solicitados em ordem com links."""
    fonts = _load_fonts()
    summary = []
    for key, val in fonts.items():
        summary.append({
            "id": key,
            "name": val.get("name", key),
            "label": val.get("label", key),
            "subtitle": val.get("subtitle", ""),
            "short_name": val.get("short_name", ""),
            "url": val.get("url", f"https://t.me/addemoji/{val.get('short_name', '')}"),
            "preview_style": val.get("preview_style", key),
            "available_letters_count": len(val.get("letters", {}))
        })
    return {"fonts": summary}

@router.post("/format")
def format_text(payload: FormatFontRequest):
    """
    Converte o texto fornecido (ex: 'BOA NOITE') no formato com tags <tg-emoji>
    compatível com os Custom Emojis do Telegram Premium para stories.
    """
    fonts = _load_fonts()
    font_data = fonts.get(payload.font)
    if not font_data:
        # Fallback para o primeiro da lista
        if fonts:
            font_data = next(iter(fonts.values()))
        else:
            raise HTTPException(status_code=404, detail="Nenhum pack de fontes configurado.")

    letters_map = font_data.get("letters", {})
    clean_text = payload.text.strip().upper()
    
    if not clean_text:
        return {"html": "", "preview": ""}

    html_parts = []
    preview_parts = []

    words = clean_text.split(" ")
    for w_idx, word in enumerate(words):
        word_html = []
        word_prev = []
        for raw_ch in word:
            # Mapeamento com tolerância a acentos
            ch = raw_ch
            if ch not in letters_map and ch in ACCENT_MAP:
                ch = ACCENT_MAP[ch]

            if ch in letters_map:
                doc_id = letters_map[ch]
                # No Telegram MTProto, o Custom Emoji exige caractere de emoji ('🔤') por baixo para ser aceito
                word_html.append(f'<tg-emoji emoji-id="{doc_id}">🔤</tg-emoji>')
                word_prev.append(raw_ch)
            else:
                word_html.append(raw_ch)
                word_prev.append(raw_ch)
        
        separator = " " if payload.spaced else ""
        html_parts.append(separator.join(word_html))
        preview_parts.append(separator.join(word_prev))

    # Junta as palavras com 3 espaços ou espaço duplo para dar destaque de título
    word_separator = "   " if payload.spaced else " "
    final_html = word_separator.join(html_parts)
    final_preview = word_separator.join(preview_parts)

    return {
        "html": final_html,
        "preview": final_preview,
        "font_label": font_data.get("label", payload.font)
    }
