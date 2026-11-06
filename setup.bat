@echo off
echo === Fro setup ===
python --version >nul 2>&1
if errorlevel 1 (
    echo Python is not installed. Get Python 3.12 from https://www.python.org/downloads/
    echo IMPORTANT: tick "Add python.exe to PATH" in the installer.
    pause
    exit /b 1
)
python -m venv venv
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo Something failed to install. Use Python 3.12 or 3.13 (64-bit) and try again.
    pause
    exit /b 1
)
echo.
echo Done. Double-click run.bat to start Fro.
pause
