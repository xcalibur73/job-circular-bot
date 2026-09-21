@echo off
setlocal
cd /d "%~dp0job_circular_bot"

echo ============================================
echo  Job Circular Bot - search and post
echo ============================================
echo.

set "KEYWORD="
set /p KEYWORD=Job title or keyword to look for (press Enter for everything): 

echo.
echo   1) Dry run    - search, filter and show what would be posted (nothing goes to Facebook)
echo   2) Real post  - actually post new notices to the Facebook Page
set "MODE=1"
set /p MODE=Choose 1 or 2 (press Enter for 1): 

echo.
if "%MODE%"=="2" (
    python src\main.py --keyword "%KEYWORD%"
) else (
    python src\main.py --keyword "%KEYWORD%" --dry-run
)

echo.
pause
