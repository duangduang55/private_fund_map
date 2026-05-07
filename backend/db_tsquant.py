"""ts_quant_db 只读查询 — 私募基金数据"""

from functools import lru_cache
import re
import json
import math
from decimal import Decimal
import psycopg2
import psycopg2.extras
from backend.config import TS_QUANT_DB


def get_ts_conn():
    return psycopg2.connect(**TS_QUANT_DB)


@lru_cache(maxsize=1)
def load_distinct_values():
    """缓存筛选下拉选项（1小时自动失效由调用方控制）"""
    conn = get_ts_conn()
    queries = {
        "办公省份": "SELECT DISTINCT office_province FROM private_fund_list WHERE office_province IS NOT NULL AND office_province != '' ORDER BY office_province",
        "管理规模": "SELECT DISTINCT org_aum FROM private_fund_list WHERE org_aum IS NOT NULL AND org_aum != '' ORDER BY org_aum",
        "会员类型": "SELECT DISTINCT member_type FROM private_fund_list WHERE member_type IS NOT NULL AND member_type != '' ORDER BY member_type",
        "机构类型": "SELECT DISTINCT ins_type FROM private_fund_list WHERE ins_type IS NOT NULL AND ins_type != '' ORDER BY ins_type",
        "企业性质": "SELECT DISTINCT ent_nature FROM private_fund_list WHERE ent_nature IS NOT NULL AND ent_nature != '' ORDER BY ent_nature",
    }
    result = {}
    try:
        for key, sql in queries.items():
            with conn.cursor() as cur:
                cur.execute(sql)
                result[key] = [row[0] for row in cur.fetchall()]
    finally:
        conn.close()
    return result


def parse_keywords(text: str) -> list[str]:
    if not text or not text.strip():
        return []
    return [kw.strip() for kw in re.split(r'[,\s]+', text.strip()) if kw.strip()]


def parse_product_range(text: str):
    if not text or not text.strip():
        return None
    text = text.strip()
    m = re.match(r'^(\d+)\s*-\s*(\d+)$', text)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    m = re.match(r'^(\d+)$', text)
    if m:
        return (int(m.group(1)), int(m.group(1)))
    return None


def build_query_sql(params: dict) -> tuple[str, list]:
    """
    构建带参数的查询 SQL，返回 (sql, params_list)
    与 query_app.py 中的 build_query 逻辑保持一致
    """
    sql_parts = [
        "SELECT l.*, d.parsed_data FROM private_fund_list l "
        "LEFT JOIN private_fund_detail d ON l.reg_num = d.reg_num WHERE 1=1"
    ]
    q_params = []

    in_filters = [
        ("l.office_province", params.get("office_provinces")),
        ("l.org_aum", params.get("org_aums")),
        ("l.member_type", params.get("member_types")),
        ("l.ins_type", params.get("ins_types")),
        ("l.ent_nature", params.get("ent_natures")),
    ]
    for field, values in in_filters:
        if values:
            placeholders = ",".join(["%s"] * len(values))
            sql_parts.append(f"AND {field} IN ({placeholders})")
            q_params.extend(values)

    org_kws = params.get("org_name_keywords", [])
    if org_kws:
        name_conditions = [f"l.org_name ILIKE %s" for _ in org_kws]
        for kw in org_kws:
            q_params.append(f"%{kw}%")
        sql_parts.append(f"AND ({' OR '.join(name_conditions)})")

    pr = params.get("product_range")
    if pr:
        sql_parts.append("AND l.fund_count BETWEEN %s AND %s")
        q_params.extend([pr[0], pr[1]])

    keyword_clauses = []

    prod_kws = params.get("product_keywords", [])
    excl_liq = params.get("exclude_liquidated", True)
    if prod_kws:
        prod_conditions = []
        for kw in prod_kws:
            if excl_liq:
                prod_conditions.append(
                    "(p->>'investor_open_rate' != %s AND p->>'name' ILIKE %s)"
                )
                q_params.extend(["基金已清算", f"%{kw}%"])
            else:
                prod_conditions.append("(p->>'name' ILIKE %s)")
                q_params.append(f"%{kw}%")
        prod_where = " OR ".join(prod_conditions)
        keyword_clauses.append(
            f"EXISTS (SELECT 1 FROM jsonb_array_elements(COALESCE(d.parsed_data->'products'->'funds_after', '[]'::jsonb)) AS p WHERE {prod_where})"
        )

    exec_kws = params.get("executive_keywords", [])
    if exec_kws:
        exec_conditions = []
        for kw in exec_kws:
            exec_conditions.append(
                "(exec_data->>'name' ILIKE %s OR r->>'employer' ILIKE %s OR r->>'department' ILIKE %s)"
            )
            q_params.extend([f"%{kw}%", f"%{kw}%", f"%{kw}%"])
        exec_where = " OR ".join(exec_conditions)
        keyword_clauses.append(
            f"EXISTS (SELECT 1 FROM jsonb_array_elements(COALESCE(d.parsed_data->'executives', '[]'::jsonb)) AS exec_data, "
            f"jsonb_array_elements(COALESCE(exec_data->'resumes', '[]'::jsonb)) AS r WHERE {exec_where})"
        )

    if keyword_clauses:
        sql_parts.append(f"AND ({' OR '.join(keyword_clauses)})")

    sql_parts.append("ORDER BY l.org_name")
    return "\n".join(sql_parts), q_params


def query_funds(params: dict) -> list[dict]:
    """执行基金查询，返回字典列表（含坐标解析）"""
    sql, sql_params = build_query_sql(params)
    conn = get_ts_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, sql_params)
            rows = cur.fetchall()

        result = []
        for row in rows:
            d = dict(row)
            # 将 NaN 转为 None（JSON 安全，含 Decimal NaN）
            for k, v in d.items():
                if isinstance(v, Decimal):
                    if v.is_nan():
                        d[k] = None
                    else:
                        d[k] = float(v)
                elif isinstance(v, float) and math.isnan(v):
                    d[k] = None
            # 解析办公地坐标
            coords = d.get("office_coordinates") or ""
            lat, lng = None, None
            if coords and "," in str(coords):
                parts = str(coords).split(",")
                if len(parts) == 2:
                    try:
                        lat = float(parts[0])
                        lng = float(parts[1])
                    except ValueError:
                        pass
            d["_lat"] = lat
            d["_lng"] = lng

            # 解析 parsed_data JSONB
            pd_val = d.get("parsed_data")
            if pd_val is not None and not isinstance(pd_val, dict):
                try:
                    d["parsed_data"] = json.loads(pd_val)
                except (json.JSONDecodeError, TypeError):
                    d["parsed_data"] = None

            result.append(d)
        return result
    finally:
        conn.close()


def query_funds_for_map(params: dict) -> list[dict]:
    """查询基金数据，转为地图展示格式"""
    funds = query_funds(params)
    map_data = []
    for f in funds:
        if f["_lat"] is None or f["_lng"] is None:
            continue
        map_data.append({
            "reg_num": f.get("reg_num", ""),
            "org_name": f.get("org_name", ""),
            "org_aum": f.get("org_aum") or "未披露",
            "fund_count": f.get("fund_count") or 0,
            "office_address": f.get("office_address") or "",
            "detail_url": f.get("detail_url") or "",
            "lat": f["_lat"],
            "lng": f["_lng"],
            "leg_person": f.get("leg_person") or "",
            "ins_type": f.get("ins_type") or "",
            "member_type": f.get("member_type") or "",
            "ent_nature": f.get("ent_nature") or "",
        })
    return map_data


def check_match_reasons(reg_nums: list[str], product_keywords: list[str], executive_keywords: list[str]) -> dict:
    """检查每个 reg_num 的产品名和高管履历是否匹配关键词，返回 {reg_num: {product_match, executive_match}}"""
    result = {rn: {"product_match": False, "executive_match": False} for rn in reg_nums}
    if not reg_nums or (not product_keywords and not executive_keywords):
        return result

    conn = get_ts_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            placeholders = ",".join("%s" for _ in reg_nums)

            if product_keywords:
                for kw in product_keywords:
                    kw_param = f"%{kw}%"
                    cur.execute(
                        f"""SELECT DISTINCT d.reg_num
                            FROM private_fund_detail d
                            WHERE d.reg_num IN ({placeholders})
                            AND EXISTS (
                                SELECT 1 FROM jsonb_array_elements(
                                    COALESCE(d.parsed_data->'products'->'funds_after', '[]'::jsonb)
                                ) AS p
                                WHERE p->>'name' ILIKE %s
                            )""",
                        [*reg_nums, kw_param],
                    )
                    for row in cur.fetchall():
                        result[row["reg_num"]]["product_match"] = True

            if executive_keywords:
                for kw in executive_keywords:
                    kw_param = f"%{kw}%"
                    cur.execute(
                        f"""SELECT DISTINCT d.reg_num
                            FROM private_fund_detail d
                            WHERE d.reg_num IN ({placeholders})
                            AND EXISTS (
                                SELECT 1 FROM jsonb_array_elements(
                                    COALESCE(d.parsed_data->'executives', '[]'::jsonb)
                                ) AS exec_data,
                                jsonb_array_elements(
                                    COALESCE(exec_data->'resumes', '[]'::jsonb)
                                ) AS r
                                WHERE (exec_data->>'name' ILIKE %s OR r->>'employer' ILIKE %s OR r->>'department' ILIKE %s)
                            )""",
                        [*reg_nums, kw_param, kw_param, kw_param],
                    )
                    for row in cur.fetchall():
                        result[row["reg_num"]]["executive_match"] = True
    finally:
        conn.close()

    return result


def query_funds_by_reg_nums(reg_nums: list[str]) -> list[dict]:
    """根据 reg_num 列表批量查询机构基本信息"""
    if not reg_nums:
        return []
    conn = get_ts_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            placeholders = ",".join("%s" for _ in reg_nums)
            cur.execute(
                f"""SELECT reg_num, org_name, org_aum, fund_count, office_address,
                           office_coordinates, detail_url
                    FROM private_fund_list
                    WHERE reg_num IN ({placeholders})""",
                reg_nums,
            )
            rows = cur.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                for k, v in d.items():
                    if isinstance(v, Decimal):
                        d[k] = float(v) if not v.is_nan() else None
                    elif isinstance(v, float) and math.isnan(v):
                        d[k] = None
                result.append(d)
            return result
    finally:
        conn.close()
