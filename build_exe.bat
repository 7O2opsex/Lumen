@echo off
setlocal
cd /d "%~dp0"
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name Lumen main.py
