"""
飞书同步核心逻辑

作为模块导入：
    from feishu_sync.sync import sync, sync_once

作为脚本运行（保持向后兼容）：
    python3 feishu_sync/sync.py

环境变量替代 config.env：
    FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_APP_TOKEN, FEISHU_TABLE_ID
"""

import sys
import time
from pathlib import Path

# 确保作为脚本直接运行时包可导入
_pkg_dir = str(Path(__file__).resolve().parent.parent)
if _pkg_dir not in sys.path:
    sys.path.insert(0, _pkg_dir)

import feishu_sync.config as config  # noqa: E402
from feishu_sync.log_manager import get_sync_logger  # noqa: E402
from feishu_sync.api import (  # noqa: E402
    get_tenant_token,
    list_bitable_records,
    update_bitable_record,
    lookup_org_name_from_dict,
    extract_fields,
)
from feishu_sync.db import (  # noqa: E402
    get_db_conn,
    ensure_sync_user,
    lookup_reg_num,
    lookup_org_details,
    insert_visit_plan,
    insert_feedback,
)

log = get_sync_logger()


def sync() -> dict:
    """
    执行一次完整同步。

    Returns:
        dict: {"success": int, "failed": int, "message": str}
    """
    log.info("=== 开始同步 ===")

    # 1. 飞书 API 认证
    try:
        token = get_tenant_token(config.FEISHU_APP_ID, config.FEISHU_APP_SECRET)
    except Exception as e:
        log.error(f"飞书认证失败: {e}")
        return {"success": 0, "failed": 0, "message": f"飞书认证失败: {e}"}

    # 2. 读取未同步记录
    try:
        records = list_bitable_records(token)
    except Exception as e:
        log.error(f"读取飞书记录失败: {e}")
        return {"success": 0, "failed": 0, "message": f"读取飞书记录失败: {e}"}

    log.info(f"读取到 {len(records)} 条待同步记录")

    if not records:
        log.info("无待同步记录，结束")
        return {"success": 0, "failed": 0, "message": "无待同步记录"}

    # 3. 连接数据库
    fm_conn = get_db_conn(config.FUND_MAP_DB)
    ts_conn = get_db_conn(config.TS_QUANT_DB)

    success_count = 0
    fail_count = 0

    try:
        user_id = ensure_sync_user(fm_conn)
        log.info(f"飞书同步 user_id = {user_id}")

        for rec in records:
            record_id = rec["record_id"]
            fields = extract_fields(rec)

            # 拜访人可能是多选（列表），转逗号分隔字符串
            if isinstance(fields.get("visitor_name"), list):
                fields["visitor_name"] = "、".join(str(v) for v in fields["visitor_name"] if v)

            try:
                # 解析关联记录（机构名称）
                org_name_val = fields.get("org_name")
                if isinstance(org_name_val, dict) and "_linked_record_ids" in org_name_val:
                    real_name = lookup_org_name_from_dict(token, org_name_val["_linked_record_ids"])
                    if real_name:
                        fields["org_name"] = real_name
                        fields.setdefault("_linked_org_text", org_name_val.get("_text", ""))
                    else:
                        log.warning("  无法从机构字典表解析机构名称")
                        update_bitable_record(token, record_id, {
                            "同步状态": "失败",
                            "同步日志": "无法从机构字典表解析机构名称",
                        })
                        fail_count += 1
                        continue

                # 校验必填字段
                missing = [k for k in ("org_name", "reg_num", "planned_date", "visitor_name") if not fields.get(k)]
                missing = [k for k in missing if k != "reg_num"]
                if missing:
                    log.warning(f"  缺少必填字段: {missing}")
                    update_bitable_record(token, record_id, {
                        "同步状态": "失败",
                        "同步日志": f"缺少必填字段: {', '.join(missing)}",
                    })
                    fail_count += 1
                    continue

                # 如果没有 reg_num，按名称从 ts_quant_db 查找
                if not fields.get("reg_num"):
                    reg_num = lookup_reg_num(ts_conn, fields.get("org_name", ""))
                    if reg_num:
                        fields["reg_num"] = reg_num
                        log.info(f"  模糊匹配 reg_num: {fields['org_name']} → {reg_num}")
                    else:
                        log.warning(f"  无法匹配机构: {fields.get('org_name')}，跳过")
                        update_bitable_record(token, record_id, {
                            "同步状态": "失败",
                            "同步日志": f"未匹配到机构: {fields.get('org_name')}",
                        })
                        fail_count += 1
                        continue

                # 补全机构详情
                details = lookup_org_details(ts_conn, fields["reg_num"])
                if details:
                    fields.setdefault("org_aum", details.get("org_aum", ""))
                    fields.setdefault("fund_count", details.get("fund_count", 0))
                    fields.setdefault("office_address", details.get("office_address", ""))
                    fields.setdefault("office_coordinates", details.get("office_coordinates", ""))
                    if not fields.get("org_name"):
                        fields["org_name"] = details.get("org_name", "")

                # 写入 visit_plans
                plan_id = insert_visit_plan(fm_conn, fields, user_id)
                if not plan_id:
                    log.warning(f"  写入 visit_plans 失败: {fields.get('reg_num')}")
                    update_bitable_record(token, record_id, {
                        "同步状态": "失败",
                        "同步日志": f"写入 visit_plans 失败: {fields.get('reg_num')}",
                    })
                    fail_count += 1
                    continue

                # 写入 visit_feedback
                insert_feedback(fm_conn, plan_id, fields)

                # 标记已同步
                update_bitable_record(token, record_id, {
                    "同步状态": "已同步",
                    "同步日志": f"OK | plan_id={plan_id} | {time.strftime('%Y-%m-%d %H:%M:%S')}",
                })
                success_count += 1
                log.info(f"  ✅ {fields.get('org_name', fields['reg_num'])} → plan_id={plan_id}")

            except Exception as e:
                log.error(f"  处理记录 {record_id} 出错: {e}")
                try:
                    update_bitable_record(token, record_id, {
                        "同步状态": "失败",
                        "同步日志": f"异常: {e}",
                    })
                except Exception:
                    pass
                fail_count += 1

    finally:
        fm_conn.close()
        ts_conn.close()

    message = f"同步完成: 成功 {success_count}, 失败 {fail_count}"
    log.info(f"=== {message} ===")
    return {"success": success_count, "failed": fail_count, "message": message}


def sync_once() -> dict:
    """加载配置后执行一次同步"""
    config.load_config()
    if not config.FEISHU_APP_ID or not config.FEISHU_APP_SECRET:
        return {"success": 0, "failed": 0, "message": "未配置飞书凭证，请先通过系统设置页面配置"}
    return sync()


if __name__ == "__main__":
    # get_sync_logger() 已在模块顶部初始化，无需重复配置
    result = sync_once()
    print(result["message"])
    if result["failed"] > 0:
        sys.exit(1)
