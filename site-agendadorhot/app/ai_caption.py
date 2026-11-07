import os
import random
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List, Optional

TIMEZONE = ZoneInfo("America/Fortaleza")

DIAS_CONFIG = {
    0: {"nome": "segunda", "nome_completo": "segunda-feira", "giria": "segundou"},
    1: {"nome": "terça", "nome_completo": "terça-feira", "giria": "terçou"},
    2: {"nome": "quarta", "nome_completo": "quarta-feira", "giria": "quartou"},
    3: {"nome": "quinta", "nome_completo": "quinta-feira", "giria": "quintou"},
    4: {"nome": "sexta", "nome_completo": "sexta-feira", "giria": "sextou"},
    5: {"nome": "sábado", "nome_completo": "sábado", "giria": "sabadão"},
    6: {"nome": "domingo", "nome_completo": "domingo", "giria": "domingou"},
}


def get_current_day_info(scheduled_time_str: Optional[str] = None):
    """
    Pega o dia da semana e o período do dia (manhã/tarde/noite) no fuso de Fortaleza,
    respeitando a linha do tempo real ou a data agendada.
    """
    now = datetime.now(TIMEZONE)
    if scheduled_time_str:
        try:
            clean_str = scheduled_time_str.replace("Z", "").replace(" ", "T")
            dt = datetime.fromisoformat(clean_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=TIMEZONE)
            now = dt
        except Exception:
            pass

    hour = now.hour
    if 5 <= hour < 12:
        periodo = "manha"
        periodo_nome = "manhã"
        saudacao = "Bom dia"
        saudacao_casual = "Boom dia"
        saudacao_alta = "BOM DIA"
    elif 12 <= hour < 18:
        periodo = "tarde"
        periodo_nome = "tarde"
        saudacao = "Boa tarde"
        saudacao_casual = "Boaa tarde"
        saudacao_alta = "BOA TARDE"
    else:
        periodo = "noite"
        periodo_nome = "noite"
        saudacao = "Boa noite"
        saudacao_casual = "Boaa noite"
        saudacao_alta = "BOA NOITE"

    day_idx = now.weekday()
    base = DIAS_CONFIG.get(day_idx, DIAS_CONFIG[0])

    return {
        "nome": base["nome"],
        "nome_completo": base["nome_completo"],
        "giria": base["giria"],
        "periodo": periodo,
        "periodo_nome": periodo_nome,
        "saudacao": saudacao,
        "saudacao_casual": saudacao_casual,
        "saudacao_alta": saudacao_alta,
        "now": now
    }


def get_context_templates(day_info):
    dia_nome = day_info["nome"]
    dia_giria = day_info["giria"]
    dia_completo = day_info["nome_completo"]
    saudacao = day_info["saudacao"]
    saudacao_casual = day_info["saudacao_casual"]
    saudacao_alta = day_info["saudacao_alta"]
    periodo = day_info["periodo"]

    # Frases do dia da semana calibradas dinamicamente com o período real:
    if dia_nome == "domingo":
        dia_semana_frases = [
            f"{saudacao} 💗 Final de Domingo é minha felicidade indo embora 😂😅" if periodo == "noite" else f"{saudacao_casual} mores, domingão delícia! 🌞✨",
            "Domingou bem tranquilinha hj! ✨📍",
            "Deitadinha hoje RS bem tranquilinha domingo 😴🤍",
            "Domingão de paz e preguiça né rs ☕🛋️",
            f"Aproveitando o finzinho do fim de semana né mores 🥰✨" if periodo == "noite" else "Aproveitando esse domingão lindo né mores 🥰✨"
        ]
    elif dia_nome == "sexta":
        dia_semana_frases = [
            f"{saudacao_casual} mores, sextou né 😘🙈",
            "Sextouu com S de saudade de sair né kkkk 🍸✨",
            "Sextinha chegou do jeito que eu amo! 💃💋",
            f"{saudacao_casual} né, hoje é aonde? Kkkk 😋🤗",
            f"Ótima {dia_completo}! 🥰 Pv liberado"
        ]
    else:
        dia_semana_frases = [
            f"{saudacao_casual} mores, {dia_giria} né 😘🙈",
            f"{dia_giria.capitalize()} por aqui com foco total! 💪✨",
            f"Ótima {dia_completo}! 🥰 Pv liberado",
            f"Começando a semana bem tranquilinha hj! 🌞📍" if (dia_nome == "segunda" and periodo == "manha") else f"{saudacao} por aqui bem tranquilinha hj! ✨📍",
            f"{dia_giria.capitalize()} braba mas o de hoje tá pago! 💪💋"
        ]

    return {
        "academia": [
            f"{saudacao}, O de hoje tá pago! 💪💋",
            f"{saudacao_casual}, Treininho leve de {dia_nome} neh 💪🤗",
            "O cárdio que eu queria hj nn era esse kkkk 🤔😂",
            "Cansadinha hoje, mas tem que ter persistência né rs 💪✨",
            f"{dia_giria.capitalize()} e o treino tá mais que pago! 🏋️‍♀️🔥",
            "Pagando o de hoje, quem já treinou aí? 🏃‍♀️💪",
            "Endorfina liberada com sucesso! 💦💋",
            "Mortinha com farofa mas tá pago! Kkkk 🥵💪",
            f"Aquele treininho pra fechar bem a {day_info['periodo_nome']}! 👊✨" if periodo == "noite" else "Aquele treininho pra começar bem o dia! 👊✨",
            "Firme no propósito né rs 💪💅"
        ],
        "praia_piscina": [
            "Dia de praia! 🏖✨🤭",
            "Piscininha hoje do jeito que eu gosto ☀️💦",
            f"Aproveitando essa {dia_nome} nesse solzão! 🌞👙",
            "Vitamina D em dia né mores 🌊✨",
            "Solzinho delícia por aqui hoje! ☀️🌴",
            "Dia de mar e paz no coração 🏖🐚💕",
            "Pegando aquela corzinha delícia! 👙☀️",
            "A vibe de hoje tá perfeita demais 🍹🌊"
        ],
        "relax_casa": [
            f"{saudacao_alta}! Bem tranquilinha hj! ✨📍",
            "Deitadinha hoje RS bem tranquilinha 😴🤍",
            f"Preguicinha boa de {dia_nome} né rs ☕🛋️",
            "Dia de descanso bem merecido! 🛌✨",
            "Mood de hoje: paz e sossego 🕯️🤍",
            "Ficando em casa quietinha hoje 🥰🎬",
            "Quartinho, cobertor e descanso... quer mais nada rs 🍿✨"
        ],
        "selfie_beleza": [
            "Tô me sentindo bonita hj KKK tbm acha? 😂💋😊",
            "Mais arrumadinha hj né rs 💕💅",
            "Aquele biscoitinho de leve pro feed de vocês 🍪🤭",
            "Gostei dessa foto, vai ter que aguentar rs 📸💋",
            f"Lookinho de {dia_nome}! O que acharam? 🥰✨",
            "Quem é essa garota ein kkkk 🙈✨",
            "Só pra registrar o momento 👗💋"
        ],
        "interacao_pv": [
            f"Ótima {dia_completo}! 🥰 Pv liberado",
            f"{saudacao}! 💕 PV LIBERADO",
            f"PV liberado nessa {dia_nome} mores, quem vem conversar? 🙈💬",
            "Tô no pv hoje ein... vem! 💌💋",
            "Respondendo vocês por aqui, manda uma mensagem! 💬✨",
            "Vem de pv puxar assunto comigo hoje 💕👇"
        ],
        "sair_rolê": [
            f"{saudacao_casual} né, {dia_nome} hoje e aonde? Kkkk 😋🤗",
            f"{saudacao_casual} mores, {dia_giria} né 😘🙈",
            f"{dia_giria.capitalize()} com estilo! Quem anima sair? 🍸✨",
            "Prontinha pra dar uma voltinha hoje 👠💃",
            "Partiu curtir né mores? 🥂✨"
        ],
        "dia_semana": dia_semana_frases
    }


KEYWORDS_MAP = {
    "academia": ["academia", "treino", "treininho", "gym", "cardio", "cárdio", "peso", "leg", "musculação", "suor", "fitness", "foco", "biceps", "gluteo", "perna"],
    "praia_piscina": ["praia", "mar", "sol", "piscina", "biquini", "biquíni", "marquinha", "areia", "verão", "bronze", "ferias", "água"],
    "relax_casa": ["cama", "deitada", "deitadinha", "casa", "preguiça", "sofa", "sofá", "tranquila", "tranquilinha", "filme", "descanso"],
    "selfie_beleza": ["rosto", "make", "maquiagem", "cabelo", "bonita", "linda", "look", "lookinho", "espelho", "selfie", "arrumada"],
    "interacao_pv": ["pv", "conversa", "chat", "direct", "pergunta", "falar", "liberado", "pvd"],
    "sair_rolê": ["festa", "balada", "rolê", "role", "bar", "chopp", "sexta", "sabado", "sabadão", "noite", "drinks", "sair"]
}


def detect_context_from_keywords(text: str) -> str:
    """Detecta o tema/contexto com base no texto ou tags informadas."""
    t = text.lower()
    for category, words in KEYWORDS_MAP.items():
        for w in words:
            if w in t:
                return category
    return "geral"


def analyze_image_heuristics(image_path: str) -> str:
    """
    Lê a imagem enviada para identificar se é academia, praia, casa ou selfie.
    """
    if not image_path or not os.path.exists(image_path):
        return "geral"

    try:
        from PIL import Image, ImageStat
        with Image.open(image_path) as img:
            img_rgb = img.convert("RGB")
            small = img_rgb.resize((50, 50))
            stat = ImageStat.Stat(small)
            r, g, b = stat.mean[:3]

            if b > r + 15 and b > g and (r + g + b) > 360:
                return "praia_piscina"

            if (r + g + b) < 220:
                return "academia"

            if r > b + 20:
                return "selfie_beleza"
    except Exception:
        pass

    return "geral"


def generate_story_captions(
    topic: Optional[str] = "",
    tone: Optional[str] = "academia",
    use_emojis: bool = True,
    use_hashtags: bool = False,
    include_cta: bool = True,
    image_path: Optional[str] = None,
    scheduled_time: Optional[str] = None
) -> List[str]:
    """
    Gera legendas calibradas com o dia da semana REAL e o período do dia REAL
    (Bom dia pela manhã, Boa tarde à tarde, Boa noite à noite).
    """
    day_info = get_current_day_info(scheduled_time)
    templates = get_context_templates(day_info)

    detected_cat = "geral"

    if topic and topic.strip():
        detected_cat = detect_context_from_keywords(topic)

    if detected_cat == "geral" and image_path:
        detected_cat = analyze_image_heuristics(image_path)

    if detected_cat == "geral":
        if tone in templates:
            detected_cat = tone
        elif tone == "lifestyle":
            detected_cat = "relax_casa"
        elif tone == "funny":
            detected_cat = "academia"
        else:
            detected_cat = "selfie_beleza"

    primary_pool = templates.get(detected_cat, templates["selfie_beleza"]).copy()
    random.shuffle(primary_pool)

    # Pool de dia da semana atual
    day_pool = templates["dia_semana"].copy()
    random.shuffle(day_pool)

    other_cats = [c for c in templates.keys() if c not in (detected_cat, "dia_semana")]
    random.shuffle(other_cats)
    sec_pool = templates[other_cats[0]].copy()
    random.shuffle(sec_pool)

    # Opção 1: contextual
    op1 = primary_pool[0] if len(primary_pool) > 0 else day_pool[0]
    # Opção 2: com o dia da semana real (ex: segunda, segundona)
    op2 = day_pool[0] if day_pool[0] != op1 else (day_pool[1] if len(day_pool) > 1 else primary_pool[1])
    # Opção 3: variação secundária
    op3 = sec_pool[0] if sec_pool[0] not in (op1, op2) else (primary_pool[2] if len(primary_pool) > 2 else "Tô me sentindo bonita hj KKK tbm acha? 😂💋😊")

    # Se a usuária digitou algo específico no tópico:
    if topic and topic.strip():
        clean_top = topic.strip()
        top_lower = clean_top.lower()
        if any(w in top_lower for w in ["trein", "acad", "perna", "gluteo", "braço", "costas", "cardio"]):
            op1 = f"{day_info['saudacao']}, {clean_top.lower()} pago! 💪💋"
        elif any(w in top_lower for w in ["praia", "mar", "sol", "piscina", "bronze"]):
            op1 = f"Dia de {clean_top.lower()}! 🏖✨🤭"
        elif any(w in top_lower for w in ["casa", "cama", "preguiça", "deitada"]):
            op1 = f"{clean_top.capitalize()} hoje RS bem tranquilinha 😴🤍"
        elif any(w in top_lower for w in ["pv", "direct", "conversa"]):
            op1 = f"Ótima {day_info['nome_completo']}! 🥰 Pv liberado"
        else:
            op1 = f"{day_info['saudacao_casual']} né, {clean_top.lower()} de {day_info['nome']}? Kkkk 😋🤗"

    raw_candidates = [op1, op2, op3]
    results = []
    seen = set()

    for c in raw_candidates:
        text = c.strip()
        if not use_emojis:
            text = re.sub(r'[\U00010000-\U0010ffff]', '', text)
            text = re.sub(r'[✨🔥💬👀❤️💭☀️🌿☕💫🦋🌸🖤🌙⚡🌟📌💌🤡💸💅🙃🙋‍♂️💆‍♀️🔮💣⏳👇✍️🏖🤭🥰😂💋😊💪😋🌴🤍🌊👙🛋️🍿🎬👗🍪🏃‍♀️🥵👊]', '', text)
            text = " ".join(text.split())

        if use_hashtags:
            text += f" #{day_info['nome']}"

        if text not in seen:
            seen.add(text)
            results.append(text)

    while len(results) < 3:
        fallback = random.choice(day_pool)
        if fallback not in results:
            results.append(fallback)
        else:
            results.append(f"{fallback} ✨")

    return results[:3]
