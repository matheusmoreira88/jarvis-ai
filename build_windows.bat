@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (echo Python Launcher not found. Install Python 3.11+ from https://www.python.org/downloads/ & exit /b 1)
py -3.11 -m venv .build-venv
if errorlevel 1 exit /b 1
.build-venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 exit /b 1
.build-venv\Scripts\python.exe -m pip install -e ".[build]"
if errorlevel 1 exit /b 1
.build-venv\Scripts\python.exe -m PyInstaller --noconfirm --clean JarvisAI.spec
if errorlevel 1 exit /b 1
where ISCC.exe >nul 2>nul
if errorlevel 1 (echo Portable app is in dist\JarvisAI. Install Inno Setup to create the Setup installer. & exit /b 0)
ISCC.exe installer\JarvisAI.iss
if errorlevel 1 exit /b 1
echo Installer created in dist\installer.
endlocal
