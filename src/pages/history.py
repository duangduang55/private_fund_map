"""拜访历史 + 统计概览页面（Phase 3）"""

import os
import streamlit as st
import requests
from datetime import date

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8100")


def show_history_page():
    headers = {"Authorization": f"Bearer {st.session_state.token}"}

    if "sort_status" not in st.session_state:
        st.session_state.sort_status = ""

    # ── 统计概览（点击筛选） ──
    st.markdown('<div class="filter-card">', unsafe_allow_html=True)
    st.markdown('<div class="filter-label">📈 统计概览</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    stats = {}
    try:
        resp = requests.get(f"{API_BASE}/api/stats", headers=headers, timeout=10)
        stats = resp.json()
    except Exception as e:
        st.error(f"加载统计数据失败：{e}")

    st.markdown('<div class="stat-row">', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    stat_items = [
        ("", "总计划", "total_plans"),
        ("pending", "待拜访", "pending"),
        ("completed", "已完成", "completed"),
        ("cancelled", "已取消", "cancelled"),
    ]
    for col, (status_val, label, stat_key) in zip([col1, col2, col3, col4], stat_items):
        with col:
            is_active = st.session_state.sort_status == status_val
            num = stats.get(stat_key, 0)
            if st.button(
                f"{num}\n{label}",
                key=f"stat_{status_val or 'all'}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state.sort_status = status_val
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # ── 历史记录 ──
    st.markdown('<div class="filter-card">', unsafe_allow_html=True)
    st.markdown('<div class="filter-label">📋 拜访历史记录</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    try:
        resp = requests.get(f"{API_BASE}/api/history", headers=headers, timeout=10)
        records = resp.json().get("data", [])
    except Exception as e:
        st.error(f"加载历史记录失败：{e}")
        return

    if not records:
        st.info("暂无拜访记录。")
        return

    # 筛选条件
    col1, col2, col3 = st.columns(3)
    with col1:
        status_filter = st.selectbox("状态筛选", ["全部", "待拜访", "已完成", "已取消"])
    with col2:
        has_feedback = st.selectbox("反馈情况", ["全部", "已反馈", "未反馈"])
    with col3:
        success_filter = st.selectbox("结果筛选", ["全部", "成功拜访", "未见到", "已搬迁", "地址有误", "其他"])

    status_map_cn = {"待拜访": "pending", "已完成": "completed", "已取消": "cancelled"}

    filtered = records
    origin_filter = status_filter
    if origin_filter != "全部":
        eng_status = status_map_cn.get(origin_filter, origin_filter)
        filtered = [r for r in filtered if r.get("status") == eng_status]
    if has_feedback == "已反馈":
        filtered = [r for r in filtered if r.get("feedback_id")]
    elif has_feedback == "未反馈":
        filtered = [r for r in filtered if not r.get("feedback_id")]
    if success_filter != "全部":
        filtered = [r for r in filtered if r.get("feedback_status") == success_filter]

    # 排序：按选择的统计卡片状态排前面
    if st.session_state.sort_status:
        matched = [r for r in filtered if r.get("status") == st.session_state.sort_status]
        unmatched = [r for r in filtered if r.get("status") != st.session_state.sort_status]
        matched.sort(key=lambda x: x.get("planned_date", "") or "", reverse=True)
        filtered = matched + unmatched
    else:
        filtered.sort(key=lambda x: x.get("planned_date", "") or "", reverse=True)

    # 批量查询 detail_url
    reg_nums = [r.get("reg_num", "") for r in filtered if r.get("reg_num", "")]
    detail_urls = {}
    if reg_nums:
        try:
            resp = requests.post(f"{API_BASE}/api/fund-links", json={"reg_nums": reg_nums}, timeout=10)
            detail_urls = resp.json().get("data", {})
        except Exception:
            pass

    # 表格展示
    token = st.session_state.token
    status_display = {"pending": "⏳ 待拜访", "completed": "✅ 已完成", "cancelled": "❌ 已取消"}
    rows = []
    for r in filtered:
        reg_num = r.get("reg_num", "")
        bid = r.get("batch_id", "") or ""
        pd_date = r.get("planned_date", "") or ""
        batch_link = f"/batch_detail?batch_id={bid}&token={token}&d={pd_date}#{bid}" if bid else ""
        is_starred = r.get("starred", False) in (True, "true", "t")
        org_display = f"⭐ {r.get('org_name', '')}" if is_starred else r.get("org_name", "")
        summary = r.get("feedback_summary", "") or ""
        if len(summary) > 60:
            summary = summary[:60] + "…"
        rows.append({
            "拜访计划": batch_link,
            "机构名称": org_display,
            "登记编号": reg_num,
            "计划日期": pd_date,
            "拜访人": r.get("visitor_name", ""),
            "状态": status_display.get(r.get("status", ""), r.get("status", "")),
            "反馈情况": "✅ 已反馈" if r.get("feedback_id") else "⏳ 待反馈",
            "拜访结果": r.get("feedback_status", "—"),
            "摘要": summary,
            "操作": f"{API_BASE}/detail?token={token}&reg_num={reg_num}",
            "AMAC详情": detail_urls.get(reg_num, ""),
            "创建人": r.get("creator_name", ""),
        })

    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
        column_config={
            "拜访计划": st.column_config.LinkColumn("拜访计划", display_text=r"&d=([^&]+)", width="medium"),
            "机构名称": st.column_config.TextColumn(width="medium"),
            "登记编号": st.column_config.TextColumn(width="small"),
            "计划日期": st.column_config.DateColumn(width="small"),
            "拜访人": st.column_config.TextColumn(width="small"),
            "状态": st.column_config.TextColumn(width="small"),
            "反馈情况": st.column_config.TextColumn(width="small"),
            "拜访结果": st.column_config.TextColumn(width="medium"),
            "摘要": st.column_config.TextColumn(width="large"),
            "操作": st.column_config.LinkColumn("操作", display_text="查看"),
            "AMAC详情": st.column_config.LinkColumn("AMAC详情", display_text="🔗 AMAC"),
            "创建人": st.column_config.TextColumn(width="small"),
        },
    )
    # 使 AMAC 链接在新窗口打开
    st.markdown(
        "<script>document.querySelectorAll('[data-testid^=\"stDataFrame\"] a[href*=\"gs.amac.org.cn\"]').forEach(function(a){a.target=\"_blank\";a.rel=\"noopener\"})</script>",
        unsafe_allow_html=True,
    )

    # 导出 CSV（不含"操作"列）
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2 = st.columns([1, 5])
    with col1:
        import csv
        import io
        csv_exclude = {"拜访计划", "操作", "AMAC详情"}
        csv_columns = [k for k in rows[0].keys() if k not in csv_exclude] if rows else []
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=csv_columns)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: v for k, v in r.items() if k not in csv_exclude})
        st.download_button(
            "📥 导出 CSV",
            data=output.getvalue().encode("utf-8-sig"),
            file_name=f"拜访历史_{date.today()}.csv",
            mime="text/csv",
            use_container_width=True,
        )
