@echo off
title Namshi Campaign Planner
color 0A
echo.
echo  =====================================================
echo   Namshi Campaign Planner - Starting...
echo  =====================================================
echo.

cd /d "%~dp0"

echo [1/3] Checking Python...
C:\Python314\python.exe --version
if errorlevel 1 (
    echo ERROR: Python not found at C:\Python314\python.exe
    pause
    exit /b 1
)

echo.
echo [2/3] Installing / verifying dependencies...
C:\Python314\python.exe -m pip install flask requests pandas openpyxl pyyaml python-dateutil --quiet --disable-pip-version-check
if errorlevel 1 (
    echo WARNING: Some packages may not have installed correctly.
)

echo.
echo [3/3] Checking history data...
if not exist "data\standardized_history.csv" (
    echo   Running data standardiser for the first time...
    C:\Python314\python.exe src\standardize.py
    if errorlevel 1 (
        echo   WARNING: Standardizer failed. App will run with config-only mode.
    )
) else (
    echo   History data found - OK
)

echo.
echo  =====================================================
echo   Opening http://localhost:5000 in your browser...
echo  =====================================================
echo.
start "" http://localhost:5000

C:\Python314\python.exe app.py

pause
