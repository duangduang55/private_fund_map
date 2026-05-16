"""飞书同步配置管理"""

import json
from pathlib import Path

# ── 配置文件路径 ──

_BASE = Path(__file__).resolve().parent
CONFIG_DIR = _BASE / "feishu_config"
CONFIG_JSON_PATH = CONFIG_DIR / "config.json"

# ── 飞书凭证（从 feishu_config/config.json 加载） ──

FEISHU_APP_ID = ""
FEISHU_APP_SECRET = ""
FEISHU_APP_TOKEN = ""
FEISHU_TABLE_ID = ""
FEISHU_ORG_DICT_TABLE_ID = ""
FEISHU_SYNC_USER = "飞书同步"
FEISHU_SYNC_INTERVAL_MINUTES = 0  # 0=关闭自动同步

# ── 数据库连接 ──

FUND_MAP_DB = {
    "host": "localhost",
    "port": 5432,
    "dbname": "fund_map_db",
    "user": "fund_map_user",
    "password": "123456789",
}

TS_QUANT_DB = {
    "host": "localhost",
    "port": 5432,
    "dbname": "ts_quant_db",
    "user": "db_query_user",
    "password": "123456789",
}

# ── 字段映射 ──

FIELD_MAP = {
    "机构名称": "org_name",
    "登记编号": "reg_num",
    "拜访日期": "planned_date",
    "拜访人": "visitor_name",
    "拜访状态": "visit_status",
    "沟通摘要": "summary",
    "沟通详情": "communication_detail",
    "已获取联系方式/名片": "has_business_card",
    "与高管/实控人建立联系": "has_contact_info",
    "跟进建议": "follow_up_suggestions",
    "标签": "tags",
    "办公地址": "office_address",
    "管理规模": "org_aum",
}

LINKED_FIELDS = {"机构名称"}
DATE_FIELDS = {"拜访日期"}


# ── JSON 配置读写 ──


def _set_globals_from_dict(data: dict):
    """从字典设置模块全局变量"""
    global FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_APP_TOKEN
    global FEISHU_TABLE_ID, FEISHU_ORG_DICT_TABLE_ID
    global FEISHU_SYNC_INTERVAL_MINUTES

    FEISHU_APP_ID = data.get("FEISHU_APP_ID", FEISHU_APP_ID)
    FEISHU_APP_SECRET = data.get("FEISHU_APP_SECRET", FEISHU_APP_SECRET)
    FEISHU_APP_TOKEN = data.get("FEISHU_APP_TOKEN", FEISHU_APP_TOKEN)
    FEISHU_TABLE_ID = data.get("FEISHU_TABLE_ID", FEISHU_TABLE_ID)
    FEISHU_ORG_DICT_TABLE_ID = data.get("FEISHU_ORG_DICT_TABLE_ID", FEISHU_ORG_DICT_TABLE_ID)
    FEISHU_SYNC_INTERVAL_MINUTES = data.get("FEISHU_SYNC_INTERVAL_MINUTES", FEISHU_SYNC_INTERVAL_MINUTES)


def load_from_json() -> bool:
    """从 feishu_config/config.json 加载配置"""
    if not CONFIG_JSON_PATH.exists():
        return False

    try:
        with open(CONFIG_JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
        # 过滤掉 _comment 开头的注释 key
        config = {k: v for k, v in data.items() if not k.startswith("_") and not isinstance(v, list)}
        _set_globals_from_dict(config)
        return True
    except (json.JSONDecodeError, OSError) as e:
        print(f"[配置] 读取 config.json 失败: {e}")
        return False


def save_to_json(config: dict) -> bool:
    """保存配置到 feishu_config/config.json（保留 _comment 注释 key）"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # 读取现有 JSON 保留注释
    existing = {}
    if CONFIG_JSON_PATH.exists():
        try:
            with open(CONFIG_JSON_PATH, encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing = {}

    # 合并：保留注释 key + cron_jobs，更新配置 key
    # 先保留所有现有 key
    merged = dict(existing)

    # 写入选中的配置 key
    for k, v in config.items():
        if k.startswith("_") or k == "cron_jobs":
            continue
        merged[k] = v

    # 确保必需 key 存在（从现有全局变量补充）
    for key in ("FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_APP_TOKEN",
                "FEISHU_TABLE_ID", "FEISHU_ORG_DICT_TABLE_ID",
                "FEISHU_SYNC_INTERVAL_MINUTES"):
        if key not in merged:
            val = globals().get(key, "")
            if key == "FEISHU_SYNC_INTERVAL_MINUTES":
                val = val if isinstance(val, (int, float)) else 0
            merged[key] = val

    try:
        with open(CONFIG_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
            f.write("\n")
        # 重新加载
        load_from_json()
        return True
    except OSError as e:
        print(f"[配置] 写入 config.json 失败: {e}")
        return False


def get_all_config_json() -> dict:
    """获取完整 JSON 配置对象（含 cron_jobs，供 API/UI 用）"""
    data = {}
    if CONFIG_JSON_PATH.exists():
        try:
            with open(CONFIG_JSON_PATH, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return data


def get_cron_jobs() -> list:
    """从 config.json 获取 cron 任务列表"""
    data = get_all_config_json()
    return data.get("cron_jobs", [])


def save_cron_jobs(jobs: list) -> bool:
    """保存 cron 任务列表到 config.json"""
    data = get_all_config_json()
    data["cron_jobs"] = jobs
    return _write_json_raw(data)


def _write_json_raw(data: dict) -> bool:
    """直接写入完整 JSON 对象（不合并，直接覆盖）"""
    try:
        with open(CONFIG_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        return True
    except OSError as e:
        print(f"[配置] 写入 config.json 失败: {e}")
        return False


def get_sync_interval() -> int:
    """获取自动同步间隔（分钟），0=关闭"""
    return FEISHU_SYNC_INTERVAL_MINUTES


# ── 配置加载 ──


def load_config():
    """从 feishu_config/config.json 加载配置"""
    if not load_from_json():
        print(f"[配置] 未找到 {CONFIG_JSON_PATH}，请先通过 Web 界面配置飞书参数")


def get_all_config() -> dict:
    """获取所有配置项（用于 API 返回，兼容旧版）"""
    return {
        "FEISHU_APP_ID": FEISHU_APP_ID,
        "FEISHU_APP_SECRET": FEISHU_APP_SECRET,
        "FEISHU_APP_TOKEN": FEISHU_APP_TOKEN,
        "FEISHU_TABLE_ID": FEISHU_TABLE_ID,
        "FEISHU_ORG_DICT_TABLE_ID": FEISHU_ORG_DICT_TABLE_ID,
    }


def save_config_to_file(config: dict) -> bool:
    """保存配置（统一走 JSON）"""
    return save_to_json(config)
