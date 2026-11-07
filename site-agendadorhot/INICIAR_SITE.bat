@echo off
title Telegram Story Scheduler - Servidor
cd /d "C:\Users\Administrator\.gemini\antigravity\scratch\telegram-story-scheduler"
echo ====================================================
echo   TELEGRAM STORY SCHEDULER - SERVIDOR EM EXECUCAO
echo   Acesse: http://127.0.0.1:8000
echo ====================================================
:loop
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
echo O servidor parou. Reiniciando em 2 segundos...
timeout /t 2 /nobreak >nul
goto loop
