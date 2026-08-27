@echo off
:: Move to the directory where this batch file is located
cd /d "%~dp0"

echo ===================================================
echo   투자 북마크 대시보드 - GitHub 자동 동기화 시작
echo ===================================================
echo.

echo [1/3] 변경된 bookmarks.json 파일 스테이징 중...
git add bookmarks.json
if %ERRORLEVEL% neq 0 (
    echo [에러] 파일 스테이징에 실패했습니다. Git 저장소 설정을 확인해 주세요.
    goto end
)

echo [2/3] 변경 사항 커밋 중...
git diff-index --quiet HEAD -- bookmarks.json
if %ERRORLEVEL% equ 0 (
    echo [알림] 변경된 북마크 내용이 없습니다. 동기화를 건너뜁니다.
    goto end
)

git commit -m "Auto-update bookmarks.json from backup"
if %ERRORLEVEL% neq 0 (
    echo [에러] 커밋에 실패했습니다.
    goto end
)

echo [3/3] GitHub 원격 저장소로 업로드(Push) 중...
git pull --rebase origin main
if %ERRORLEVEL% neq 0 (
    echo [에러] 원격 저장소의 최신 변경 사항을 가져오는 데 실패했습니다 (Pull/Rebase 실패).
    goto end
)
git push origin main
if %ERRORLEVEL% neq 0 (
    echo [에러] GitHub 업로드에 실패했습니다. 인터넷 연결이나 권한을 확인해 주세요.
    goto end
)

echo.
echo ===================================================
echo   ★ 북마크 동기화 완료! Streamlit 앱에 자동 반영됩니다.
echo ===================================================

:end
echo.
pause
