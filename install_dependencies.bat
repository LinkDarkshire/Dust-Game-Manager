@echo off
echo ============================================
echo Dust Game Manager - Dependency Installation
echo ============================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8 or higher from https://python.org
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

echo Python found: 
python --version
echo.

:: Check if Node.js is installed
node --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Node.js is not installed or not in PATH
    echo Please install Node.js from https://nodejs.org
    pause
    exit /b 1
)

echo Node.js found:
node --version
echo.

:: Install Node.js dependencies
echo Installing Node.js dependencies...
npm install
if errorlevel 1 (
    echo ERROR: Failed to install Node.js dependencies
    pause
    exit /b 1
)
echo ✓ Node.js dependencies installed successfully
echo.

:: Install Python dependencies
echo Installing Python dependencies...
cd backend
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install Python dependencies
    echo Trying with --user flag...
    pip install --user -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install Python dependencies
        echo Please try installing manually:
        echo pip install Flask Flask-CORS dlsite-async aiohttp aiofiles python-dateutil Pillow
        cd ..
        pause
        exit /b 1
    )
)
cd ..
echo ✓ Python dependencies installed successfully
echo.

:: Create necessary directories
echo Creating necessary directories...
if not exist "data" mkdir data
if not exist "data\covers" mkdir data\covers
if not exist "logs" mkdir logs
if not exist "assets" mkdir assets
echo ✓ Directories created
echo.

:: Install Python package in development mode
echo Installing Python package in development mode...
cd backend
pip install -e .
if errorlevel 1 (
    echo Warning: Failed to install Python package in development mode
    echo This is not critical, but some imports might not work
)
cd ..
echo.

:: Test backend startup
echo Testing Python backend...
echo Starting backend for 5 seconds to test...
start /b python backend\scripts\main.py --port 5001 > backend_test.log 2>&1
timeout /t 5 /nobreak > nul

:: Check if backend started successfully
curl -s http://127.0.0.1:5001/api/status > nul 2>&1
if errorlevel 1 (
    echo Warning: Backend test failed
    echo This might be normal if dependencies are still installing
    echo Check backend_test.log for details
) else (
    echo ✓ Backend started successfully
)

:: Kill test backend
taskkill /f /im python.exe > nul 2>&1

echo.
echo ============================================
echo Installation completed!
echo ============================================
echo.
echo You can now start the application with:
echo   npm start
echo or
echo   start.bat
echo.
echo For debugging, use:
echo   start-debug.bat
echo.
pause