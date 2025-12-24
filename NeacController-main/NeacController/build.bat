@echo off
echo Setting up Driver..
echo =====================================

REM Check if running as administrator
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: This script must be run as Administrator
    echo Right-click and select "Run as administrator"
    pause
    exit /b 1
)

echo Installing Python dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo Building C++ extension...
python setup.py build_ext --inplace
if %errorlevel% neq 0 (
    echo ERROR: Failed to build extension
    pause
    exit /b 1
)

echo.
echo Installing module...
python setup.py install
if %errorlevel% neq 0 (
    echo ERROR: Failed to install module
    pause
    exit /b 1
)

echo.
echo =====================================
echo Build completed successfully!
echo.
echo You can now use the module with:
echo   import neac_controller
echo.
echo Run example.py to test the module
echo =====================================
pause
