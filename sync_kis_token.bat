@echo off
setlocal
cd /d "%~dp0"

echo =========================================================
echo   KIS OpenAPI Token Sync (Oracle Server -> Local PC)
echo =========================================================
echo.

python "scripts\sync_kis_token.py"

echo.
pause
endlocal
