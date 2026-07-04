@echo off
setlocal enabledelayedexpansion

title GrassSea AI — 一键启动

:: 记录日志
set "LOG=%~dp0startup.log"
echo [%date% %time%] 开始启动 GrassSea AI... > "%LOG%"

echo.
echo ╔══════════════════════════════════════════════╗
echo ║     🌊 白草沧智 GrassSea AI — 启动中...      ║
echo ╚══════════════════════════════════════════════╝
echo.

:: ============================================
:: 切换到脚本所在目录
:: ============================================
cd /d "%~dp0"
echo 工作目录: %cd% >> "%LOG%"

:: ============================================
:: 1. 检查环境
:: ============================================
echo [1/5] 检查环境...

:: Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   ✗ Python 未安装或未加入 PATH
    echo   → 请安装 Python 3.11+ 并勾选 "Add to PATH"
    goto :error
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo   ✓ %%i

:: Node.js
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   ✗ Node.js 未安装或未加入 PATH
    echo   → 请安装 Node.js 并勾选 "Add to PATH"
    goto :error
)
for /f "tokens=*" %%i in ('node --version 2^>^&1') do echo   ✓ Node.js %%i

:: Docker
:: 尝试多个可能的 Docker 路径
set "DOCKER_CMD="
where docker >nul 2>&1 && set "DOCKER_CMD=docker"
if "%DOCKER_CMD%"=="" (
    if exist "C:\Program Files\Docker\Docker\resources\bin\docker.exe" (
        set "DOCKER_CMD=C:\Program Files\Docker\Docker\resources\bin\docker.exe"
    )
)
if "%DOCKER_CMD%"=="" (
    echo   ✗ Docker 未安装或未加入 PATH
    echo   → 请安装 Docker Desktop
    goto :error
)

:: 检查 Docker 是否在运行
%DOCKER_CMD% info >nul 2>&1
if %errorlevel% neq 0 (
    echo   ✗ Docker Desktop 未运行
    echo   → 请先启动 Docker Desktop，等待引擎就绪后重试
    goto :error
)
for /f "tokens=*" %%i in ('%DOCKER_CMD% --version 2^>^&1') do echo   ✓ %%i

:: ============================================
:: 2. 启动 Docker 中间件
:: ============================================
echo.
echo [2/5] 启动 Docker 中间件...

%DOCKER_CMD% compose up -d postgres mongodb redis rabbitmq minio >> "%LOG%" 2>&1
if %errorlevel% neq 0 (
    echo   ✗ Docker 启动失败，详情见 startup.log
    goto :error
)

:: 等待健康检查
echo   等待所有服务就绪（首次需要拉取镜像，可能较慢）...
set "TRY=0"
:wait_health
%DOCKER_CMD% compose ps 2>nul | findstr "unhealthy" >nul
if %errorlevel% equ 0 (
    set /a TRY+=1
    if !TRY! lss 5 (
        echo   发现不健康的服务，等待重试 !TRY!/5...
        timeout /t 10 /nobreak >nul
        goto :wait_health
    )
)

:: 统计健康服务数
set "HEALTHY=0"
for /f "delims=" %%i in ('%DOCKER_CMD% compose ps 2^>nul ^| findstr /c:"healthy" ^| find /c "healthy"') do set "HEALTHY=%%i"
if %HEALTHY% lss 5 (
    echo   ⚠ 健康服务: %HEALTHY%/5, 继续等待...
    timeout /t 10 /nobreak >nul
    goto :wait_health
)

echo   ✓ PostgreSQL  5432
echo   ✓ MongoDB     27017
echo   ✓ Redis       6379
echo   ✓ MinIO       9000/9001
echo   ✓ RabbitMQ    5672/15672

:: ============================================
:: 3. 启动后端 Python 服务
:: ============================================
echo.
echo [3/5] 启动后端服务...

:: 模型网关 — 8004
start "GrassSea-ModelGateway" cmd /k "cd /d %~dp0 && echo 模型网关 http://localhost:8004 && python -m uvicorn services.model_gateway.main:app --host 0.0.0.0 --port 8004"
echo   ✓ 模型网关     http://localhost:8004

:: 知识库/RAG — 8003
start "GrassSea-Knowledge" cmd /k "cd /d %~dp0 && echo 知识库服务 http://localhost:8003 && python -m uvicorn services.knowledge_service.main:app --host 0.0.0.0 --port 8003"
echo   ✓ 知识库/RAG   http://localhost:8003

:: 智能体编排 — 8002
start "GrassSea-Agent" cmd /k "cd /d %~dp0 && echo 智能体编排 http://localhost:8002 && python -m uvicorn services.agent_service.main:app --host 0.0.0.0 --port 8002"
echo   ✓ 智能体编排   http://localhost:8002

:: 对话服务 — 8012
start "GrassSea-Chat" cmd /k "cd /d %~dp0 && echo 对话服务 http://localhost:8012 && python -m uvicorn services.chat_service.main:app --host 0.0.0.0 --port 8012"
echo   ✓ 对话服务     http://localhost:8012

echo   等待服务启动 (约 8 秒)...
timeout /t 8 /nobreak >nul

:: ============================================
:: 4. 前端依赖
:: ============================================
echo.
echo [4/5] 检查前端依赖...
cd /d "%~dp0frontend"
if not exist "node_modules\" (
    echo   首次运行，正在安装前端依赖 (约 1-2 分钟)...
    call npm install >> "%LOG%" 2>&1
    if %errorlevel% neq 0 (
        echo   ✗ npm install 失败，详情见 startup.log
        cd /d "%~dp0"
        goto :error
    )
)
echo   ✓ 前端依赖已就绪
cd /d "%~dp0"

:: ============================================
:: 5. 启动前端
:: ============================================
echo.
echo [5/5] 启动前端...
start "GrassSea-Frontend" cmd /k "cd /d %~dp0frontend && echo GrassSea AI 前端 http://localhost:3000 && npm run dev"

:: 等待前端编译
echo   等待前端编译 (约 4 秒)...
timeout /t 4 /nobreak >nul

:: 打开浏览器
start "" http://localhost:3000

:: ============================================
:: 完成
:: ============================================
echo.
echo ╔══════════════════════════════════════════════╗
echo ║         🎉 启动完成！                        ║
echo ╠══════════════════════════════════════════════╣
echo ║  前端       http://localhost:3000            ║
echo ║  模型网关   http://localhost:8004/health     ║
echo ║  RAG引擎    http://localhost:8003/health     ║
echo ║  智能体     http://localhost:8002/health     ║
echo ║  对话服务   http://localhost:8012/health     ║
echo ╠══════════════════════════════════════════════╣
echo ║  不要关闭弹出的命令行窗口                     ║
echo ║  停止: 双击 stop.bat                         ║
echo ╚══════════════════════════════════════════════╝
echo.
echo 日志文件: startup.log
echo 按任意键关闭此窗口（不影响运行中的服务）...
pause >nul
exit /b 0

:error
echo.
echo ╔══════════════════════════════════════════════╗
echo ║  ❌ 启动失败！请检查上方错误信息               ║
echo ║  详情见: startup.log                         ║
echo ╚══════════════════════════════════════════════╝
echo.
pause
exit /b 1
