@echo off
title Kiara Cloudflare Tunnel (Port 8000)
cd /d "%~dp0"

set "PATH=C:\Program Files (x86)\cloudflared;%PATH%"

echo ========================================================
echo   Kiara - Cloudflare Tunnel Publico
echo ========================================================
echo.
echo Iniciando tunel seguro HTTPS para a API local (porta 8000)...
echo Copie o link HTTPS exibido abaixo (ex: https://xxxx.trycloudflare.com)
echo e configure na Vercel como KIARA_API_URL.
echo.
echo ========================================================
echo.

"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://127.0.0.1:8000
pause
