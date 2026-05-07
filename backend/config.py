"""数据库配置和通用设置

配置读取优先级（从高到低）：
1. config.ini 配置文件（从项目根目录或 FUND_MAP_CONFIG 环境变量指定路径）
2. 环境变量（FUND_MAP__{section}__{key}）
3. 下方硬编码的默认值（仅用于本地开发）
"""

import os
import configparser
from typing import Dict, Any


def _load_config() -> configparser.ConfigParser:
    """加载配置文件"""
    cfg = configparser.ConfigParser()

    # 1. 尝试从项目根目录加载 config.ini
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(base_dir, "config.ini"),
        os.environ.get("FUND_MAP_CONFIG", ""),
    ]
    for path in candidates:
        if path and os.path.exists(path):
            cfg.read(path, encoding="utf-8")
            return cfg
    return cfg


_config = _load_config()


def _get(section: str, key: str, fallback: Any = None) -> Any:
    """按优先级获取配置：config.ini → 环境变量 → fallback"""
    # 1. config.ini
    if _config.has_section(section) and _config.has_option(section, key):
        val = _config.get(section, key)
        if val:
            return val
    # 2. 环境变量 FUND_MAP__{section}__{key}
    env_key = f"FUND_MAP__{section}__{key}"
    env_val = os.environ.get(env_key)
    if env_val:
        return env_val
    # 3. fallback
    return fallback


# ── ts_quant_db（只读，私募数据来源） ──
TS_QUANT_DB: Dict[str, Any] = {
    "host": _get("ts_quant_db", "host", "localhost"),
    "port": int(_get("ts_quant_db", "port", "5432")),
    "dbname": _get("ts_quant_db", "dbname", "ts_quant_db"),
    "user": _get("ts_quant_db", "user", "db_query_user"),
    "password": _get("ts_quant_db", "password", ""),
}

# ── fund_map_db（读写，业务数据） ──
FUND_MAP_DB: Dict[str, Any] = {
    "host": _get("fund_map_db", "host", "localhost"),
    "port": int(_get("fund_map_db", "port", "5432")),
    "dbname": _get("fund_map_db", "dbname", "fund_map_db"),
    "user": _get("fund_map_db", "user", "fund_map_user"),
    "password": _get("fund_map_db", "password", ""),
}

# ── JWT ──
JWT_SECRET = _get("jwt", "secret", "change-me-to-a-random-secret-key")
JWT_ALGORITHM = _get("jwt", "algorithm", "HS256")
JWT_EXPIRE_MINUTES = int(_get("jwt", "expire_minutes", "480"))
