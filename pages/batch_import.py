"""批量补录已拜访（Phase 3 — 搜索+反馈表单）"""

import streamlit as st
import requests

API_BASE = "http://localhost:8000"

# ── Session 初始化 ──
if "batch_import_items" not in st.session_state:
    st.session_state.batch_import_items = []
if "search_results" not in st.session_state:
    st.session_state.search_results = []


def show_batch_import_page():
    headers = {"Authorization": f"Bearer {st.session_state.token}"}

    st.markdown('<div class="filter-card">', unsafe_allow_html=True)
    st.markdown('<div class="filter-label">📥 批量补录已拜访</div>', unsafe_allow_html=True)
    st.markdown(
        '<p style="color:#9ca3af;font-size:14px;">'
        "搜索机构并添加补录记录，提交后自动创建已完成的拜访计划和反馈。</p>",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    # ── 公共信息 ──
    col1, col2 = st.columns(2)
    with col1:
        visitor_name = st.text_input("拜访人", placeholder="填写拜访人姓名", key="bi_visitor")
    with col2:
        visit_date = st.date_input("拜访日期", value=None, key="bi_date")

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # ── 搜索机构 ──
    st.markdown('<div class="filter-label">🔍 搜索机构</div>', unsafe_allow_html=True)
    col1, col2 = st.columns([3, 1])
    with col1:
        search_query = st.text_input(
            "机构名称",
            placeholder="输入机构名称关键字进行模糊搜索",
            label_visibility="collapsed",
        )
    with col2:
        if st.button("🔍 查询", use_container_width=True, type="primary"):
            if search_query.strip():
                try:
                    resp = requests.get(
                        f"{API_BASE}/api/funds",
                        params={"org_name_query": search_query.strip(), "page_size": 50},
                        timeout=15,
                    )
                    data = resp.json()
                    st.session_state.search_results = data.get("data", [])
                except Exception as e:
                    st.error(f"查询失败：{e}")
                    st.session_state.search_results = []
            else:
                st.session_state.search_results = []

    # ── 搜索结果 ──
    if st.session_state.search_results:
        st.markdown(
            f'<p style="color:#6b7280;font-size:12px;">'
            f'找到 {len(st.session_state.search_results)} 条结果（点击 + 添加到补录列表）</p>',
            unsafe_allow_html=True,
        )
        existing_regs = {item["reg_num"] for item in st.session_state.batch_import_items}
        for fund in st.session_state.search_results[:30]:
            cols = st.columns([3, 1.5, 1.5, 0.8])
            with cols[0]:
                st.markdown(
                    f'<div style="padding:2px 0;"><strong style="color:#e0e0e0;">{fund.get("org_name", "")}</strong></div>',
                    unsafe_allow_html=True,
                )
            with cols[1]:
                st.markdown(
                    f'<div style="padding:2px 0;color:#9ca3af;font-size:13px;">{fund.get("reg_num", "")}</div>',
                    unsafe_allow_html=True,
                )
            with cols[2]:
                st.markdown(
                    f'<div style="padding:2px 0;color:#9ca3af;font-size:13px;">{fund.get("org_aum", "-")}</div>',
                    unsafe_allow_html=True,
                )
            with cols[3]:
                reg_num = fund.get("reg_num", "")
                if reg_num in existing_regs:
                    st.markdown(
                        '<div style="padding:2px 0;color:#34d399;font-size:12px;">✓</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    if st.button("＋", key=f"add_{reg_num}", help="添加到补录列表"):
                        st.session_state.batch_import_items.append({
                            "reg_num": reg_num,
                            "org_name": fund.get("org_name", ""),
                            "org_aum": fund.get("org_aum", ""),
                            "fund_count": fund.get("fund_count", 0),
                            "office_address": fund.get("office_address", ""),
                            "office_coordinates": "",
                            "summary": "",
                            "contact_obtained": False,
                            "has_business_card": False,
                            "has_contact_info": False,
                            "communication_detail": "",
                            "follow_up_suggestions": "",
                            "tags": [],
                        })
                        st.rerun()
        st.markdown("<br>", unsafe_allow_html=True)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    # ── 补录列表（含反馈表单） ──
    st.markdown(
        f'<div class="filter-label">📋 待补录列表（{len(st.session_state.batch_import_items)} 条）</div>',
        unsafe_allow_html=True,
    )

    if not st.session_state.batch_import_items:
        st.info("暂无待补录条目，请在上方搜索并添加机构。")
    else:
        items_to_remove = []
        for i, item in enumerate(st.session_state.batch_import_items):
            with st.expander(
                f"{'📥'} {item.get('org_name', item.get('reg_num', ''))} [{item.get('reg_num', '')}]",
                expanded=False,
            ):
                col1, col2 = st.columns([5, 1])
                with col2:
                    if st.button("🗑️ 移除", key=f"remove_{i}"):
                        items_to_remove.append(i)

                item["summary"] = st.text_input(
                    "简要总结",
                    value=item.get("summary", ""),
                    placeholder="拜访总结",
                    key=f"bi_summary_{i}",
                )
                item["contact_obtained"] = st.checkbox(
                    "获取联系方式",
                    value=item.get("contact_obtained", False),
                    key=f"bi_contact_{i}",
                )
                item["has_business_card"] = st.checkbox(
                    "有名片", value=item.get("has_business_card", False),
                    key=f"bi_card_{i}",
                )
                item["has_contact_info"] = st.checkbox(
                    "获取联系信息", value=item.get("has_contact_info", False),
                    key=f"bi_info_{i}",
                )
                item["communication_detail"] = st.text_area(
                    "沟通详情",
                    value=item.get("communication_detail", ""),
                    placeholder="详细描述沟通情况",
                    key=f"bi_detail_{i}",
                )

                # 标签
                tag_options = ["合作意向", "不对外", "不合作", "需求高度匹配"]
                selected_tags = item.get("tags", [])
                tag_cols = st.columns(len(tag_options))
                for ti, tag in enumerate(tag_options):
                    with tag_cols[ti]:
                        if st.checkbox(
                            tag, value=tag in selected_tags,
                            key=f"bi_tag_{i}_{tag}",
                        ):
                            if tag not in selected_tags:
                                selected_tags.append(tag)
                        else:
                            if tag in selected_tags:
                                selected_tags.remove(tag)
                item["tags"] = selected_tags

                item["follow_up_suggestions"] = st.text_area(
                    "后续建议",
                    value=item.get("follow_up_suggestions", ""),
                    placeholder="后续跟进建议",
                    key=f"bi_follow_{i}",
                )

        # 移除标记的条目
        for idx in reversed(items_to_remove):
            st.session_state.batch_import_items.pop(idx)
        if items_to_remove:
            st.rerun()

        # ── 提交 ──
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📥 提交补录", use_container_width=True, type="primary"):
            if not visitor_name.strip():
                st.error("请填写拜访人姓名")
                return

            items = st.session_state.batch_import_items[:]
            for item in items:
                item["visitor_name"] = visitor_name.strip()
                item["planned_date"] = visit_date.strftime("%Y-%m-%d") if visit_date else ""

            try:
                resp = requests.post(
                    f"{API_BASE}/api/plans/batch-import-with-feedback",
                    json=items,
                    headers=headers,
                    timeout=60,
                )
                result = resp.json()
                if result.get("success"):
                    imported = result["imported_count"]
                    st.success(f"✅ 成功补录 {imported}/{len(items)} 条（含反馈）")
                    st.session_state.batch_import_items = []
                    st.rerun()
                else:
                    st.error("补录失败")
            except Exception as e:
                st.error(f"补录失败：{e}")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        '<p style="color:#6b7280;font-size:12px;">'
        "💡 提示：补录后系统会自动创建完成的拜访计划和反馈记录（拜访状态标记为「其他[手动补录]」）。</p>",
        unsafe_allow_html=True,
    )
