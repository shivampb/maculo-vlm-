  @echo off
rem Double-click to start Maculo, then open http://127.0.0.1:8000
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
  echo Can't find the Python environment in the "venv" folder.
  echo See "Setup" in README.md.
  pause
  exit /b 1
)
echo Starting Maculo. The first start can take a minute while the models load.
echo When you see "Uvicorn running", open http://127.0.0.1:8000 in your browser.
echo Close this window to stop Maculo.
start "" /b cmd /c "timeout /t 4 >nul & start http://127.0.0.1:8000"
"venv\Scripts\python.exe" -m maculo
pause
