@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo Python nao foi encontrado. Instale o Python 3.11 ou superior e tente novamente.
  pause
  exit /b 1
)

if not exist .venv (
  echo Preparando o ambiente local pela primeira vez...
  py -m venv .venv || exit /b 1
)

.venv\Scripts\python -c "import fastapi, pymupdf, markdown_it, docx, reportlab, uvicorn" >nul 2>nul
if errorlevel 1 (
  echo Instalando as dependencias locais...
  .venv\Scripts\pip install -r requirements.txt || exit /b 1
)

start "Resumo Rapido Juridico" /b .venv\Scripts\python -m uvicorn app:app --host 127.0.0.1 --port 8787
timeout /t 2 /nobreak >nul
start "" http://127.0.0.1:8787/
echo Resumo Rapido Juridico aberto. Mantenha esta janela aberta durante o uso.
pause
endlocal
