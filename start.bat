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
if exist data\mosaic.db goto :api_check
:seed
echo Seeding the demo...
python -m app.seed --reset
if errorlevel 1 exit /b 1

:api_check
set API_PID=
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":8000 .*LISTENING"') do set API_PID=%%P
if defined API_PID goto :api_running
echo Starting the API on http://localhost:8000 ...
start "MOSAIC API" cmd /k "cd /d %ROOT%backend && call .venv\Scripts\activate.bat && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
goto :frontend

:api_running
echo API already running on http://localhost:8000 (PID %API_PID%).

:frontend
cd /d "%ROOT%frontend"
if exist node_modules goto :web_check
echo Installing frontend packages...
call npm install --no-audit --no-fund
if errorlevel 1 exit /b 1

:web_check
set WEB_PID=
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":3000 .*LISTENING"') do set WEB_PID=%%P
if defined WEB_PID goto :web_running

if not exist .next goto :start_web
echo Removing stale Next.js build output...
rmdir /s /q .next

:start_web
echo.
echo MOSAIC is starting. Open http://localhost:3000
echo API docs: http://localhost:8000/docs
echo.
call npm run dev
exit /b %errorlevel%

:web_running
echo Frontend already running on http://localhost:3000 (PID %WEB_PID%).
echo Reuse that browser tab instead of starting a second Next.js server.
exit /b 0

:no_python
echo ERROR: Python was not found on PATH.
exit /b 1

:no_npm
echo ERROR: npm was not found on PATH.
exit /b 1
