@echo off
echo ==============================================
echo AuraGuard AI - System Shutdown Utility
echo ==============================================
echo.

echo [1/2] Terminating Python Backend...
taskkill /F /IM python.exe /T 2>nul
if %errorlevel% equ 0 (
    echo Backend processes terminated.
) else (
    echo No active Python backend found.
)

echo.
echo [2/2] Terminating Node.js/Vite Frontend...
taskkill /F /IM node.exe /T 2>nul
if %errorlevel% equ 0 (
    echo Frontend processes terminated.
) else (
    echo No active Node.js frontend found.
)

echo.
echo ==============================================
echo Cleanup Complete.
echo ==============================================
timeout /t 3
