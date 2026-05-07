#!/bin/bash
# 私募基金拓客辅助系统 — 启动脚本
# 启动 FastAPI 后端 + Streamlit 前端
# 使用前请确保 config.ini 已配置（基于 config.ini.example）

set -e

echo "=========================================="
echo "  私募基金拓客辅助系统"
echo "=========================================="

# 切换到项目根目录
cd "$(dirname "$0")"

# 检查 config.ini
if [ ! -f config.ini ]; then
    if [ -f config.ini.example ]; then
        echo "[!] 未检测到 config.ini，请复制 config.ini.example 并配置:"
        echo "    cp config.ini.example config.ini"
        echo "    然后编辑 config.ini 填入数据库连接信息"
    fi
fi

# 检查 PostgreSQL
echo "[1/3] 检查 PostgreSQL 连接..."
python3 -c "
import sys
sys.path.insert(0, '.')
from backend.config import TS_QUANT_DB, FUND_MAP_DB
import psycopg2
for name, cfg in [('ts_quant_db', TS_QUANT_DB), ('fund_map_db', FUND_MAP_DB)]:
    if not cfg.get('password'):
        print(f'  ⚠️  {name} 密码为空，跳过检查')
        continue
    conn = psycopg2.connect(**cfg)
    conn.close()
    print(f'  ✅ {name} 连接正常')
print('  数据库检查完成')
" 2>&1 || { echo "  ❌ 数据库连接失败，请确认 PostgreSQL 已启动且 config.ini 配置正确"; exit 1; }

# 启动 FastAPI 后端（后台）
echo "[2/3] 启动 FastAPI 后端 (port 8000)..."
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
FASTAPI_PID=$!
echo "  ✅ FastAPI 已启动 (PID: $FASTAPI_PID)"

# 等待 FastAPI 就绪
sleep 2

# 启动 Streamlit 前端
echo "[3/3] 启动 Streamlit 前端 (port 8501)..."
streamlit run app.py --server.port 8501 &
STREAMLIT_PID=$!
echo "  ✅ Streamlit 已启动 (PID: $STREAMLIT_PID)"

echo ""
echo "=========================================="
echo "  🚀 系统已启动！"
echo "  Streamlit: http://localhost:8501"
echo "  FastAPI:   http://localhost:8000"
echo "  API文档:   http://localhost:8000/docs"
echo "  地图页面:  http://localhost:8000/map"
echo "=========================================="
echo ""
echo "按 Ctrl+C 停止所有服务"

# 捕获中断信号，停止所有服务
trap "echo '正在停止...'; kill $FASTAPI_PID $STREAMLIT_PID 2>/dev/null; exit 0" SIGINT SIGTERM

# 等待任意子进程退出
wait
