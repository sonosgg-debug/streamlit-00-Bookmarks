@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo =========================================================
echo   Oracle Cloud Server (168.110.38.90) Code Sync Tool
echo =========================================================
echo.

if "%1"=="" (
    echo [사용법]
    echo   sync_oracle.bat [앱번호 또는 앱이름]
    echo   sync_oracle.bat all
    echo.
    echo [예시]
    echo   sync_oracle.bat 21
    echo   sync_oracle.bat 39
    echo   sync_oracle.bat all
    echo.
    set /p APP_INPUT="동기화할 앱 번호나 이름을 입력하세요 (전체: all): "
    if not "%APP_INPUT%"=="" (
        python scripts\sync_to_oracle.py "%APP_INPUT%"
    )
) else (
    python scripts\sync_to_oracle.py "%1"
)

echo.
pause
