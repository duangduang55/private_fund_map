#!/bin/bash
# 私募基金拓客辅助系统 — 重启脚本
# 停止现有服务后重新启动，保留 start.sh 的检测逻辑

set -e

cd "$(dirname "$0")"

echo "=========================================="
echo "  私募基金拓客辅助系统 — 重启"
echo "=========================================="

# ── 1. 停止现有服务 ──
echo "[1/4] 停止现有服务..."

stop_port() {
    local port=$1 name=$2
    local pids
    pids=$(lsof -ti :"$port" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        kill $pids 2>/dev/null || true
        sleep 1
        # 强制终止
        pids=$(lsof -ti :"$port" 2>/dev/null || true)
        if [ -n "$pids" ]; then
            kill -9 $pids 2>/dev/null || true
        fi
        echo "  ✅ 已停止 $name (port $port)"
    else
        echo "  ⏭️  $name (port $port) 未运行"
    fi
}

stop_port 8100 "FastAPI"
stop_port 8501 "Streamlit"

# ── 2. 检测 Python 环境（复用 start.sh 逻辑） ──
detect_python() {
    if [ -f "venv/bin/python3" ]; then
        echo "  使用项目 venv: venv/"
        . venv/bin/activate
        return 0
    fi
    if [ -f ".venv/bin/python3" ]; then
        echo "  使用项目 .venv"
        . .venv/bin/activate
        return 0
    fi
    if [ -n "$CONDA_DEFAULT_ENV" ]; then
        echo "  使用 conda 环境: $CONDA_DEFAULT_ENV"
        return 0
    fi
    if command -v python3 &>/dev/null; then
        echo "  使用系统 python3: $(which python3)"
        return 0
    fi
    echo "  ❌ 未找到 Python 环境"
    exit 1
}

echo "[2/4] 检测 Python 环境..."
detect_python

# ── 3. 检查数据库 ──
echo "[3/4] 检查 PostgreSQL 连接..."
python3 -c "
import sys; sys.path.insert(0, '.')
from backend.config import TS_QUANT_DB, FUND_MAP_DB
import psycopg2
for cfg in [TS_QUANT_DB, FUND_MAP_DB]:
    conn = psycopg2.connect(**cfg)
    conn.close()
print('  ✅ 数据库连接正常')
" 2>&1 || { echo "  ❌ 数据库连接失败"; exit 1; }

# ── 4. 启动服务 ──
echo "[4/4] 启动服务..."

python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8100 --reload &
FASTAPI_PID=$!
echo "  ✅ FastAPI 已启动 (PID: $FASTAPI_PID, port 8100)"

sleep 2

streamlit run app.py --server.port 8501 &
STREAMLIT_PID=$!
echo "  ✅ Streamlit 已启动 (PID: $STREAMLIT_PID, port 8501)"

echo ""
echo "=========================================="
echo "  🚀 系统已重启！"
echo "  Streamlit: http://localhost:8501"
echo "  FastAPI:   http://localhost:8100"
echo "  API文档:   http://localhost:8100/docs"
echo "=========================================="
echo ""
echo "按 Ctrl+C 停止所有服务"

trap "echo '正在停止...'; kill $FASTAPI_PID $STREAMLIT_PID 2>/dev/null; exit 0" SIGINT SIGTERM

wait
