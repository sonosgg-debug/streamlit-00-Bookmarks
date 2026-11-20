@echo off
setlocal
cd /d "%~dp0"

echo =========================================================
echo   Oracle Cloud Server (168.110.38.90) Code Sync Tool
echo =========================================================
echo.

set "APP_TARGET=%~1"
if "%APP_TARGET%"=="" (
    echo [Usage]
    echo   sync_oracle.bat [app_number or name]
    echo   sync_oracle.bat all
    echo.
    echo [Examples]
    echo   sync_oracle.bat 21
    echo   sync_oracle.bat 28
    echo   sync_oracle.bat 39
    echo   sync_oracle.bat all
    echo.
    set /p "APP_TARGET=Enter app number or name to sync (or 'all'): "
)

if not "%APP_TARGET%"=="" (
    python scripts\sync_to_oracle.py "%APP_TARGET%"
)

echo.
pause
endlocal
