"""数据库连接配置 + JWT 配置（从 .env 加载）"""

import os
from pathlib import Path

# 从项目根目录加载 .env 文件
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=env_path)

# ts_quant_db（只读 — 私募数据来源）
TS_QUANT_DB = {
    "host": os.environ.get("TS_QUANT_DB_HOST", "localhost"),
    "port": int(os.environ.get("TS_QUANT_DB_PORT", "5432")),
    "dbname": os.environ.get("TS_QUANT_DB_NAME", "ts_quant_db"),
    "user": os.environ.get("TS_QUANT_DB_USER", "db_query_user"),
    "password": os.environ.get("TS_QUANT_DB_PASSWORD", "123456789"),
}

# fund_map_db（读写 — 业务数据）
FUND_MAP_DB = {
    "host": os.environ.get("FUND_MAP_DB_HOST", "localhost"),
    "port": int(os.environ.get("FUND_MAP_DB_PORT", "5432")),
    "dbname": os.environ.get("FUND_MAP_DB_NAME", "fund_map_db"),
    "user": os.environ.get("FUND_MAP_DB_USER", "fund_map_user"),
    "password": os.environ.get("FUND_MAP_DB_PASSWORD", "123456789"),
}

# JWT 认证
JWT_SECRET = os.environ.get("JWT_SECRET", "private-fund-map-jwt-secret-key-2025")
JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "480"))
