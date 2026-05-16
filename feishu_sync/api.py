"""飞书 API 调用封装"""

import logging
import os
import time

import requests

from . import config

log = logging.getLogger("feishu_sync")
FEISHU_BASE = "https://open.feishu.cn/open-apis"


def get_tenant_token(app_id: str, app_secret: str) -> str:
    """获取飞书 tenant_access_token"""
    resp = requests.post(
        f"{FEISHU_BASE}/auth/v3/tenant_access_token/internal",
        json={"app_id": app_id, "app_secret": app_secret},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"获取 token 失败: {data}")
    return data["tenant_access_token"]


def list_bitable_records(token: str, page_size: int = 50) -> list[dict]:
    """读取多维表格中所有记录，Python 端过滤未同步的记录"""
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{FEISHU_BASE}/bitable/v1/apps/{config.FEISHU_APP_TOKEN}/tables/{config.FEISHU_TABLE_ID}/records"

    all_records = []
    page_token = None
    while True:
        params = {"page_size": page_size}
        if page_token:
            params["page_token"] = page_token
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        data = resp.json()
        if data.get("code") != 0:
            log.error(f"读取记录失败: {data}")
            break
        items = data.get("data", {}).get("items") or []
        all_records.extend(items)
        if not data.get("data", {}).get("has_more"):
            break
        page_token = data["data"].get("page_token")

    # Python 端过滤：同步状态为空或不为"已同步"
    pending = []
    for r in all_records:
        status = r.get("fields", {}).get("同步状态", "")
        if not status or status != "已同步":
            pending.append(r)
    return pending


def update_bitable_record(token: str, record_id: str, fields: dict):
    """更新多维表格记录（标记同步状态）"""
    headers = {"Authorization": f"Bearer {token}"}
    url = (
        f"{FEISHU_BASE}/bitable/v1/apps/{config.FEISHU_APP_TOKEN}"
        f"/tables/{config.FEISHU_TABLE_ID}/records/{record_id}"
    )
    resp = requests.put(url, headers=headers, json={"fields": fields}, timeout=10)
    data = resp.json()
    if data.get("code") != 0:
        log.warning(f"更新记录 {record_id} 失败: {data}")


def lookup_org_name_from_dict(token: str, record_ids: list[str]) -> str | None:
    """从飞书机构字典表中根据 record_id 查询真实的机构名称"""
    headers = {"Authorization": f"Bearer {token}"}
    dict_table_id = config.FEISHU_ORG_DICT_TABLE_ID or os.environ.get("FEISHU_ORG_DICT_TABLE_ID", "tblEkotFTMArOXsF")
    url = f"{FEISHU_BASE}/bitable/v1/apps/{config.FEISHU_APP_TOKEN}/tables/{dict_table_id}/records/{record_ids[0]}"
    resp = requests.get(url, headers=headers, timeout=10)
    data = resp.json()
    if data.get("code") == 0:
        record = data.get("data", {}).get("record", {})
        fields = record.get("fields", {})
        name = fields.get("机构名称")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return None


def extract_feishu_value(cn_name: str, raw_value) -> object:
    """将飞书 API 返回的字段值转换为 Python 原生类型"""
    if raw_value is None:
        return None

    if isinstance(raw_value, bool):
        return raw_value

    if isinstance(raw_value, (int, float)):
        if cn_name in config.DATE_FIELDS:
            return time.strftime("%Y-%m-%d", time.localtime(raw_value / 1000))
        return raw_value

    if isinstance(raw_value, str):
        return raw_value

    if isinstance(raw_value, list):
        if not raw_value:
            return None

        first = raw_value[0]
        if isinstance(first, dict) and "record_ids" in first:
            return {"_linked_record_ids": first["record_ids"], "_text": first.get("text") or ""}

        if isinstance(first, dict) and "text" in first:
            texts = [item.get("text", "") for item in raw_value if isinstance(item, dict)]
            return "".join(texts)

        result = []
        for item in raw_value:
            if isinstance(item, dict):
                result.append(item.get("text", str(item)))
            else:
                result.append(str(item))
        return result

    return raw_value


def extract_fields(bitable_record: dict) -> dict:
    """将飞书多维表格记录转换为 Postgres 字段"""
    fields = bitable_record.get("fields", {})
    result = {}
    for cn_name, db_name in config.FIELD_MAP.items():
        raw = fields.get(cn_name)
        if raw is None:
            continue
        value = extract_feishu_value(cn_name, raw)
        if value is not None:
            result[db_name] = value
    return result
