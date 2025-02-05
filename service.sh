#!/bin/bash

# 配置
APP_NAME="Web Dictation App"
PORT=8800
PROXY_HOST="192.168.31.31"
PROXY_PORT=8001
APP_DIR="/volume3/docker/WebDictation"
VENV_PATH="$APP_DIR/myenv"
PID_FILE="$APP_DIR/app.pid"
LOG_FILE="$APP_DIR/app.log"

# 确保在正确的目录中
cd "$APP_DIR" || { echo "无法切换到应用目录: $APP_DIR"; exit 1; }

# 激活虚拟环境
if [ -f "$VENV_PATH/bin/activate" ]; then
    source "$VENV_PATH/bin/activate"
    which python
    which uvicorn
else
    echo "虚拟环境不存在: $VENV_PATH"
    exit 1
fi

# 代理设置
export HTTPS_PROXY="http://${PROXY_HOST}:${PROXY_PORT}"
export HTTP_PROXY="http://${PROXY_HOST}:${PROXY_PORT}"

# 检查是否安装了必要的命令
command -v uvicorn >/dev/null 2>&1 || { echo "需要安装 uvicorn，请先运行 pip install uvicorn"; exit 1; }

# 获取应用状态
get_status() {
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo "$APP_NAME 正在运行 (PID: $pid，端口: $PORT)"
            return 0
        else
            echo "$APP_NAME 未运行（PID文件存在但进程已终止）"
            rm -f "$PID_FILE"
            return 1
        fi
    else
        echo "$APP_NAME 未运行"
        return 1
    fi
}

# 启动应用
start() {
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo "$APP_NAME 已经在运行 (PID: $pid)"
            return
        else
            rm -f "$PID_FILE"
        fi
    fi

    echo "正在启动 $APP_NAME..."
    nohup uvicorn src.main:app --host 0.0.0.0 --port $PORT > "$LOG_FILE" 2>&1 &
    pid=$!
    echo $pid > "$PID_FILE"
    sleep 2

    if ps -p "$pid" > /dev/null 2>&1; then
        echo "$APP_NAME 启动成功 (PID: $pid)"
        echo "日志文件: $LOG_FILE"
        echo "访问地址: http://localhost:$PORT"
    else
        echo "$APP_NAME 启动失败，请检查日志文件: $LOG_FILE"
        rm -f "$PID_FILE"
    fi
}

# 停止应用
stop() {
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo "正在停止 $APP_NAME (PID: $pid)..."
            kill "$pid"
            sleep 2
            if ps -p "$pid" > /dev/null 2>&1; then
                echo "进程未响应，强制终止..."
                kill -9 "$pid"
            fi
            rm -f "$PID_FILE"
            echo "$APP_NAME 已停止"
        else
            echo "$APP_NAME 未运行"
            rm -f "$PID_FILE"
        fi
    else
        echo "$APP_NAME 未运行"
    fi
}

# 重启应用
restart() {
    echo "正在重启 $APP_NAME..."
    stop
    sleep 2
    start
}

# 查看日志
logs() {
    if [ -f "$LOG_FILE" ]; then
        tail -f "$LOG_FILE"
    else
        echo "日志文件不存在"
    fi
}

# 清理函数
cleanup() {
    if [ -n "$VIRTUAL_ENV" ]; then
        deactivate
    fi
}

# 注册清理函数
trap cleanup EXIT

# 命令行参数处理
case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        get_status
        ;;
    logs)
        logs
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status|logs}"
        exit 1
        ;;
esac

exit 0