@echo off
setlocal
title HUGINN - Diagnostico HTTPS
set "PSModulePath=%SystemRoot%\System32\WindowsPowerShell\v1.0\Modules;%ProgramFiles%\WindowsPowerShell\Modules"
powershell.exe -NoProfile -File "%~dp0Test-HuginnCloud.ps1"
echo.
echo Diagnostico concluido. Nenhuma configuracao de rede foi alterada.
pause
endlocal
