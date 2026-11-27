@echo off
setlocal
cd /d "%~dp0"

echo =========================================================
echo   KRX Market Cache DB Sync (Oracle Server -> Local PC)
echo =========================================================
echo.

python "scripts\sync_krx_db.py"

echo.
pause
endlocal
