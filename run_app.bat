@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo ===================================================
echo   투자 게이트웨이 북마크 앱 (로컬 실행기)
echo ===================================================
echo.

REM 가상환경(.venv 또는 venv)이 존재하는 경우 자동 활성화
if exist ".venv\Scripts\activate.bat" (
    echo [가상환경] .venv 활성화 중...
    call ".venv\Scripts\activate.bat"
) else if exist "venv\Scripts\activate.bat" (
    echo [가상환경] venv 활성화 중...
    call "venv\Scripts\activate.bat"
)

REM Python 설치 여부 확인
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [오류] Python이 시스템에 설치되어 있지 않거나 PATH 환경 변수에 등록되어 있지 않습니다.
    echo Python을 설치하거나 환경 변수를 확인해 주세요.
    echo.
    pause
    exit /b 1
)

REM Streamlit 설치 여부 확인 및 미설치 시 자동 설치
python -m streamlit --version >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [알림] Streamlit이 설치되어 있지 않습니다.
    echo 필수 패키지 설치를 진행합니다 [requirements.txt]...
    echo.
    pip install -r requirements.txt
    if %ERRORLEVEL% neq 0 (
        echo.
        echo [오류] 패키지 설치에 실패했습니다. 인터넷 연결이나 pip 설정을 확인해 주세요.
        echo.
        pause
        exit /b 1
    )
    echo [완료] 패키지 설치가 완료되었습니다.
    echo.
)

echo ===================================================
echo   앱을 시작합니다.
echo   - 로컬 주소: http://localhost:8501
echo   - 기본 웹 브라우저가 자동으로 실행됩니다.
echo   - 앱을 종료하려면 이 콘솔 창에서 [Ctrl + C]를 누르세요.
echo ===================================================
echo.

python -m streamlit run app.py %*

if %ERRORLEVEL% neq 0 (
    echo.
    echo [알림] 앱 실행이 비정상 종료되었거나 중단되었습니다. [종료 코드: %ERRORLEVEL%]
    echo.
)

pause