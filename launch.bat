@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if not errorlevel 1 (
    set "PYTHON=py -3"
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        echo Python 3 was not found. Install Python 3.11 or later and try again.
        pause
        exit /b 1
    )
    set "PYTHON=python"
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating the project virtual environment...
    %PYTHON% -m venv .venv
    if errorlevel 1 (
        echo Failed to create the virtual environment.
        pause
        exit /b 1
    )
)

echo Installing requirements...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install requirements.
    pause
    exit /b 1
)

echo Starting Lumen...
".venv\Scripts\python.exe" main.py
if errorlevel 1 (
    echo Lumen exited with an error.
    pause
    exit /b 1
)
