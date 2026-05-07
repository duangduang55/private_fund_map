"""拜访历史 + 统计概览页面（Phase 3）"""

import streamlit as st
import requests
from datetime import date

API_BASE = "http://localhost:8000"


def show_history_page():
    headers = {"Authorization": f"Bearer {st.session_state.token}"}

    # ── 统计概览 ──
    st.markdown('<div class="filter-card">', unsafe_allow_html=True)
    st.markdown('<div class="filter-label">📈 统计概览</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    stats = {}
    try:
        resp = requests.get(f"{API_BASE}/api/stats", headers=headers, timeout=10)
        stats = resp.json()
    except Exception as e:
        st.error(f"加载统计数据失败：{e}")

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.markdown(
            f'<div class="stat-card"><div class="num">{stats.get("total_plans", 0)}</div><div class="label">总计划</div></div>',
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f'<div class="stat-card"><div class="num" style="color:#fbbf24;">{stats.get("pending", 0)}</div><div class="label">待拜访</div></div>',
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            f'<div class="stat-card"><div class="num" style="color:#34d399;">{stats.get("completed", 0)}</div><div class="label">已完成</div></div>',
            unsafe_allow_html=True,
        )
    with col4:
        st.markdown(
            f'<div class="stat-card"><div class="num" style="color:#ef4444;">{stats.get("cancelled", 0)}</div><div class="label">已取消</div></div>',
            unsafe_allow_html=True,
        )
    with col5:
        total = stats.get("completed", 0) or 0
        feedback = stats.get("feedback_count", 0) or 0
        st.markdown(
            f'<div class="stat-card"><div class="num" style="color:#0ea5e9;">{feedback}</div><div class="label">已反馈</div></div>',
            unsafe_allow_html=True,
        )
    with col6:
        total_visits = stats.get("success_visits", 0) or 0
        feedback_total = stats.get("feedback_count", 0) or 0
        rate = f"{total_visits}/{feedback_total}"
        st.markdown(
            f'<div class="stat-card"><div class="num" style="color:#00d4aa;">{rate}</div><div class="label">成功/反馈</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

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
        status_filter = st.selectbox("状态筛选", ["全部", "pending", "completed", "cancelled"])
    with col2:
        has_feedback = st.selectbox("反馈情况", ["全部", "已反馈", "未反馈"])
    with col3:
        success_filter = st.selectbox("结果筛选", ["全部", "成功拜访", "未见到", "已搬迁", "地址有误", "其他"])

    filtered = records
    if status_filter != "全部":
        filtered = [r for r in filtered if r.get("status") == status_filter]
    if has_feedback == "已反馈":
        filtered = [r for r in filtered if r.get("feedback_id")]
    elif has_feedback == "未反馈":
        filtered = [r for r in filtered if not r.get("feedback_id")]
    if success_filter != "全部":
        filtered = [r for r in filtered if r.get("feedback_status") == success_filter]

    # 表格展示
    status_map = {"pending": "⏳ 待拜访", "completed": "✅ 已完成", "cancelled": "❌ 已取消"}
    rows = []
    for r in filtered:
        rows.append({
            "机构名称": r.get("org_name", ""),
            "登记编号": r.get("reg_num", ""),
            "计划日期": r.get("planned_date", ""),
            "拜访人": r.get("visitor_name", ""),
            "状态": status_map.get(r.get("status", ""), r.get("status", "")),
            "反馈情况": "✅ 已反馈" if r.get("feedback_id") else "⏳ 待反馈",
            "拜访结果": r.get("feedback_status", "—"),
            "摘要": r.get("feedback_summary", ""),
            "创建人": r.get("creator_name", ""),
        })

    st.dataframe(rows, use_container_width=True, hide_index=True)

    # 导出
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2 = st.columns([1, 5])
    with col1:
        csv_data = "\n".join([
            ",".join(rows[0].keys()),
            *[",".join(f'"{v}"' for v in r.values()) for r in rows],
        ])
        st.download_button(
            "📥 导出 CSV",
            data=csv_data.encode("utf-8-sig"),
            file_name=f"拜访历史_{date.today()}.csv",
            mime="text/csv",
            use_container_width=True,
        )
