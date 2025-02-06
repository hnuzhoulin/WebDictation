@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: 配置
set "APP_NAME=Web Dictation App"
set "PORT=8800"
set "PROXY_HOST=192.168.119.155"
set "PROXY_PORT=7897"
set "APP_DIR=%~dp0"
set "VENV_PATH=%APP_DIR%venv"
set "PID_FILE=%APP_DIR%app.pid"
set "LOG_FILE=%APP_DIR%app.log"

:: 设置 Python 默认编码为 UTF-8
set "PYTHONIOENCODING=utf8"
set "PYTHONUTF8=1"

:: 切换到应用目录
cd /d "%APP_DIR%" || (
    echo Cannot change to application directory: %APP_DIR%
    exit /b 1
)

:: 代理设置
set "HTTPS_PROXY=http://%PROXY_HOST%:%PROXY_PORT%"
set "HTTP_PROXY=http://%PROXY_HOST%:%PROXY_PORT%"

:: 主程序入口
goto :parse_command

:: 获取状态函数
:do_status
for /f  %%a in ('wmic process where "commandline like '%%uvicorn%%' and name like '%%python%%'" get processid ^| findstr /r "[0-9]"') do (
    echo Found running instance with PID: %%a
    exit /b 0
)
echo %APP_NAME% is not running
exit /b 1


:: 启动函数
:start
:: 清理可能存在的旧 PID 文件
if exist "%PID_FILE%" (
    del "%PID_FILE%" 2>nul
)

:: 检查虚拟环境
if exist "%APP_DIR%venv\Scripts\activate.bat" (
    set "VENV_PATH=%APP_DIR%venv"
) else if exist "%APP_DIR%myenv\Scripts\activate.bat" (
    set "VENV_PATH=%APP_DIR%myenv"
) else (
    echo Virtual environment not found in venv or myenv
    exit /b 1
)

:: 激活虚拟环境
call "%VENV_PATH%\Scripts\activate.bat"

:: 检查 uvicorn 是否安装
"%VENV_PATH%\Scripts\python.exe" -c "import uvicorn" 2>nul
if !errorlevel! neq 0 (
    echo uvicorn is required. Please run: pip install uvicorn
    exit /b 1
)

echo Starting %APP_NAME%...

:: 使用完整路径启动 uvicorn，确保使用 UTF-8 编码
start /b cmd /c "set PYTHONIOENCODING=utf8 && set PYTHONUTF8=1 && "%VENV_PATH%\Scripts\python.exe" -X utf8 -m uvicorn src.main:app --host 0.0.0.0 --port %PORT% > "%LOG_FILE%" 2>&1"

:: 等待几秒确保进程启动
timeout /t 2 /nobreak >nul

:: 获取新启动的 Python 进程的 PID
for /f  %%a in ('wmic process where "commandline like '%%uvicorn%%' and name like '%%python%%'" get processid ^| findstr /r "[0-9]"') do (
    if "%%a" neq "" (
        echo %APP_NAME% started successfully,PID: %%a 
        echo %%a>>"%PID_FILE%"
        echo Log file: %LOG_FILE%
        echo Access URL: http://localhost:%PORT%
        exit /b 0
    )
)

:: 如果没有找到进程，检查日志文件中的进程ID
findstr /C:"Started server process" "%LOG_FILE%" > nul
if !errorlevel! equ 0 (
    for /f "tokens=4 delims=[] " %%a in ('findstr /C:"Started server process" "%LOG_FILE%"') do (
        set "PID=%%a"
        echo %PID%>"%PID_FILE%"
        echo %APP_NAME% started successfully (PID: %PID%)
        echo Log file: %LOG_FILE%
        echo Access URL: http://localhost:%PORT%
        exit /b 0
    )
)

echo %APP_NAME% failed to start. Please check log file: %LOG_FILE%
type "%LOG_FILE%"
exit /b 1

:: 停止函数
:stop
:: 尝试查找并终止所有相关的 Python 进程
for /f  %%a in ('wmic process where "commandline like '%%uvicorn%%' and name like '%%python%%'" get processid ^| findstr /r "[0-9]"') do (
    echo Found running instance with PID: %%a
    taskkill /F /PID %%a >nul 2>&1
)
exit /b 0


:: 重启函数
:restart
call :stop
timeout /t 2 /nobreak >nul
goto :start

:: 查看日志函数
:logs
if exist "%LOG_FILE%" (
    type "%LOG_FILE%"
) else (
    echo Log file does not exist
)
exit /b 0

:: 命令解析
:parse_command
if "%~1"=="" (
    echo Usage: %~n0 {start^|stop^|restart^|status^|logs}
    exit /b 1
)

if /i "%~1"=="start" goto :start
if /i "%~1"=="stop" goto :stop
if /i "%~1"=="status" goto :do_status
if /i "%~1"=="restart" goto :restart
@REM if /i "%~1"=="status" goto :status
if /i "%~1"=="logs" goto :logs

echo Invalid command: %~1
echo Usage: %~n0 {start^|stop^|restart^|status^|logs}
exit /b 1
