"""拜访计划页面（Phase 2 完善）"""

import os
import streamlit as st
import requests
from datetime import date

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8100")
STREAMLIT_BASE = "http://localhost:8501"


def show_plans_page():
    st.markdown('<div class="filter-card">', unsafe_allow_html=True)
    st.markdown('<div class="filter-label">📋 拜访计划</div>', unsafe_allow_html=True)
    st.markdown(
        '<p style="color:#9ca3af;font-size:14px;">查看和管理拜访计划。完整功能将在 Phase 2 实现。</p>',
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    # 加载购物车
    try:
        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        cart_resp = requests.get(f"{API_BASE}/api/cart", headers=headers, timeout=10)
        cart_data = cart_resp.json().get("data", [])
    except Exception as e:
        st.error(f"加载购物车失败：{e}")
        return

    # 显示购物车
    if cart_data:
        st.markdown(f'<span class="stats-badge">🛒 待拜访清单：{len(cart_data)} 条</span>', unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        for item in cart_data:
            cols = st.columns([3, 1.5, 1.5, 1])
            with cols[0]:
                st.markdown(
                    f'<div style="padding:4px 0;"><strong style="color:#e0e0e0;">{item["org_name"]}</strong>'
                    f'<br><span style="color:#9ca3af;font-size:12px;">{item.get("reg_num", "")}</span></div>',
                    unsafe_allow_html=True,
                )
            with cols[1]:
                st.markdown(
                    f'<div style="padding:8px 0;color:#9ca3af;font-size:13px;">{item.get("org_aum", "-")}</div>',
                    unsafe_allow_html=True,
                )
            with cols[2]:
                st.markdown(
                    f'<div style="padding:8px 0;color:#9ca3af;font-size:13px;">基金数: {item.get("fund_count", "-")}</div>',
                    unsafe_allow_html=True,
                )
            with cols[3]:
                if st.button("🗑️", key=f"del_cart_{item['id']}", help="从清单移除"):
                    try:
                        requests.delete(f"{API_BASE}/api/cart/{item['id']}", headers=headers, timeout=5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"删除失败：{e}")

        # 确认计划表单
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="filter-label">✅ 确认拜访计划</div>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)
        with col1:
            planned_date = st.date_input("计划拜访日期", value=date.today())
        with col2:
            visitor_name = st.text_input("拜访人姓名", placeholder="填写拜访人姓名")

        col1, col2, col3 = st.columns([1, 1, 1])
        with col1:
            if st.button("✅ 确认提交计划", use_container_width=True):
                if not visitor_name.strip():
                    st.error("请填写拜访人姓名")
                else:
                    try:
                        resp = requests.post(
                            f"{API_BASE}/api/plans/confirm",
                            json={
                                "planned_date": planned_date.strftime("%Y-%m-%d"),
                                "visitor_name": visitor_name.strip(),
                            },
                            headers=headers,
                            timeout=10,
                        )
                        result = resp.json()
                        if result.get("success"):
                            st.success(f"已生成 {result['count']} 条拜访计划！")
                            st.rerun()
                        else:
                            st.error("提交失败")
                    except Exception as e:
                        st.error(f"提交失败：{e}")

        with col3:
            if st.button("🗑️ 清空待拜访清单", use_container_width=True):
                try:
                    requests.delete(f"{API_BASE}/api/cart", headers=headers, timeout=5)
                    st.rerun()
                except Exception as e:
                    st.error(f"清空失败：{e}")
    else:
        st.info("暂无待拜访清单，请先在数据查询或地图页面中添加。")

    # 显示已有计划
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="filter-label">📋 已有拜访计划</div>', unsafe_allow_html=True)

    try:
        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        plans_resp = requests.get(f"{API_BASE}/api/plans", headers=headers, timeout=10)
        plans = plans_resp.json().get("data", [])
    except Exception:
        plans = []

    if plans:
        token = st.session_state.token
        # 批量查询 detail_url
        reg_nums = [p.get("reg_num", "") for p in plans if p.get("reg_num", "")]
        detail_urls = {}
        if reg_nums:
            try:
                resp = requests.post(f"{API_BASE}/api/fund-links", json={"reg_nums": reg_nums}, timeout=10)
                detail_urls = resp.json().get("data", {})
            except Exception:
                pass

        plans_df = []
        for p in plans:
            reg_num = p.get("reg_num", "")
            bid = p.get("batch_id", "") or ""
            pd_date = p.get("planned_date", "") or ""
            batch_link = f"/batch_detail?batch_id={bid}&token={token}&d={pd_date}#{bid}" if bid else ""
            is_starred = p.get("starred", False) in (True, "true", "t")
            org_display = f"⭐ {p['org_name']}" if is_starred else p["org_name"]
            plans_df.append({
                "拜访计划": batch_link,
                "计划ID": p["id"],
                "机构名称": org_display,
                "登记编号": reg_num,
                "管理规模": p.get("org_aum", ""),
                "计划日期": pd_date,
                "拜访人": p.get("visitor_name", ""),
                "状态": {"pending": "⏳ 待拜访", "completed": "✅ 已完成", "cancelled": "❌ 已取消"}.get(p.get("status", ""), p.get("status", "")),
                "操作": f"{API_BASE}/detail?token={token}&reg_num={reg_num}",
                "AMAC详情": detail_urls.get(reg_num, ""),
            })
        st.dataframe(
            plans_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "拜访计划": st.column_config.LinkColumn("拜访计划", display_text=r"&d=([^&]+)", width="medium"),
                "计划ID": st.column_config.NumberColumn(width="small"),
                "机构名称": st.column_config.TextColumn(width="medium"),
                "登记编号": st.column_config.TextColumn(width="small"),
                "管理规模": st.column_config.TextColumn(width="small"),
                "计划日期": st.column_config.DateColumn(width="small"),
                "拜访人": st.column_config.TextColumn(width="small"),
                "状态": st.column_config.TextColumn(width="small"),
                "操作": st.column_config.LinkColumn("操作", display_text="查看"),
                "AMAC详情": st.column_config.LinkColumn("AMAC详情", display_text="🔗 AMAC"),
            },
        )
        # 使 AMAC 链接在新窗口打开
        st.markdown(
            "<script>document.querySelectorAll('[data-testid^=\"stDataFrame\"] a[href*=\"gs.amac.org.cn\"]').forEach(function(a){a.target=\"_blank\";a.rel=\"noopener\"})</script>",
            unsafe_allow_html=True,
        )
    else:
        st.info("暂无拜访计划记录。")
