@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo =========================================================
echo   Bookmarks Dual-Sync Tool (GitHub + Oracle Server)
echo =========================================================
echo.

echo [1/3] Checking bookmarks.json...
git add bookmarks.json
if !ERRORLEVEL! neq 0 (
    echo [ERROR] Git add failed.
    goto end
)

git diff-index --quiet HEAD -- bookmarks.json
if !ERRORLEVEL! equ 0 (
    echo [INFO] No changes detected in bookmarks.json compared to Git.
) else (
    echo [2/3] Committing and pushing to GitHub...
    git commit -m "Auto-update bookmarks.json from backup"
    git pull --rebase origin main
    git push origin main
    if !ERRORLEVEL! neq 0 (
        echo [WARNING] GitHub push had issues, continuing to Oracle sync...
    ) else (
        echo [OK] Pushed to GitHub successfully.
    )
)

echo.
echo [3/3] Syncing to Oracle Server (168.110.38.90:8500)...
python scripts\sync_to_oracle.py "00 Bookmarks"

echo.
echo =========================================================
echo   Dual Sync Completed! (GitHub + Oracle Server:8500)
echo =========================================================

:end
echo.
pause
endlocal
