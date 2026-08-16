@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Virtual environment not found. Run setup_windows.bat first.
  pause
  exit /b 1
)
start "MATTERS Backend" cmd /k "%~dp0run_backend.bat"
start "MATTERS UI" cmd /k "%~dp0run_ui.bat"
timeout /t 2 /nobreak >nul
start "" http://127.0.0.1:5500/MATTERS.htm
