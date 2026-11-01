@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 goto use_py
where python >nul 2>nul
if not errorlevel 1 goto use_python
echo Python wurde nicht gefunden. Bitte Python 3.10 oder neuer installieren.
echo Danach diese Datei erneut starten.
pause
exit /b 1
:use_py
py -3 %*
goto finished
:use_python
python %*
:finished
set kr_exit=%errorlevel%
echo.
pause
exit /b %kr_exit%
