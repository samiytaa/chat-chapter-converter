@echo off
setlocal

cd /d "%~dp0"
where node >nul 2>nul
if errorlevel 1 (
    echo Node.js was not found in PATH.
    echo Please install Node.js or add it to PATH, then try again.
    pause
    exit /b 1
)

call npm run build
if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

echo Starting preview server...
start "TXT Converter Preview" cmd /k npm run serve
timeout /t 2 /nobreak >nul
start http://127.0.0.1:8765

endlocal
