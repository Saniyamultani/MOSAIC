@echo off
REM One-command start for Windows.
REM   start.bat          -> install (first run), seed the demo, run both servers
REM   start.bat --fresh  -> wipe the database and re-seed first
setlocal
set ROOT=%~dp0
cd /d "%ROOT%"

echo -- MOSAIC ------------------------------------------------

where python >nul 2>&1
if errorlevel 1 goto :no_python
where npm >nul 2>&1
if errorlevel 1 goto :no_npm

cd /d "%ROOT%backend"
if exist .venv goto :venv_ready
echo Creating the Python virtual environment...
python -m venv .venv
if errorlevel 1 exit /b 1
:venv_ready
call .venv\Scripts\activate.bat
python -m pip install -q --upgrade pip
if errorlevel 1 exit /b 1
python -m pip install -q -r requirements.txt
if errorlevel 1 exit /b 1

if /I "%1"=="--fresh" goto :seed
if exist data\mosaic.db goto :frontend_setup
:seed
echo Seeding the demo...
python -m app.seed --reset
if errorlevel 1 exit /b 1

:frontend_setup
cd /d "%ROOT%"
if exist node_modules goto :start_fullstack
echo Installing Node.js packages...
call npm install --no-audit --no-fund
if errorlevel 1 exit /b 1

:start_fullstack
echo.
echo MOSAIC is starting. Open http://localhost:3000
echo API docs: http://localhost:8000/docs
echo.
call npm run dev
exit /b %errorlevel%

:no_python
echo ERROR: Python was not found on PATH.
exit /b 1

:no_npm
echo ERROR: npm was not found on PATH.
exit /b 1
