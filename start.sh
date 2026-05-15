#!/bin/bash
# 私募基金拓客辅助系统 — 启动脚本
# 自动检测 Python 环境，从 .env 加载配置
# 可重复运行：自动杀掉旧进程后重启

set -e

# 进入脚本所在目录（保证相对路径正确）
cd "$(dirname "$0")"

echo "=========================================="
echo "  私募基金拓客辅助系统"
echo "=========================================="

# ── 1. 停止占用端口的旧进程 ──
echo "[1/5] 清理旧进程..."
stop_port() {
    local port=$1 name=$2
    local pids
    pids=$(lsof -ti :"$port" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        kill $pids 2>/dev/null || true
        sleep 1
        pids=$(lsof -ti :"$port" 2>/dev/null || true)
        if [ -n "$pids" ]; then
            kill -9 $pids 2>/dev/null || true
        fi
        echo "  ✅ 已停止旧 $name (port $port)"
    else
        echo "  ⏭️   $name (port $port) 未运行"
    fi
}
stop_port 8100 "FastAPI"
stop_port 8501 "Streamlit"

# ── 2. 自动检测 Python 环境 ──
detect_python() {
    # 1. 项目内 venv/
    if [ -f "venv/bin/python3" ]; then
        echo "  使用项目 venv: venv/"
        . venv/bin/activate
        return 0
    fi
    # 2. 项目内 .venv/
    if [ -f ".venv/bin/python3" ]; then
        echo "  使用项目 .venv"
        . .venv/bin/activate
        return 0
    fi
    # 3. conda 环境已激活
    if [ -n "$CONDA_DEFAULT_ENV" ]; then
        echo "  使用 conda 环境: $CONDA_DEFAULT_ENV"
        return 0
    fi
    # 4. 系统 python3
    if command -v python3 &>/dev/null; then
        echo "  使用系统 python3: $(which python3)"
        return 0
    fi
    echo "  ❌ 未找到 Python 环境"
    echo "  请确保已安装 Python 3.11+，或创建 venv/"
    exit 1
}

detect_python

# ── 3. 检查 PostgreSQL 连接（从 config.py 读取配置） ──
echo "[3/5] 检查 PostgreSQL 连接..."
python3 -c "
import sys; sys.path.insert(0, '.')
from backend.config import TS_QUANT_DB, FUND_MAP_DB
import psycopg2
for cfg in [TS_QUANT_DB, FUND_MAP_DB]:
    conn = psycopg2.connect(**cfg)
    conn.close()
print('  ✅ 数据库连接正常')
" 2>&1 || { echo "  ❌ 数据库连接失败，请确认 PostgreSQL 已启动"; exit 1; }

# 启动 FastAPI 后端（后台）
echo "[4/5] 启动 FastAPI 后端 (port 8100)..."
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8100 --reload &
FASTAPI_PID=$!
echo "  ✅ FastAPI 已启动 (PID: $FASTAPI_PID)"

# 等待 FastAPI 就绪
sleep 2

# 启动 Streamlit 前端
echo "[5/5] 启动 Streamlit 前端 (port 8501)..."
streamlit run app.py --server.port 8501 &
STREAMLIT_PID=$!
echo "  ✅ Streamlit 已启动 (PID: $STREAMLIT_PID)"

echo ""
echo "=========================================="
echo "  🚀 系统已启动！"
echo "  Streamlit: http://localhost:8501"
echo "  FastAPI:   http://localhost:8100"
echo "  API文档:   http://localhost:8100/docs"
echo "  地图页面:  http://localhost:8100/map"
echo "=========================================="
echo ""
echo "按 Ctrl+C 停止所有服务"

# 捕获中断信号，停止所有服务
trap "echo '正在停止...'; kill $FASTAPI_PID $STREAMLIT_PID 2>/dev/null; exit 0" SIGINT SIGTERM

# 等待任意子进程退出
wait
