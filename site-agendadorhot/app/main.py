import os
from datetime import datetime
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.config import (
    APP_TIMEZONE,
    TIMEZONE_STR,
    UPLOAD_DIR,
    BASE_DIR
)
from app.database import init_db
from app.scheduler import scheduler, reload_pending_jobs
from app.routes import auth, stories, logs, ai, fonts


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida da aplicação: inicializa banco, agenda tarefas e desliga com segurança."""
    # 1. Cria as tabelas do banco de dados SQLite caso não existam
    init_db()

    # 2. Inicia o APScheduler
    scheduler.start()

    # 3. Recarrega agendamentos pendentes do SQLite
    reload_pending_jobs()

    yield

    # Encerramento gracioso do agendador
    if scheduler.running:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="Telegram Story Scheduler",
    description="Sistema automatizado de agendamento e publicação de Stories no Telegram via MTProto",
    version="1.0.0",
    lifespan=lifespan
)

# Configuração de CORS para permitir requisições locais fluidas
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclusão dos roteadores da API
app.include_router(auth.router)
app.include_router(stories.router)
app.include_router(logs.router)
app.include_router(ai.router)
app.include_router(fonts.router)

# Diretórios estáticos e de mídia
STATIC_DIR = BASE_DIR / "app" / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/media", StaticFiles(directory=str(UPLOAD_DIR)), name="media")


@app.get("/api/health")
def health_check():
    """Endpoint de verificação de integridade e hora atual no fuso de Fortaleza."""
    now_fortaleza = datetime.now(APP_TIMEZONE)
    return {
        "status": "healthy",
        "timezone": TIMEZONE_STR,
        "current_time": now_fortaleza.strftime("%Y-%m-%d %H:%M:%S"),
        "scheduler_running": scheduler.running
    }


@app.websocket("/ws/admin")
async def dummy_ws_admin(websocket: WebSocket):
    """Trata conexões WebSocket de abas secundárias sem derrubar a aplicação."""
    try:
        await websocket.accept()
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, Exception):
        pass


@app.get("/ws/admin")
def dummy_get_admin():
    return {"status": "ok"}


@app.get("/")
def serve_index():
    """Serve a aplicação web frontend."""
    index_path = STATIC_DIR / "index.html"
    return FileResponse(str(index_path))


if __name__ == "__main__":
    import uvicorn
    from app.config import HOST, PORT
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
