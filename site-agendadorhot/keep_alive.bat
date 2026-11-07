@echo off
cd /d "C:\Users\Administrator\.gemini\antigravity\scratch\telegram-story-scheduler"
:loop
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 >> server.log 2>&1
timeout /t 2 /nobreak >nul
goto loop
