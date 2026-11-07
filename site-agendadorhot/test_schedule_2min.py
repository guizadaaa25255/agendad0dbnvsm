"""
Script de Teste Automatizado do Fluxo Completo:
- Agenda um story para exatamente 2 minutos a partir de agora (America/Fortaleza)
- Ativa a opção de fixar no perfil (pinned=True) e duração de 48h (Premium)
- Monitora os logs em tempo real até a publicação ser concluída
"""

import sys
import time
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BASE_URL = "http://localhost:8000"
TIMEZONE = ZoneInfo("America/Fortaleza")


def create_sample_story_image(file_path: Path):
    """Gera uma imagem de teste 1080x1920 (proporção 9:16 padrão de Stories)."""
    img = Image.new("RGB", (1080, 1920), color=(17, 24, 39))
    draw = ImageDraw.Draw(img)

    # Gradiente ou faixas decorativas
    draw.rectangle([(60, 60), (1020, 1860)], outline=(14, 165, 233), width=6)
    draw.rectangle([(100, 100), (980, 300)], fill=(30, 41, 59))

    # Textos na imagem
    draw.text((140, 160), "TELEGRAM STORY SCHEDULER", fill=(56, 189, 248))
    draw.text((140, 220), "Publicacao Automatica via MTProto", fill=(203, 213, 225))
    draw.text((140, 400), "Story Agendado para 2 minutos", fill=(255, 255, 255))
    draw.text((140, 460), "Opcao: Fixar no Perfil (pinned=True)", fill=(245, 158, 11))
    draw.text((140, 520), f"Data/Hora: {datetime.now(TIMEZONE).strftime('%d/%m/%Y %H:%M:%S')}", fill=(148, 163, 184))

    img.save(file_path, "JPEG", quality=90)


def main():
    print("=" * 60)
    print(" TELEGRAM STORY SCHEDULER - TESTE DE AGENDAMENTO (2 MINUTOS)")
    print("=" * 60)

    # 1. Verifica integridade do servidor
    try:
        r = requests.get(f"{BASE_URL}/api/health", timeout=5)
        if r.status_code != 200:
            print("[ERRO] O servidor nao respondeu corretamente.")
            sys.exit(1)
        health = r.json()
        print(f"[OK] Servidor ativo em {BASE_URL}")
        print(f"[OK] Fuso horario: {health['timezone']} | Hora atual: {health['current_time']}")
    except Exception as e:
        print(f"[ERRO] Nao foi possivel conectar ao servidor em {BASE_URL}.")
        print("Certifique-se de que o servidor esta rodando com: uvicorn app.main:app --reload")
        sys.exit(1)

    # 2. Verifica status da conta do Telegram
    r = requests.get(f"{BASE_URL}/api/auth/status")
    auth_data = r.json()
    if not auth_data.get("connected"):
        print("\n[AVISO] Nenhuma conta do Telegram conectada ainda!")
        print(f"Abra o navegador em {BASE_URL} e clique em 'Conectar Conta' para fazer login.")
        print("Apos conectar sua conta, execute este script novamente.")
        sys.exit(0)

    account = auth_data["accounts"][0]  # use --account <id> para escolher outra
    if len(sys.argv) > 2 and sys.argv[1] == "--account":
        account = next((a for a in auth_data["accounts"] if str(a["id"]) == sys.argv[2]), account)
    print(f"[OK] Conta Telegram: {account.get('first_name')} ({account.get('phone')}) id={account['id']}")
    if account.get("is_premium"):
        print("[OK] Conta possui Telegram Premium ativo! (Opcao de 48h habilitada)")

    # 3. Calcula o horário para exatamente 2 minutos à frente
    now = datetime.now(TIMEZONE)
    scheduled_dt = now + timedelta(minutes=2)
    scheduled_iso = scheduled_dt.strftime("%Y-%m-%dT%H:%M:%S")

    print(f"\n[1/3] Gerando imagem de teste do story...")
    temp_img_path = Path("sample_test_story.jpg")
    create_sample_story_image(temp_img_path)

    print(f"[2/3] Agendando story para {scheduled_dt.strftime('%d/%m/%Y as %H:%M:%S')} (America/Fortaleza)...")
    print("      - Duracao: 48 horas (172800s)")
    print("      - Fixar no perfil (pinned): SIM (pinned=True)")
    print("      - Privacidade: Todos (all)")

    with open(temp_img_path, "rb") as f:
        files = {"file": ("sample_test_story.jpg", f, "image/jpeg")}
        data = {
            "account_id": account["id"],
            "scheduled_time": scheduled_iso,
            "period": 172800,  # 48h
            "pinned": "true",
            "privacy": "all",
            "caption": "Story agendado automaticamente via Telegram Story Scheduler! 🚀 #TelegramStories #AutoPublish"
        }
        res = requests.post(f"{BASE_URL}/api/stories", data=data, files=files)

    if res.status_code != 201:
        print(f"[ERRO] Falha ao agendar: {res.text}")
        if temp_img_path.exists():
            temp_img_path.unlink()
        sys.exit(1)

    story = res.json()
    story_id = story["id"]
    print(f"[OK] Story #{story_id} criado com sucesso e agendado no APScheduler!")

    print(f"\n[3/3] Aguardando publicacao automatica (disparo em ~2 minutos)...")
    print("Pressione Ctrl+C para interromper o monitoramento (o agendamento continuara no servidor).")

    # Monitora até a publicação
    try:
        while True:
            time.sleep(5)
            chk = requests.get(f"{BASE_URL}/api/stories/{story_id}").json()
            status = chk.get("status")
            retry_count = chk.get("retry_count", 0)

            now_str = datetime.now(TIMEZONE).strftime("%H:%M:%S")
            print(f"[{now_str}] Status atual: {status} (Tentativas: {retry_count}/3)")

            if status == "PUBLISHED":
                print("\n" + "=" * 60)
                print(f" SUCESSO! O Story #{story_id} foi publicado automaticamente!")
                print(f" ID no Telegram: {chk.get('telegram_story_id')}")
                print(f" Fixado no perfil: {chk.get('pinned')}")
                print(f" Publicado em: {chk.get('published_at')}")
                print("=" * 60)
                break
            elif status == "FAILED":
                print("\n" + "=" * 60)
                print(f" [FALHA] O Story #{story_id} falhou apos retentativas.")
                print(f" Mensagem de erro: {chk.get('error_message')}")
                print("=" * 60)
                break
    except KeyboardInterrupt:
        print("\nMonitoramento encerrado. O story continuara sendo gerenciado pelo servidor.")
    finally:
        if temp_img_path.exists():
            temp_img_path.unlink()


if __name__ == "__main__":
    main()
