"""fund_map_db 读写 — 业务数据（用户、购物车、计划、反馈）"""

import psycopg2
import psycopg2.extras
from src.backend.config import FUND_MAP_DB


def get_fm_conn():
    return psycopg2.connect(**FUND_MAP_DB)


# ── 用户 ──

def get_user_by_username(username: str) -> dict | None:
    conn = get_fm_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE username = %s", (username,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> dict | None:
    conn = get_fm_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def create_user(username: str, password_hash: str, display_name: str, role: str = "member") -> dict | None:
    conn = get_fm_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO users (username, password_hash, display_name, role) VALUES (%s, %s, %s, %s) RETURNING id, username, display_name, role, created_at",
                (username, password_hash, display_name, role),
            )
            conn.commit()
            row = cur.fetchone()
            return dict(row) if row else None
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return None
    finally:
        conn.close()


# ── 拜访标记（用于地图显示已拜访状态） ──

def get_visit_status_reg_nums() -> tuple[set[str], set[str]]:
    """获取已拜访（completed）和待拜访（only pending）的 reg_num 集合"""
    conn = get_fm_conn()
    try:
        with conn.cursor() as cur:
            # 有过 completed 记录的 → 已拜访
            cur.execute("SELECT DISTINCT reg_num FROM visit_plans WHERE status = 'completed'")
            completed = {row[0] for row in cur.fetchall()}
            # 有 pending 记录但无 completed 记录的 → 待拜访
            cur.execute(
                """SELECT DISTINCT vp.reg_num FROM visit_plans vp
                   WHERE vp.status = 'pending'
                   AND NOT EXISTS (SELECT 1 FROM visit_plans vp2 WHERE vp2.reg_num = vp.reg_num AND vp2.status = 'completed')"""
            )
            pending = {row[0] for row in cur.fetchall()}
            return completed, pending
    finally:
        conn.close()


def get_latest_visit_info(reg_num: str) -> dict | None:
    """获取某个私募的最新已完成拜访记录"""
    conn = get_fm_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT vp.visitor_name, vp.planned_date, vf.summary
                   FROM visit_plans vp
                   LEFT JOIN visit_feedback vf ON vf.visit_plan_id = vp.id
                   WHERE vp.reg_num = %s AND vp.status = 'completed'
                   ORDER BY vp.planned_date DESC LIMIT 1""",
                (reg_num,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def get_visit_history(reg_num: str, limit: int = 5) -> list[dict]:
    """获取某个私募的拜访历史（多条，按时间倒序）"""
    conn = get_fm_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT vp.id, vp.visitor_name, vp.planned_date, vp.status,
                          vf.visit_status, vf.summary, vf.tags
                   FROM visit_plans vp
                   LEFT JOIN visit_feedback vf ON vf.visit_plan_id = vp.id
                   WHERE vp.reg_num = %s AND vp.status IN ('completed', 'pending')
                   ORDER BY vp.planned_date DESC, vp.created_at DESC
                   LIMIT %s""",
                (reg_num, limit),
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


# ── 购物车（待拜访清单） ──

def get_cart_items(user_id: int) -> list[dict]:
    conn = get_fm_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM visit_cart WHERE user_id = %s ORDER BY created_at",
                (user_id,),
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def add_to_cart(user_id: int, fund: dict) -> bool:
    conn = get_fm_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO visit_cart (user_id, reg_num, org_name, org_aum, fund_count, office_address, office_coordinates)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT DO NOTHING""",
                (
                    user_id,
                    fund.get("reg_num", ""),
                    fund.get("org_name", ""),
                    fund.get("org_aum", ""),
                    fund.get("fund_count", 0),
                    fund.get("office_address", ""),
                    f"{fund.get('lat', '')},{fund.get('lng', '')}",
                ),
            )
            conn.commit()
            return cur.rowcount > 0
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def remove_from_cart(cart_id: int, user_id: int) -> bool:
    conn = get_fm_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM visit_cart WHERE id = %s AND user_id = %s",
                (cart_id, user_id),
            )
            conn.commit()
            return cur.rowcount > 0
    finally:
        conn.close()


def clear_cart(user_id: int) -> None:
    conn = get_fm_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM visit_cart WHERE user_id = %s", (user_id,))
            conn.commit()
    finally:
        conn.close()


# ── 星标切换 ──

def toggle_cart_star(cart_id: int, user_id: int) -> bool:
    conn = get_fm_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE visit_cart SET starred = NOT COALESCE(starred, false) WHERE id = %s AND user_id = %s RETURNING starred",
                (cart_id, user_id),
            )
            conn.commit()
            return cur.rowcount > 0
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def set_plan_star(plan_id: int, user_id: int, starred: bool) -> bool:
    """设置拜访计划的星标状态"""
    conn = get_fm_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE visit_plans SET starred = %s WHERE id = %s AND user_id = %s",
                (starred, plan_id, user_id),
            )
            conn.commit()
            return cur.rowcount > 0
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


# ── 拜访计划 ──


def get_plan_by_id(plan_id: int) -> dict | None:
    """查询拜访计划完整记录"""
    conn = get_fm_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM visit_plans WHERE id = %s", (plan_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def get_plan_owner_id(plan_id: int) -> int | None:
    """查询拜访计划的所有者 user_id"""
    conn = get_fm_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT user_id FROM visit_plans WHERE id = %s", (plan_id,))
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()


def create_plans_from_cart(user_id: int, planned_date: str, visitor_name: str, batch_id: str = "") -> list[dict]:
    """将购物车中的条目转为拜访计划（同批次共享 batch_id，星标状态继承）"""
    items = get_cart_items(user_id)
    if not items:
        return []
    conn = get_fm_conn()
    created = []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            for item in items:
                cur.execute(
                    """INSERT INTO visit_plans
                       (reg_num, org_name, org_aum, fund_count, office_address, office_coordinates,
                        planned_date, visitor_name, user_id, status, batch_id, starred)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s)
                       RETURNING id, reg_num, org_name, planned_date, visitor_name, status, batch_id, starred""",
                    (
                        item["reg_num"],
                        item["org_name"],
                        item["org_aum"],
                        item["fund_count"],
                        item["office_address"],
                        item["office_coordinates"],
                        planned_date,
                        visitor_name,
                        user_id,
                        batch_id,
                        item.get("starred", False),
                    ),
                )
                row = cur.fetchone()
                if row:
                    created.append(dict(row))
            conn.commit()
        # 清空购物车
        clear_cart(user_id)
        return created
    except Exception:
        conn.rollback()
        return []
    finally:
        conn.close()


def get_user_plans(user_id: int, role: str) -> list[dict]:
    conn = get_fm_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if role == "admin":
                cur.execute(
                    "SELECT vp.*, u.display_name as creator_name FROM visit_plans vp LEFT JOIN users u ON vp.user_id = u.id ORDER BY vp.planned_date DESC"
                )
            else:
                cur.execute(
                    "SELECT vp.*, u.display_name as creator_name FROM visit_plans vp LEFT JOIN users u ON vp.user_id = u.id WHERE vp.user_id = %s ORDER BY vp.planned_date DESC",
                    (user_id,),
                )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_plans_by_batch(batch_id: str) -> list[dict]:
    """按 batch_id 查询批次内所有计划（含反馈信息）"""
    conn = get_fm_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT vp.*, u.display_name as creator_name,
                          vf.id as feedback_id, vf.visit_status as feedback_status
                   FROM visit_plans vp
                   LEFT JOIN users u ON vp.user_id = u.id
                   LEFT JOIN visit_feedback vf ON vf.visit_plan_id = vp.id
                   WHERE vp.batch_id = %s
                   ORDER BY vp.id""",
                (batch_id,),
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


# ── 拜访反馈 ──

def get_feedback_by_plan_id(plan_id: int) -> dict | None:
    """获取某个计划的反馈"""
    conn = get_fm_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM visit_feedback WHERE visit_plan_id = %s", (plan_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def upsert_feedback(plan_id: int, data: dict) -> dict | None:
    """创建或更新拜访反馈（基于 visit_plan_id UNIQUE 约束）"""
    conn = get_fm_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """INSERT INTO visit_feedback
                   (visit_plan_id, visit_date, visitor_name, visit_status,
                    has_business_card, has_contact_info,
                    summary, communication_detail, follow_up_suggestions, tags)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (visit_plan_id)
                   DO UPDATE SET
                       visit_date = EXCLUDED.visit_date,
                       visitor_name = EXCLUDED.visitor_name,
                       visit_status = EXCLUDED.visit_status,
                       has_business_card = EXCLUDED.has_business_card,
                       has_contact_info = EXCLUDED.has_contact_info,
                       summary = EXCLUDED.summary,
                       communication_detail = EXCLUDED.communication_detail,
                       follow_up_suggestions = EXCLUDED.follow_up_suggestions,
                       tags = EXCLUDED.tags,
                       updated_at = now()
                   RETURNING *""",
                (
                    plan_id,
                    data.get("visit_date"),
                    data.get("visitor_name"),
                    data.get("visit_status"),
                    data.get("has_business_card", False),
                    data.get("has_contact_info", False),
                    data.get("summary", ""),
                    data.get("communication_detail", ""),
                    data.get("follow_up_suggestions", ""),
                    data.get("tags", []),
                ),
            )
            conn.commit()
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception:
        conn.rollback()
        return None
    finally:
        conn.close()


def update_plan_status(plan_id: int, status: str, remark: str = "") -> bool:
    """更新拜访计划状态，可选更新备注"""
    conn = get_fm_conn()
    try:
        with conn.cursor() as cur:
            if remark:
                cur.execute(
                    "UPDATE visit_plans SET status = %s, remark = %s, updated_at = now() WHERE id = %s",
                    (status, remark, plan_id),
                )
            else:
                cur.execute(
                    "UPDATE visit_plans SET status = %s, updated_at = now() WHERE id = %s",
                    (status, plan_id),
                )
            conn.commit()
            return cur.rowcount > 0
    finally:
        conn.close()


def get_plans_with_feedback(user_id: int, role: str) -> list[dict]:
    """获取计划列表（含反馈信息），用于历史页面"""
    conn = get_fm_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if role == "admin":
                cur.execute(
                    """SELECT vp.*, u.display_name as creator_name,
                              vf.id as feedback_id, vf.visit_status as feedback_status,
                              vf.summary as feedback_summary, vf.tags,
                              vf.has_business_card
                      FROM visit_plans vp
                      LEFT JOIN users u ON vp.user_id = u.id
                      LEFT JOIN visit_feedback vf ON vf.visit_plan_id = vp.id
                      ORDER BY vp.planned_date DESC"""
                )
            else:
                cur.execute(
                    """SELECT vp.*, u.display_name as creator_name,
                              vf.id as feedback_id, vf.visit_status as feedback_status,
                              vf.summary as feedback_summary, vf.tags,
                              vf.has_business_card
                      FROM visit_plans vp
                      LEFT JOIN users u ON vp.user_id = u.id
                      LEFT JOIN visit_feedback vf ON vf.visit_plan_id = vp.id
                      WHERE vp.user_id = %s
                      ORDER BY vp.planned_date DESC""",
                    (user_id,),
                )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_visit_stats(user_id: int, role: str) -> dict:
    """拜访统计概览"""
    conn = get_fm_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if role == "admin":
                cur.execute(
                    """SELECT
                      COUNT(*)::int as total_plans,
                      COUNT(*) FILTER (WHERE vp.status = 'pending')::int as pending,
                      COUNT(*) FILTER (WHERE vp.status = 'completed')::int as completed,
                      COUNT(*) FILTER (WHERE vp.status = 'cancelled')::int as cancelled,
                      COUNT(vf.id)::int as feedback_count,
                      COUNT(vf.id) FILTER (WHERE vf.visit_status = '成功')::int as success_visits
                      FROM visit_plans vp
                      LEFT JOIN visit_feedback vf ON vf.visit_plan_id = vp.id"""
                )
            else:
                cur.execute(
                    """SELECT
                      COUNT(*)::int as total_plans,
                      COUNT(*) FILTER (WHERE vp.status = 'pending')::int as pending,
                      COUNT(*) FILTER (WHERE vp.status = 'completed')::int as completed,
                      COUNT(*) FILTER (WHERE vp.status = 'cancelled')::int as cancelled,
                      COUNT(vf.id)::int as feedback_count,
                      COUNT(vf.id) FILTER (WHERE vf.visit_status = '成功')::int as success_visits
                      FROM visit_plans vp
                      LEFT JOIN visit_feedback vf ON vf.visit_plan_id = vp.id
                      WHERE vp.user_id = %s""",
                    (user_id,),
                )
            row = cur.fetchone()
            return dict(row) if row else {}
    finally:
        conn.close()


# ── 自动过期（7天未反馈自动取消） ──

def auto_expire_plans() -> int:
    """将超过7天未反馈的 pending 计划自动取消，返回取消数量"""
    conn = get_fm_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE visit_plans SET status = 'cancelled', remark = '超期自动取消', updated_at = now()
                   WHERE status = 'pending'
                   AND planned_date < CURRENT_DATE - INTERVAL '7 days'
                   AND NOT EXISTS (SELECT 1 FROM visit_feedback vf WHERE vf.visit_plan_id = visit_plans.id)
                   RETURNING id"""
            )
            conn.commit()
            return cur.rowcount
    except Exception:
        conn.rollback()
        return 0
    finally:
        conn.close()


# ── 批量补录已拜访（项目上线前已完成的拜访） ──

def batch_import_visited(user_id: int, records: list[dict]) -> int:
    """批量创建已完成的拜访计划（补录），返回成功条数"""
    conn = get_fm_conn()
    count = 0
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            for rec in records:
                try:
                    cur.execute(
                        """INSERT INTO visit_plans
                           (reg_num, org_name, org_aum, fund_count, office_address, office_coordinates,
                            planned_date, visitor_name, user_id, status)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'completed')
                           ON CONFLICT DO NOTHING""",
                        (
                            rec.get("reg_num", ""),
                            rec.get("org_name", ""),
                            rec.get("org_aum", ""),
                            rec.get("fund_count", 0),
                            rec.get("office_address", ""),
                            rec.get("office_coordinates", ""),
                            rec.get("planned_date", ""),
                            rec.get("visitor_name", ""),
                            user_id,
                        ),
                    )
                    if cur.rowcount > 0:
                        count += 1
                except Exception:
                    pass
            conn.commit()
        return count
    except Exception:
        conn.rollback()
        return 0
    finally:
        conn.close()


def batch_import_with_feedback(user_id: int, records: list[dict]) -> int:
    """批量补录已拜访（含反馈），创建 visit_plans(completed) + visit_feedback(手动补录)"""
    conn = get_fm_conn()
    count = 0
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            for rec in records:
                try:
                    # 创建已完成计划
                    cur.execute(
                        """INSERT INTO visit_plans
                           (reg_num, org_name, org_aum, fund_count, office_address, office_coordinates,
                            planned_date, visitor_name, user_id, status)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'completed')
                           RETURNING id""",
                        (
                            rec.get("reg_num", ""),
                            rec.get("org_name", rec.get("reg_num", "")),
                            rec.get("org_aum", ""),
                            rec.get("fund_count", 0),
                            rec.get("office_address", ""),
                            rec.get("office_coordinates", ""),
                            rec.get("planned_date", rec.get("visit_date", "")),
                            rec.get("visitor_name", ""),
                            user_id,
                        ),
                    )
                    row = cur.fetchone()
                    if not row:
                        continue
                    plan_id = row["id"]

                    # 构建 tags：追加"手动补录"标记
                    tags = list(rec.get("tags", []))
                    if "手动补录" not in tags:
                        tags.append("手动补录")

                    # 创建反馈
                    cur.execute(
                        """INSERT INTO visit_feedback
                           (visit_plan_id, visit_date, visitor_name, visit_status,
                            has_business_card, has_contact_info,
                            summary, communication_detail, follow_up_suggestions, tags)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (
                            plan_id,
                            rec.get("planned_date", rec.get("visit_date", "")),
                            rec.get("visitor_name", ""),
                            '其他',
                            rec.get("has_business_card", False),
                            rec.get("has_contact_info", False),
                            rec.get("summary", ""),
                            rec.get("communication_detail", ""),
                            rec.get("follow_up_suggestions", ""),
                            tags,
                        ),
                    )
                    count += 1
                except Exception:
                    pass
            conn.commit()
        return count
    except Exception:
        conn.rollback()
        return 0
    finally:
        conn.close()


# ── 删除拜访计划 ──

def delete_plan(plan_id: int, user_id: int, role: str) -> bool:
    """删除单个拜访计划及关联反馈。admin 可删任意记录，member 仅删自己的。"""
    conn = get_fm_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM visit_feedback WHERE visit_plan_id = %s", (plan_id,))
            if role == "admin":
                cur.execute("DELETE FROM visit_plans WHERE id = %s", (plan_id,))
            else:
                cur.execute("DELETE FROM visit_plans WHERE id = %s AND user_id = %s", (plan_id, user_id))
            conn.commit()
            return cur.rowcount > 0
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def delete_plans_by_batch(batch_id: str, user_id: int, role: str) -> int:
    """删除某批次下的所有计划及关联反馈，返回删除条数。"""
    conn = get_fm_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM visit_feedback WHERE visit_plan_id IN (SELECT id FROM visit_plans WHERE batch_id = %s)"
                if role == "admin" else
                "DELETE FROM visit_feedback WHERE visit_plan_id IN (SELECT id FROM visit_plans WHERE batch_id = %s AND user_id = %s)",
                (batch_id,) if role == "admin" else (batch_id, user_id),
            )
            if role == "admin":
                cur.execute("DELETE FROM visit_plans WHERE batch_id = %s", (batch_id,))
            else:
                cur.execute("DELETE FROM visit_plans WHERE batch_id = %s AND user_id = %s", (batch_id, user_id))
            conn.commit()
            return cur.rowcount
    except Exception:
        conn.rollback()
        return 0
    finally:
        conn.close()


def get_user_tags(user_id: int) -> list[str]:
    """获取用户历史反馈中使用过的所有标签（去重、排序）"""
    conn = get_fm_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT DISTINCT unnest(vf.tags) as tag
                FROM visit_feedback vf
                JOIN visit_plans vp ON vf.visit_plan_id = vp.id
                WHERE vp.user_id = %s
                  AND vf.tags IS NOT NULL
                  AND cardinality(vf.tags) > 0
                ORDER BY tag
            """, (user_id,))
            return [row["tag"] for row in cur.fetchall()]
    finally:
        conn.close()


# ── 私募拜访记录详情 ──

def get_all_visit_records(reg_num: str) -> list[dict]:
    """获取某个私募的所有拜访记录（含反馈），按计划日期降序"""
    conn = get_fm_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT vp.id, vp.reg_num, vp.org_name, vp.org_aum, vp.fund_count,
                          vp.planned_date, vp.visitor_name, vp.status, vp.remark,
                          vf.id as feedback_id, vf.visit_status, vf.summary,
                          vf.communication_detail, vf.follow_up_suggestions, vf.tags,
                          vf.has_business_card, vf.has_contact_info,
                          vf.visit_date, vf.visitor_name as feedback_visitor
                   FROM visit_plans vp
                   LEFT JOIN visit_feedback vf ON vf.visit_plan_id = vp.id
                   WHERE vp.reg_num = %s
                   ORDER BY vp.planned_date DESC, vp.created_at DESC""",
                (reg_num,),
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_fund_tags(reg_num: str) -> list[str]:
    """获取某个私募的所有标签（去重）"""
    conn = get_fm_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT DISTINCT unnest(vf.tags) as tag
                   FROM visit_feedback vf
                   JOIN visit_plans vp ON vf.visit_plan_id = vp.id
                   WHERE vp.reg_num = %s
                     AND vf.tags IS NOT NULL
                     AND cardinality(vf.tags) > 0
                   ORDER BY tag""",
                (reg_num,),
            )
            return [row["tag"] for row in cur.fetchall()]
    finally:
        conn.close()
