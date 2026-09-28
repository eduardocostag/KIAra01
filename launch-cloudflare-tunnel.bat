@echo off
title Kiara Cloudflare Tunnel (Port 8000)
cd /d "%~dp0"

set "PATH=C:\Program Files (x86)\cloudflared;%PATH%"

echo ========================================================
echo   Kiara - Cloudflare Tunnel Publico
echo ========================================================
echo.
echo Iniciando tunel seguro HTTPS para a API local (porta 8000)...
echo.
echo ATENCAO: este e um Quick Tunnel temporario e pode expirar sem aviso.
echo Quando a URL mudar, configure na Vercel:
echo   KIARA_COMPETITION_API_URL=https://xxxx.trycloudflare.com
echo Depois, faca um novo deploy de producao do site.
echo Nao altere KIARA_API_URL: ela pertence ao backend principal.
echo.
echo Para producao estavel, substitua este Quick Tunnel por um tunel
 echo nomeado com dominio fixo ou hospede a API em infraestrutura permanente.
echo.
echo ========================================================
echo.

"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://127.0.0.1:8000
pause
