@echo off
if not exist "%~dp0settings.json" copy /Y "%~dp0settings.example.json" "%~dp0settings.json" >nul
start "" notepad.exe "%~dp0settings.json"
