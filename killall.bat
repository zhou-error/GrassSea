@echo off
echo Killing all GrassSea processes...

for %%p in (21144 5376 42036 21808 16160 39268 44268 42656) do (
    taskkill /F /PID %%p >nul 2>&1
)

echo.
echo Killing all uvicorn processes...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *uvicorn*" >nul 2>&1

echo Killing all node processes...
taskkill /F /IM node.exe >nul 2>&1

echo.
echo Stopping Docker containers...
cd /d "%~dp0"
docker compose down 2>&1

echo.
echo All processes stopped.
pause
