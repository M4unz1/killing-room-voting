@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3 install_content.py %*
) else (
    python install_content.py %*
)
pause
