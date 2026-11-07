import os
import sys
import time
import re
import subprocess
import logging
import threading
from pathlib import Path
from urllib.request import urlopen

BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    filename=str(LOG_DIR / "supervisor.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

PYTHON_EXE = sys.executable
CLOUDFLARED_EXE = BASE_DIR / "cloudflared.exe"
DESKTOP_DIR = Path(os.path.expanduser("~")) / "Desktop"


def is_healthy():
    try:
        with urlopen("http://127.0.0.1:8000/api/health", timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def run_cloudflared_forever():
    """Mantém o túnel público Cloudflare ativo para acesso seguro via Safari no celular."""
    if not CLOUDFLARED_EXE.exists():
        logging.warning("cloudflared.exe não encontrado. Túnel externo desativado.")
        return

    logging.info("Iniciando túnel Cloudflare para acesso remoto/celular...")
    while True:
        try:
            cf_proc = subprocess.Popen(
                [str(CLOUDFLARED_EXE), "tunnel", "--url", "http://127.0.0.1:8000"],
                cwd=str(BASE_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace"
            )
            for line in cf_proc.stdout:
                if "trycloudflare.com" in line:
                    match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
                    if match:
                        url = match.group(0)
                        logging.info(f"Link público do Cloudflare gerado: {url}")
                        try:
                            # Salva atalhos na Área de Trabalho para fácil acesso
                            desktop_txt = DESKTOP_DIR / "LINK_ACESSO_CELULAR.txt"
                            desktop_url = DESKTOP_DIR / "Acessar no Celular (Safari).url"

                            content = (
                                "=== COMO ACESSAR NO CELULAR (SAFARI / CHROME) ===\n\n"
                                f"1. LINK SEGURO (Funciona em qualquer lugar: 4G, 5G ou Wi-Fi):\n"
                                f"{url}\n\n"
                                f"2. LINK WI-FI LOCAL (Se o celular estiver no mesmo Wi-Fi do computador):\n"
                                f"http://192.168.1.8:8000\n\n"
                                "Dica no iPhone: Abra o link no Safari, clique no botão Compartilhar e selecione 'Adicionar à Tela de Início' para virar um app no seu celular!\n"
                            )
                            desktop_txt.write_text(content, encoding="utf-8")

                            url_shortcut = f"[InternetShortcut]\r\nURL={url}\r\nIconIndex=0\r\n"
                            desktop_url.write_text(url_shortcut, encoding="utf-8")

                            (LOG_DIR / "public_url.txt").write_text(url, encoding="utf-8")
                        except Exception as err:
                            logging.error(f"Erro ao salvar atalho no Desktop: {err}")
            cf_proc.wait()
        except Exception as e:
            logging.error(f"Erro no cloudflared tunnel: {e}")

        time.sleep(3)


def free_port_8000():
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"],
            capture_output=True,
            timeout=5
        )
    except Exception:
        pass


def run_server_forever():
    logging.info("=== Supervisor do Telegram Story Scheduler Iniciado ===")

    # Inicia o túnel para o celular em background
    threading.Thread(target=run_cloudflared_forever, daemon=True).start()

    env = os.environ.copy()
    env["PYTHONPATH"] = str(BASE_DIR)

    server_log_path = LOG_DIR / "server.log"

    while True:
        logging.info("Iniciando processo Uvicorn...")
        free_port_8000()
        time.sleep(1)

        try:
            with open(server_log_path, "a", encoding="utf-8") as s_log:
                proc = subprocess.Popen(
                    [
                        PYTHON_EXE,
                        "-m",
                        "uvicorn",
                        "app.main:app",
                        "--host",
                        "0.0.0.0",
                        "--port",
                        "8000",
                        "--ws",
                        "auto"
                    ],
                    cwd=str(BASE_DIR),
                    env=env,
                    stdout=s_log,
                    stderr=subprocess.STDOUT
                )
            logging.info(f"Processo Uvicorn iniciado com PID: {proc.pid}")

            time.sleep(3)

            consecutive_failures = 0
            while proc.poll() is None:
                time.sleep(10)
                if not is_healthy():
                    consecutive_failures += 1
                    logging.warning(f"Health check falhou ({consecutive_failures}/3)")
                    if consecutive_failures >= 3:
                        logging.error("Servidor travou (3 falhas consecutivas). Reiniciando...")
                        proc.terminate()
                        try:
                            proc.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                        break
                else:
                    consecutive_failures = 0

            return_code = proc.poll()
            logging.warning(f"Uvicorn encerrou com código {return_code}. Reiniciando em 2 segundos...")
        except Exception as e:
            logging.error(f"Erro no supervisor: {e}")

        time.sleep(2)


if __name__ == "__main__":
    run_server_forever()
