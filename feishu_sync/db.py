"""数据库操作封装"""

import psycopg2
import psycopg2.extras

from .config import FEISHU_SYNC_USER


def get_db_conn(db_config: dict):
    """获取数据库连接"""
    return psycopg2.connect(**db_config)


def ensure_sync_user(conn) -> int:
    """确保飞书同步用户存在，返回 user_id"""
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE username = 'feishu_sync'")
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute(
            """INSERT INTO users (username, password_hash, display_name, role)
               VALUES ('feishu_sync', '', %s, 'member')
               ON CONFLICT (username) DO UPDATE SET display_name = EXCLUDED.display_name
               RETURNING id""",
            (FEISHU_SYNC_USER,),
        )
        conn.commit()
        return cur.fetchone()[0]


def lookup_reg_num(conn, org_name: str) -> str | None:
    """从 ts_quant_db 按机构名称模糊查找登记编号"""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT reg_num FROM private_fund_list
               WHERE org_name ILIKE %s LIMIT 1""",
            (f"%{org_name}%",),
        )
        row = cur.fetchone()
        return row[0] if row else None


def lookup_org_details(conn, reg_num: str) -> dict:
    """从 ts_quant_db 查询机构详情"""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """SELECT org_name, org_aum, fund_count,
                      office_address, office_coordinates
               FROM private_fund_list WHERE reg_num = %s""",
            (reg_num,),
        )
        row = cur.fetchone()
        return dict(row) if row else {}


def insert_visit_plan(conn, fields: dict, user_id: int) -> int | None:
    """写入拜访计划记录，返回 plan_id"""
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO visit_plans
               (reg_num, org_name, org_aum, fund_count,
                office_address, office_coordinates, planned_date, visitor_name,
                user_id, status, remark)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'completed', %s)
               RETURNING id""",
            (
                fields["reg_num"],
                fields["org_name"],
                fields.get("org_aum", ""),
                fields.get("fund_count", 0),
                fields.get("office_address", ""),
                fields.get("office_coordinates", ""),
                fields["planned_date"],
                fields["visitor_name"],
                user_id,
                fields.get("remark", "来自飞书表单同步"),
            ),
        )
        conn.commit()
        row = cur.fetchone()
        return row[0] if row else None


def insert_feedback(conn, plan_id: int, fields: dict):
    """写入拜访反馈"""
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO visit_feedback
               (visit_plan_id, visit_date, visitor_name, visit_status,
                has_business_card, has_contact_info,
                summary, communication_detail, follow_up_suggestions, tags)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               ON CONFLICT (visit_plan_id) DO UPDATE SET
                   visit_date = EXCLUDED.visit_date,
                   visitor_name = EXCLUDED.visitor_name,
                   visit_status = EXCLUDED.visit_status,
                   has_business_card = EXCLUDED.has_business_card,
                   has_contact_info = EXCLUDED.has_contact_info,
                   summary = EXCLUDED.summary,
                   communication_detail = EXCLUDED.communication_detail,
                   follow_up_suggestions = EXCLUDED.follow_up_suggestions,
                   tags = EXCLUDED.tags,
                   updated_at = now()""",
            (
                plan_id,
                fields.get("visit_date", fields["planned_date"]),
                fields["visitor_name"],
                fields.get("visit_status", "其他"),
                fields.get("has_business_card", False),
                fields.get("has_contact_info", False),
                fields.get("summary", ""),
                fields.get("communication_detail", ""),
                fields.get("follow_up_suggestions", ""),
                fields.get("tags", []),
            ),
        )
        conn.commit()
