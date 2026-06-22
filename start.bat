@echo off
echo ==========================================
echo       Starting Second Brain OS Server
echo ==========================================
if not exist venv (
    echo Error: Virtual environment 'venv' not found!
    echo Please make sure dependencies are fully installed first.
    pause
    exit /b 1
)
echo Open http://localhost:8000 in your web browser.
echo Press Ctrl+C in this terminal window to stop.
echo ------------------------------------------
venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --app-dir backend --reload
pause
