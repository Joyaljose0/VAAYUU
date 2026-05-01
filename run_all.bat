@echo off
echo ==============================================
echo AuraGuard AI - Full Stack Initialization
echo ==============================================
echo.

echo [1/3] Compiling and Flashing ESP32 Firmware via PlatformIO...
set /p flash_esp=Do you want to re-upload the ESP32 code? (y/N): 
set PIO_EXE="%USERPROFILE%\.platformio\penv\Scripts\pio.exe"

if /I "%flash_esp%"=="y" (
    echo [NOTE] Clearing COM port by running stop_all.bat...
    call stop_all.bat
    timeout /t 2 /nobreak >nul
    
    if exist %PIO_EXE% (
        call %PIO_EXE% run -t upload
        if errorlevel 1 (
            echo.
            echo [ERROR] PlatformIO failed to upload firmware. Please check your COM port and ESP32 connection.
            pause
            exit /b 1
        )
        echo ESP32 Flashed Successfully!
    ) else (
        echo [ERROR] PlatformIO executable not found at %PIO_EXE%.
        echo Are you sure PlatformIO is installed?
        pause
        exit /b 1
    )
) else (
    echo Skipping ESP32 flash...
)
echo.

echo [2/3] Starting React Frontend in background...
start /b cmd /c "cd frontend && npm run dev"
timeout /t 3 /nobreak >nul

echo [3/3] Starting Python Backend...
echo The React dashboard should automatically open or be available at http://localhost:3000
echo.

set VENV_PYTHON="%~dp0.venv\Scripts\python.exe"
if exist %VENV_PYTHON% (
    echo Using Virtual Environment...
    %VENV_PYTHON% "%~dp0backend\api\main.py"
) else (
    echo.
    echo WARNING: Virtual environment not found at %VENV_PYTHON%
    echo Attempting to use system python...
    python "%~dp0backend\api\main.py"
)

pause
