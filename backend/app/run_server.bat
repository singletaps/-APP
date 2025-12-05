@echo off
REM Windows批处理脚本：启动FastAPI后端服务器（允许局域网访问）
REM 
REM 使用方法:
REM    run_server.bat              - 默认配置（仅本地访问）
REM    run_server.bat 0.0.0.0      - 允许局域网访问

set HOST=%1
if "%HOST%"=="" set HOST=127.0.0.1

echo ============================================================
echo FastAPI 后端服务器启动
echo ============================================================
echo 主机地址: %HOST%
echo 端口: 8000
echo ============================================================

if "%HOST%"=="0.0.0.0" (
    echo.
    echo 注意：服务器已配置为允许局域网访问
    echo 请确保防火墙允许端口 8000 的入站连接
    echo.
)

python run_server.py --host %HOST% --port 8000 --reload

pause


