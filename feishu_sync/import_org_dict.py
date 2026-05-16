"""
将本地 ts_quant_db 的机构数据导入飞书多维表格「机构字典」表。

作为模块导入：
    from feishu_sync.import_org_dict import sync_org_dict
    result = sync_org_dict(force=False)  # 正常模式：跳过已存在
    result = sync_org_dict(force=True)   # 强制模式：先删同名再重建

作为脚本运行：
    python3 feishu_sync/import_org_dict.py          # 正常模式
    python3 feishu_sync/import_org_dict.py --force   # 强制模式
"""

import sys
import time
from pathlib import Path

import psycopg2
import psycopg2.extras
import requests

# 确保作为脚本直接运行时包可导入
_pkg_dir = str(Path(__file__).resolve().parent.parent)
if _pkg_dir not in sys.path:
    sys.path.insert(0, _pkg_dir)

import feishu_sync.config as config  # noqa: E402
from feishu_sync.log_manager import get_sync_logger  # noqa: E402

FEISHU_BASE = "https://open.feishu.cn/open-apis"
CREATE_DELAY = 0.3  # 逐条创建间隔（秒），防限流

_TOKEN_EXPIRE_AT = 0  # token 过期时间戳

log = get_sync_logger()


def _get_app_token() -> str:
    """获取飞书 token（不缓存，每次获取）"""
    global _TOKEN_EXPIRE_AT
    table_id = config.FEISHU_ORG_DICT_TABLE_ID or config.FEISHU_TABLE_ID
    if not config.FEISHU_APP_ID or not config.FEISHU_APP_SECRET or not config.FEISHU_APP_TOKEN or not table_id:
        raise ValueError("飞书配置不完整，请先通过系统设置页面配置飞书参数")
    resp = requests.post(
        f"{FEISHU_BASE}/auth/v3/tenant_access_token/internal",
        json={"app_id": config.FEISHU_APP_ID, "app_secret": config.FEISHU_APP_SECRET},
        timeout=10,
    )
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"获取 token 失败: {data}")
    _TOKEN_EXPIRE_AT = time.time() + data.get("expire", 7200) - 300
    return data["tenant_access_token"]


def _ensure_token(token: str) -> str:
    """token 即将过期时自动刷新"""
    if time.time() >= _TOKEN_EXPIRE_AT:
        log.info("Token 即将过期，自动刷新...")
        token = _get_app_token()
        log.info("Token 已刷新")
    return token


def _get_table_id() -> str:
    """获取机构字典表 ID"""
    return config.FEISHU_ORG_DICT_TABLE_ID or config.FEISHU_TABLE_ID


def query_local_data() -> list[dict]:
    """从 ts_quant_db 查询需要导入的机构数据"""
    conn = psycopg2.connect(**config.TS_QUANT_DB)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT org_name, reg_num, office_address, org_aum, fund_count, office_coordinates
                   FROM private_fund_list
                   WHERE ins_type IN ('私募证券投资基金管理人', '其他私募投资基金管理人')
                   ORDER BY org_name"""
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def fetch_existing_records(token: str) -> tuple[set, dict]:
    """拉取飞书机构字典表中已有的机构名称和 record_id 映射。"""
    table_id = _get_table_id()
    existing_names = set()
    name_to_id = {}
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{FEISHU_BASE}/bitable/v1/apps/{config.FEISHU_APP_TOKEN}/tables/{table_id}/records"
    page_token = None
    page_size = 500

    while True:
        token = _ensure_token(token)
        headers["Authorization"] = f"Bearer {token}"
        params = {"page_size": page_size}
        if page_token:
            params["page_token"] = page_token
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        data = resp.json()

        if data.get("code") != 0:
            log.warning(f"拉取飞书现有记录失败: code={data.get('code')} msg={data.get('msg','')[:100]}")
            break

        items = data.get("data", {}).get("items") or []
        for item in items:
            rid = item.get("record_id", "")
            name = (item.get("fields") or {}).get("机构名称", "")
            if name:
                existing_names.add(name)
                name_to_id[name] = rid

        if not data.get("data", {}).get("has_more"):
            break
        page_token = data["data"].get("page_token")

    return existing_names, name_to_id


def create_single_record(token: str, fields: dict, max_retries: int = 3) -> tuple:
    """逐条创建机构记录到飞书多维表格。"""
    table_id = _get_table_id()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    url = f"{FEISHU_BASE}/bitable/v1/apps/{config.FEISHU_APP_TOKEN}/tables/{table_id}/records"
    for attempt in range(max_retries):
        resp = requests.post(url, headers=headers, json={"fields": fields}, timeout=30)
        data = resp.json()
        if data.get("code") == 0:
            return True, ""
        if data.get("code") == 1254607 and attempt < max_retries - 1:
            time.sleep(3 * (attempt + 1))
            continue
        return False, f"code={data.get('code')} msg={data.get('msg','')[:200]}"
    return False, "max retries exceeded"


def delete_single_record(token: str, record_id: str) -> tuple:
    """删除飞书中的单条记录。"""
    table_id = _get_table_id()
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{FEISHU_BASE}/bitable/v1/apps/{config.FEISHU_APP_TOKEN}/tables/{table_id}/records/{record_id}"
    resp = requests.delete(url, headers=headers, timeout=15)
    data = resp.json()
    ok = data.get("code") == 0
    err = "" if ok else f"code={data.get('code')} msg={data.get('msg','')[:100]}"
    return ok, err


def build_feishu_fields(r: dict) -> dict:
    """将本地记录转换为飞书字段格式"""
    fields = {"机构名称": r["org_name"], "登记编号": r["reg_num"]}
    if r.get("office_address"):
        fields["办公地址"] = r["office_address"]
    if r.get("org_aum"):
        fields["管理规模"] = r["org_aum"]
    if r.get("fund_count") is not None:
        fields["基金数量"] = r["fund_count"]
    if r.get("office_coordinates"):
        fields["办公地坐标"] = r["office_coordinates"]
    return fields


def sync_org_dict(force: bool = False) -> dict:
    """执行一次机构字典同步。

    从 ts_quant_db 查询 eligible 机构，写入飞书机构字典表。

    Args:
        force: True=强制覆盖（先删同名再创建），False=跳过已存在的

    Returns:
        dict: {"success": int, "failed": int, "skipped": int, "message": str}
    """
    mode = "强制覆盖" if force else "增量导入"
    log.info(f"=== 开始机构字典同步（{mode}）===")

    # 1. 查询本地数据
    log.info("查询本地数据库...")
    records = query_local_data()
    total = len(records)
    log.info(f"共 {total} 条待处理机构")
    if not total:
        return {"success": 0, "failed": 0, "skipped": 0, "message": "无待处理机构数据"}

    # 2. 飞书认证
    try:
        token = _get_app_token()
    except (ValueError, RuntimeError) as e:
        log.error(f"飞书认证失败: {e}")
        return {"success": 0, "failed": 0, "skipped": 0, "message": f"飞书认证失败: {e}"}

    # 3. 拉取飞书现有记录做去重
    log.info("拉取飞书现有机构名称（去重）...")
    existing_names, name_to_id = fetch_existing_records(token)
    log.info(f"飞书已有 {len(existing_names)} 条记录")

    # 4. 过滤
    to_create = []
    skipped = []
    for r in records:
        if r["org_name"] in existing_names:
            if force:
                to_create.append(r)
            else:
                skipped.append(r["org_name"])
        else:
            to_create.append(r)

    skipped_count = len(skipped)
    if skipped_count > 0:
        if not force:
            log.info(f"跳过已存在的机构: {skipped_count} 条")
        else:
            log.info(f"--force 模式: 将覆盖 {len(name_to_id)} 条同名记录")

    if not to_create:
        msg = "全部已存在，无需导入"
        log.info(msg)
        return {"success": 0, "failed": 0, "skipped": skipped_count, "message": msg}

    # 5. force 模式：先删后建
    deleted_count = 0
    delete_fails = 0
    if force:
        log.info("删除已有同名记录...")
        force_names = {r["org_name"] for r in records}
        delete_items = [(name, rid) for name, rid in name_to_id.items() if name in force_names]
        for i, (name, rid) in enumerate(delete_items):
            token = _ensure_token(token)
            ok, err = delete_single_record(token, rid)
            if ok:
                deleted_count += 1
            else:
                delete_fails += 1
                if delete_fails <= 10:
                    log.warning(f"删除失败: {name}: {err}")
            if (i + 1) % 100 == 0 or i == len(delete_items) - 1:
                log.info(f"删除进度: {i+1}/{len(delete_items)}  成功: {deleted_count}  失败: {delete_fails}")
        log.info(f"删除完成: 成功 {deleted_count} 条, 失败 {delete_fails} 条")
        to_create = records  # force 模式下重新创建全部

    # 6. 逐条创建
    success_count = 0
    fail_count = 0
    failed_details = []

    log.info(f"开始导入 {len(to_create)} 条机构...")
    for i, r in enumerate(to_create):
        token = _ensure_token(token)
        fields = build_feishu_fields(r)
        ok, err = create_single_record(token, fields)
        if ok:
            success_count += 1
        else:
            fail_count += 1
            failed_details.append((r["org_name"], err))
            if fail_count <= 10:
                log.warning(f"创建失败: {r['org_name']}: {err}")

        if (i + 1) % 100 == 0 or i == len(to_create) - 1:
            log.info(f"进度: {i+1}/{len(to_create)}  成功: {success_count}  失败: {fail_count}")

        time.sleep(CREATE_DELAY)

    # 7. 汇总
    message = f"同步完成: 成功 {success_count}, 失败 {fail_count}, 跳过 {skipped_count}"
    log.info(f"=== {message} ===")
    return {"success": success_count, "failed": fail_count, "skipped": skipped_count, "message": message}


def main():
    """CLI 入口"""
    import feishu_sync.config as cfg
    cfg.load_config()
    force = "--force" in sys.argv
    result = sync_org_dict(force=force)
    print(result["message"])
    if result["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
