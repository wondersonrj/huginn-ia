@echo off
setlocal
cd /d "%~dp0"
if not exist "runtime\python.exe" (
  echo Pacote incompleto. Extraia todo o ZIP antes de iniciar.
  pause
  exit /b 1
)
if not exist "frontend\dist\index.html" (
  echo Interface ausente. Extraia todo o ZIP antes de iniciar.
  pause
  exit /b 1
)
"%~dp0runtime\python.exe" -I "%~dp0launcher.py"
if errorlevel 1 (
  echo Falha ao iniciar. Confira a mensagem acima. Nenhum dado Oracle foi alterado.
  pause
  exit /b 1
)
endlocal
