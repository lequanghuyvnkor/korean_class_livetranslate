@echo off
title Korean Live Lecture Translator
color 0B
echo ================================================================
echo    KOREAN LIVE LECTURE TRANSLATOR - (KOREAN -> ENGLISH)
echo ================================================================
echo.

cd /d "%~dp0"

set KMP_DUPLICATE_LIB_OK=TRUE
set OMP_NUM_THREADS=4

echo [*] Checking Python installation...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found in PATH! Please install Python or Anaconda.
    pause
    exit /b 1
)

echo [*] Starting Live Translation Server...
python main.py

pause
