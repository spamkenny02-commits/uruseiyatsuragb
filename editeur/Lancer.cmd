@echo off
cd /d "%~dp0"
if exist "%LocalAppData%\Programs\Python\Python313\python.exe" (
  "%LocalAppData%\Programs\Python\Python313\python.exe" -X utf8 editeur.py
) else (
  py -3 -X utf8 editeur.py
)
if errorlevel 1 pause
