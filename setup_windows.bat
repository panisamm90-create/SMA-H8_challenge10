@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if not errorlevel 1 (
  set "PY_CMD=py -3"
) else (
  set "PY_CMD=python"
)

echo [MATTERS] Checking Python version...
%PY_CMD% -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)"
if errorlevel 1 (
  echo.
  echo ERROR: Python 3.11 or newer is required.
  echo Install Python 3.11, 3.12, or 3.13 and run this file again.
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [MATTERS] Creating virtual environment...
  %PY_CMD% -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if not exist ".env" (
  copy /Y .env.example .env >nul
  echo.
  echo [MATTERS] Created .env from .env.example.
  echo Add at least ORS_API_KEY before route analysis.
)

echo.
echo [MATTERS] Setup complete.
echo Run verify_setup.py to check the environment.
echo Run run_all.bat to start the project.
endlocal
