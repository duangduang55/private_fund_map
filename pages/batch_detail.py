"""拜访批次详情页面 — 查看某批次下的所有机构"""

import os
import streamlit as st
import requests

st.set_page_config(page_title="批次详情", layout="wide", initial_sidebar_state="collapsed")

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8100")


def init_auth():
    if st.session_state.get("token"):
        return True
    token = st.query_params.get("token")
    if token:
        try:
            resp = requests.get(
                f"{API_BASE}/api/auth/me",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5,
            )
            if resp.ok:
                st.session_state.token = token
                st.session_state.user = resp.json()
                return True
        except Exception:
            pass
    return False


def main():
    if not init_auth():
        batch_id = st.query_params.get("batch_id", "")
        return_url = f"/batch_detail?batch_id={batch_id}" if batch_id else "/batch_detail"
        st.warning("请先登录")
        st.markdown(f"[前往登录](/?login_redirect={return_url})")
        return

    batch_id = st.query_params.get("batch_id")
    if not batch_id:
        st.error("缺少 batch_id 参数")
        return

    token = st.session_state.token
    headers = {"Authorization": f"Bearer {token}"}

    try:
        resp = requests.get(f"{API_BASE}/api/plans/by-batch/{batch_id}", headers=headers, timeout=10)
        plans = resp.json().get("data", [])
    except Exception as e:
        st.error(f"加载失败：{e}")
        return

    if not plans:
        st.info("该批次下暂无拜访计划")
        return

    first = plans[0]
    planned_date = first.get("planned_date", "")
    visitor_name = first.get("visitor_name", "")

    # 批次信息卡片
    st.markdown(
        f"""
    <div style="background:#1e293b;border:1px solid #334155;border-radius:6px;padding:1.2rem 1.5rem;margin-bottom:1rem;">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:0.5rem;">
            <div>
                <span style="color:#94a3b8;font-size:12px;">批次 ID</span>
                <div style="color:#f1f5f9;font-size:18px;font-weight:600;">{batch_id}</div>
            </div>
            <div>
                <span style="color:#94a3b8;font-size:12px;">计划日期</span>
                <div style="color:#f1f5f9;font-size:16px;">{planned_date or '-'}</div>
            </div>
            <div>
                <span style="color:#94a3b8;font-size:12px;">拜访人</span>
                <div style="color:#f1f5f9;font-size:16px;">{visitor_name or '-'}</div>
            </div>
            <div>
                <span style="color:#94a3b8;font-size:12px;">机构数量</span>
                <div style="color:#f1f5f9;font-size:16px;font-weight:600;">{len(plans)} 家</div>
            </div>
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # 操作 / 按钮
    col1, col2, col3, _ = st.columns([1, 1, 1, 4])
    with col1:
        if st.button("← 返回主页", use_container_width=True):
            st.switch_page("app.py")
    with col2:
        print_url = f"{API_BASE}/batch-detail-print?token={token}&batch_id={batch_id}"
        st.markdown(
            f'<a href="{print_url}" target="_blank"><button style="width:100%;padding:0.4rem 1rem;background:#2563eb;color:white;border:none;border-radius:6px;font-size:14px;font-weight:500;cursor:pointer;">📄 导出 PDF</button></a>',
            unsafe_allow_html=True,
        )
    with col3:
        map_url = f"{API_BASE}/batch-map?token={token}&batch_id={batch_id}"
        st.markdown(
            f'<a href="{map_url}" target="_blank"><button style="width:100%;padding:0.4rem 1rem;background:transparent;color:#f87171;border:1px solid rgba(248,113,113,0.4);border-radius:6px;font-size:14px;font-weight:500;cursor:pointer;">🗺️ 在地图上查看</button></a>',
            unsafe_allow_html=True,
        )

    # 机构明细表格
    status_map = {"pending": "⏳ 待拜访", "completed": "✅ 已完成", "cancelled": "❌ 已取消"}
    rows = []
    for p in plans:
        reg_num = p.get("reg_num", "")
        has_feedback = p.get("feedback_id") is not None
        is_starred = p.get("starred", False) in (True, "true", "t")
        org_display = f"⭐ {p.get('org_name', '')}" if is_starred else p.get("org_name", "")
        rows.append({
            "机构名称": org_display,
            "登记编号": reg_num,
            "管理规模": p.get("org_aum", ""),
            "基金数量": p.get("fund_count", 0),
            "办公地址": p.get("office_address", ""),
            "状态": status_map.get(p.get("status", ""), p.get("status", "")),
            "反馈": "✅ 已完成" if has_feedback else "—",
            "操作": f"{API_BASE}/feedback?token={token}&plan_id={p['id']}" if not has_feedback else "",
            "查看": f"{API_BASE}/detail?token={token}&reg_num={reg_num}",
        })

    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
        column_config={
            "机构名称": st.column_config.TextColumn("机构名称", width="medium"),
            "登记编号": st.column_config.TextColumn("登记编号", width="small"),
            "管理规模": st.column_config.TextColumn("管理规模", width="small"),
            "基金数量": st.column_config.NumberColumn("基金数量", width="small"),
            "办公地址": st.column_config.TextColumn("办公地址", width="large"),
            "状态": st.column_config.TextColumn("状态", width="small"),
            "反馈": st.column_config.TextColumn("反馈", width="small"),
            "操作": st.column_config.LinkColumn("操作", display_text="✏️ 填写反馈"),
            "查看": st.column_config.LinkColumn("查看", display_text="查看"),
        },
    )


main()
