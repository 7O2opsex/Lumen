@echo off
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --icon=assets\lumen.ico --name Lumen main.py
