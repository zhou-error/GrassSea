@echo off
title GrassSea AI — 停止所有服务

echo.
echo ╔══════════════════════════════════════════════╗
echo ║       🌊 GrassSea AI — 停止所有服务          ║
echo ╚══════════════════════════════════════════════╝
echo.

echo [1/3] 停止后端服务窗口...

:: 关闭所有 GrassSea 相关窗口
for %%t in (
    "GrassSea-ModelGateway"
    "GrassSea-Knowledge"
    "GrassSea-Agent"
    "GrassSea-Chat"
    "GrassSea-Frontend"
) do (
    taskkill /FI "WINDOWTITLE eq %%t" /T /F 2>nul
)

:: 也杀掉 uvicorn 进程（备用）
taskkill /IM python.exe /FI "WINDOWTITLE eq *uvicorn*" /T /F 2>nul

echo   ✓ 后端服务窗口已关闭

echo.
echo [2/3] 停止 Docker 容器...
docker compose down 2>nul || docker-compose down 2>nul
echo   ✓ Docker 容器已停止

echo.
echo [3/3] 清理完成
echo   ✓ 所有服务已停止
echo   💡 重新启动请双击 start.bat

echo.
pause
