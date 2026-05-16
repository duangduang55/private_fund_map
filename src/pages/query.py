"""私募基金数据查询与导出页面（适配 Streamlit 多页面）"""

import os
import streamlit as st
import pandas as pd
import json
import re
import io
from datetime import datetime
import requests

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8100")


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


def get_matched_products(parsed_data, keywords, exclude_liquidated):
    if not parsed_data or not keywords:
        return []
    products = parsed_data.get("products", {}).get("funds_after", [])
    matched = []
    for p in products:
        if exclude_liquidated and p.get("investor_open_rate") == "基金已清算":
            continue
        name = p.get("name", "")
        if any(kw.lower() in name.lower() for kw in keywords):
            matched.append(name)
    return matched


def get_matched_executives(parsed_data, keywords):
    if not parsed_data or not keywords:
        return []
    execs = parsed_data.get("executives", [])
    if not execs:
        return []
    has_hit = False
    for e in execs:
        name = e.get("name", "")
        if any(kw.lower() in name.lower() for kw in keywords):
            has_hit = True
            break
        for r in e.get("resumes", []):
            employer = r.get("employer", "")
            dept = r.get("department", "")
            if any(kw.lower() in employer.lower() or kw.lower() in dept.lower() for kw in keywords):
                has_hit = True
                break
        if has_hit:
            break
    if not has_hit:
        return []
    result = []
    for e in execs:
        name = e.get("name", "")
        if not e.get("resumes"):
            result.append(name)
            continue
        latest = e["resumes"][0]
        employer = latest.get("employer", "")
        dept = latest.get("department", "")
        if employer and dept:
            result.append(f"{name}({employer}-{dept})")
        elif employer:
            result.append(f"{name}({employer})")
        else:
            result.append(name)
    return result


# ── 字段映射 ──
COLUMN_MAP = {
    "reg_num": "登记编号", "sys_id": "系统ID", "org_name": "机构名称",
    "lic_num": "营业执照号", "leg_person": "法定代表人", "act_controller": "实际控制人",
    "est_date": "成立时间", "reg_date": "登记时间", "has_products": "是否有产品",
    "org_aum": "管理规模", "detail_url": "详情页URL", "reg_address": "注册地址",
    "reg_province": "注册省份", "reg_city": "注册城市", "fund_count": "基金数量",
    "paid_capital": "实缴资本(万)", "reg_capital": "认缴资本(万)", "emp_num": "全职员工人数",
    "fund_pra_num": "从业人数", "reg_coordinates": "注册地坐标", "office_coordinates": "办公地坐标",
    "office_address": "办公地址", "office_province": "办公省份", "office_city": "办公城市",
    "has_special_notice": "特别提示", "has_credit_notice": "信用提示", "ent_nature": "企业性质",
    "ins_type": "机构类型", "main_invest_type": "主要投资类型", "member_type": "会员类型",
    "org_form": "组织形式", "created_at": "创建时间", "updated_at": "更新时间",
}
DISPLAY_COLUMNS = list(COLUMN_MAP.values())


def show_query_page():
    """查询页面主函数"""
    st.markdown('<div class="filter-card">', unsafe_allow_html=True)
    st.markdown('<div class="filter-label">📌 筛选条件</div>', unsafe_allow_html=True)

    # 从 API 加载下拉选项
    try:
        resp = requests.get(f"{API_BASE}/api/filters", timeout=10)
        dv = resp.json()
    except Exception as e:
        st.error(f"无法加载筛选选项：{e}")
        st.info("请确认 FastAPI 后端已启动（localhost:8100）")
        return

    col1, col2, col3 = st.columns(3)
    with col1:
        selected_provinces = st.multiselect("办公省份", dv.get("办公省份", []), placeholder="全部")
    with col2:
        selected_aums = st.multiselect("管理规模", dv.get("管理规模", []), placeholder="全部")
    with col3:
        selected_natures = st.multiselect("企业性质", dv.get("企业性质", []), placeholder="全部")

    col1, col2, col3 = st.columns(3)
    with col1:
        selected_members = st.multiselect("会员类型", dv.get("会员类型", []), placeholder="全部")
    with col2:
        selected_ins = st.multiselect("机构类型", dv.get("机构类型", []), placeholder="全部")
    with col3:
        product_range_text = st.text_input(
            "产品数量", placeholder="如 0-9 或 13-20",
            help="输入范围格式，如 0-9（≤9只）或 13-20（13≤x≤20）。不填则不限制。",
        )

    col1, col2, col3 = st.columns([1.8, 1, 1.8])
    with col1:
        product_name_query = st.text_input(
            "产品名称模糊查询", placeholder="多个关键词用空格隔开",
            help="输入关键词搜索产品名称，多个关键词用空格或逗号分隔，匹配任一即满足条件。",
        )
    with col2:
        exclude_liq = st.checkbox("排除已清算产品", value=True)
    with col3:
        executive_query = st.text_input(
            "高管履历模糊查询", placeholder="搜索姓名/单位/职务/部门",
            help="搜索高管姓名、任职单位、职务或部门，多个关键词用空格或逗号分隔。",
        )

    col1, col2, col3 = st.columns(3)
    with col1:
        org_name_query = st.text_input(
            "机构名称模糊查询", placeholder="多个关键词用空格隔开",
            help="输入关键词搜索机构名称，多个关键词用空格或逗号分隔，匹配任一即满足条件。",
        )
    with col2:
        st.markdown("<div></div>", unsafe_allow_html=True)
    with col3:
        st.markdown("<div></div>", unsafe_allow_html=True)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    query_col1, query_col2, query_col3 = st.columns([1, 2, 1])
    with query_col2:
        query_clicked = st.button("🔍 执行查询", use_container_width=True)

    # ── 保存查询参数，用于"在地图上显示" ──
    query_params = {}
    if selected_provinces:
        query_params["office_provinces"] = ",".join(selected_provinces)
    if selected_aums:
        query_params["org_aums"] = ",".join(selected_aums)
    if selected_members:
        query_params["member_types"] = ",".join(selected_members)
    if selected_ins:
        query_params["ins_types"] = ",".join(selected_ins)
    if selected_natures:
        query_params["ent_natures"] = ",".join(selected_natures)
    if product_range_text.strip():
        query_params["product_range"] = product_range_text.strip()
    if product_name_query.strip():
        query_params["product_name_query"] = product_name_query.strip()
    query_params["exclude_liquidated"] = "true" if exclude_liq else "false"
    if executive_query.strip():
        query_params["executive_query"] = executive_query.strip()
    if org_name_query.strip():
        query_params["org_name_query"] = org_name_query.strip()

    st.markdown("</div>", unsafe_allow_html=True)

    if query_clicked:
        product_kws = parse_keywords(product_name_query)
        exec_kws = parse_keywords(executive_query)

        # 保存查询参数供"在地图上显示"使用
        if query_params:
            st.session_state.last_query_params = query_params

        try:
            api_params = {
                "office_provinces": ",".join(selected_provinces) if selected_provinces else None,
                "org_aums": ",".join(selected_aums) if selected_aums else None,
                "member_types": ",".join(selected_members) if selected_members else None,
                "ins_types": ",".join(selected_ins) if selected_ins else None,
                "ent_natures": ",".join(selected_natures) if selected_natures else None,
                "product_range": product_range_text.strip() or None,
                "product_name_query": product_name_query.strip() or None,
                "exclude_liquidated": exclude_liq,
                "executive_query": executive_query.strip() or None,
                "org_name_query": org_name_query.strip() or None,
                "page_size": 20000,
            }
            api_params = {k: v for k, v in api_params.items() if v is not None}

            with st.spinner("正在查询..."):
                headers = {"Authorization": f"Bearer {st.session_state.token}"}
                resp = requests.get(f"{API_BASE}/api/funds", params=api_params, headers=headers, timeout=60)
                if resp.status_code == 200:
                    result = resp.json()
                    df = pd.DataFrame(result["data"])
                else:
                    st.error(f"查询失败：{resp.text}")
                    return
        except Exception as e:
            st.error(f"查询失败：{e}")
            return

        if df.empty:
            st.warning("未找到匹配条件的管理人记录。")
            return

        # 添加命中列
        product_hits = []
        executive_hits = []
        for _, row in df.iterrows():
            parsed = row.get("parsed_data")
            if parsed is not None and not pd.isna(parsed):
                if isinstance(parsed, str):
                    try:
                        parsed = json.loads(parsed)
                    except json.JSONDecodeError:
                        parsed = None
            else:
                parsed = None

            if product_kws:
                matched_products = get_matched_products(parsed, product_kws, exclude_liq)
                product_hits.append("；".join(matched_products) if matched_products else "")
            else:
                product_hits.append("")

            if exec_kws:
                matched_execs = get_matched_executives(parsed, exec_kws)
                executive_hits.append("；".join(matched_execs) if matched_execs else "")
            else:
                executive_hits.append("")

        df["产品名称命中"] = product_hits
        df["高管履历命中"] = executive_hits

        # 构建展示 DataFrame
        rename_map = {k: v for k, v in COLUMN_MAP.items() if k in df.columns}
        display_df = df.rename(columns=rename_map)
        display_df = display_df.drop(columns=["parsed_data"], errors="ignore")

        has_product_hits = product_kws and df["产品名称命中"].str.len().sum() > 0
        has_exec_hits = exec_kws and df["高管履历命中"].str.len().sum() > 0

        show_cols = [c for c in DISPLAY_COLUMNS if c in display_df.columns]
        if has_product_hits:
            show_cols.append("产品名称命中")
        if has_exec_hits:
            show_cols.append("高管履历命中")
        display_df = display_df[show_cols]

        # 结果统计
        total = len(display_df)
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:1rem;margin:1rem 0;flex-wrap:wrap;">'
            f'<span class="stats-badge">📊 共 {total} 条记录</span>'
            f'{"<span class=\"stats-badge\">🏷️ 产品名称命中</span>" if has_product_hits else ""}'
            f'{"<span class=\"stats-badge\">👤 高管履历命中</span>" if has_exec_hits else ""}'
            f'</div>',
            unsafe_allow_html=True,
        )

        # 表格展示
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        # ── 操作区 ──
        col_a, col_b, col_c = st.columns([1, 1, 1])

        # 在地图上显示
        with col_a:
            token = st.session_state.token
            qs = "&".join(f"{k}={v}" for k, v in query_params.items() if v)
            map_url = f"{API_BASE}/map?token={token}&{qs}"
            st.markdown(
                f'<a href="{map_url}" target="_blank">'
                f'<button style="width:100%;padding:0.5rem 1rem;background:#2563eb;'
                f'color:white;border:none;border-radius:6px;font-size:14px;cursor:pointer;">🗺️ 在地图上显示</button></a>',
                unsafe_allow_html=True,
            )

        # 导出 Excel
        with col_b:
            export_cols = [c for c in DISPLAY_COLUMNS if c in display_df.columns]
            export_df = display_df[export_cols].copy()
            if has_product_hits:
                export_df["产品名称命中"] = display_df["产品名称命中"]
            if has_exec_hits:
                export_df["高管履历命中"] = display_df["高管履历命中"]

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                export_df.to_excel(writer, index=False, sheet_name="私募管理人查询结果")
                worksheet = writer.sheets["私募管理人查询结果"]
                for i, col_name in enumerate(export_df.columns):
                    vals = export_df[col_name].dropna()
                    max_len = max(
                        vals.astype(str).map(len).max() if len(vals) > 0 else 0,
                        len(str(col_name)),
                    )
                    worksheet.column_dimensions[chr(65 + i) if i < 26 else "A"].width = min(max_len + 4, 60)

            excel_buffer.seek(0)
            st.download_button(
                label="📥 导出 Excel",
                data=excel_buffer,
                file_name=f"私募管理人查询_{timestamp}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        with col_c:
            if st.button("📋 加入待拜访清单（全部结果）", use_container_width=True):
                # 逐条添加至购物车
                token = st.session_state.token
                headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                added = 0
                for _, row in df.iterrows():
                    coords = str(row.get("office_coordinates", "") or "")
                    lat, lng = 0, 0
                    if coords and "," in coords:
                        try:
                            parts = coords.split(",")
                            lat, lng = float(parts[0]), float(parts[1])
                        except ValueError:
                            pass
                    payload = {
                        "reg_num": str(row.get("reg_num", "")),
                        "org_name": str(row.get("org_name", "")),
                        "org_aum": str(row.get("org_aum", "") or ""),
                        "fund_count": int(row.get("fund_count", 0) or 0),
                        "office_address": str(row.get("office_address", "") or ""),
                        "lat": lat,
                        "lng": lng,
                    }
                    try:
                        r = requests.post(f"{API_BASE}/api/cart/add", json=payload, headers=headers, timeout=5)
                        if r.json().get("success"):
                            added += 1
                    except Exception:
                        pass
                st.success(f"已将 {added} 条记录加入待拜访清单")
