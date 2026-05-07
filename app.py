"""私募基金拓客辅助系统 — Streamlit 主入口"""

import streamlit as st
import requests

API_BASE = "http://localhost:8000"

# ── 页面配置 ──
st.set_page_config(
    page_title="私募基金拓客辅助系统",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── 初始化 session 状态 ──
if "token" not in st.session_state:
    st.session_state.token = None
if "user" not in st.session_state:
    st.session_state.user = None
if "page" not in st.session_state:
    st.session_state.page = "query"


# ── 登录/退出函数 ──
def do_login(username, password):
    try:
        resp = requests.post(f"{API_BASE}/api/auth/login", json={
            "username": username, "password": password
        }, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            st.session_state.token = data["token"]
            st.session_state.user = data["user"]
            return True, ""
        else:
            return False, resp.json().get("detail", "登录失败")
    except requests.ConnectionError:
        return False, "无法连接后端服务，请确认 FastAPI 已启动（localhost:8000）"
    except Exception as e:
        return False, str(e)


def do_logout():
    st.session_state.token = None
    st.session_state.user = None
    st.rerun()


# ── 自定义 CSS（复用现有暗色主题） ──
CUSTOM_CSS = """
<style>
.stApp { background: #0a0a0f; }
.main-title {
    font-size: 2rem; font-weight: 700; color: #00d4aa;
    text-align: center; padding: 1.2rem 0 0.3rem 0;
    letter-spacing: 2px; text-shadow: 0 0 20px rgba(0,212,170,0.3);
}
.sub-title {
    text-align: center; color: #6b7280; font-size: 0.9rem; margin-bottom: 1.5rem;
}
.filter-card {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border: 1px solid rgba(0,212,170,0.15); border-radius: 12px;
    padding: 1.2rem 1.5rem; margin-bottom: 1rem;
    box-shadow: 0 4px 20px rgba(0,0,0,0.3);
}
.filter-card:hover { border-color: rgba(0,212,170,0.35); }
.filter-label { color: #00d4aa; font-size: 0.8rem; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 0.4rem; }
.divider { height: 1px; background: linear-gradient(90deg, transparent, rgba(0,212,170,0.3), transparent); margin: 0.8rem 0 1.2rem 0; }
.stats-badge {
    display: inline-block; background: linear-gradient(135deg, #00d4aa22, #0ea5e922);
    border: 1px solid rgba(0,212,170,0.3); border-radius: 20px;
    padding: 0.35rem 1rem; color: #00d4aa; font-size: 0.9rem; font-weight: 600;
}
div.stButton > button {
    background: linear-gradient(135deg, #00d4aa, #0ea5e9) !important;
    color: white !important; font-weight: 600 !important;
    border: none !important; border-radius: 8px !important;
    padding: 0.5rem 2rem !important; letter-spacing: 1px;
    transition: all 0.3s ease; box-shadow: 0 4px 15px rgba(0,212,170,0.3);
}
div.stButton > button:hover {
    transform: translateY(-1px); box-shadow: 0 6px 20px rgba(0,212,170,0.45);
}
.stSelectbox label, .stMultiSelect label, .stTextInput label, .stCheckbox label {
    color: #00d4aa !important; font-size: 0.8rem !important; font-weight: 600 !important;
}
.footer { text-align: center; color: #4b5563; font-size: 0.75rem; padding: 2rem 0 0.5rem 0; }
.user-info {
    position: fixed; top: 12px; right: 20px; z-index: 999;
    background: rgba(26,26,46,0.9); border: 1px solid rgba(0,212,170,0.15);
    border-radius: 8px; padding: 6px 14px; font-size: 13px; color: #e0e0e0;
    display: flex; align-items: center; gap: 12px;
}
.user-info .role-tag {
    font-size: 11px; padding: 1px 8px; border-radius: 10px;
    background: rgba(0,212,170,0.15); color: #00d4aa;
}
.stat-card {
    background: linear-gradient(135deg,#1a1a2e,#16213e);
    border: 1px solid rgba(0,212,170,0.15); border-radius: 10px;
    padding: 0.8rem 1rem; text-align: center;
}
.stat-card .num { font-size: 1.5rem; font-weight: 700; color: #00d4aa; }
.stat-card .label { font-size: 12px; color: #6b7280; margin-top: 2px; }
</style>
"""


# ── 登录页面 ──
def show_login():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    st.markdown('<div class="main-title">私募基金拓客辅助系统</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">请登录后使用</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        with st.container():
            st.markdown(
                '<div style="background:linear-gradient(135deg,#1a1a2e,#16213e);border:1px solid rgba(0,212,170,0.15);'
                'border-radius:12px;padding:2rem;box-shadow:0 4px 20px rgba(0,0,0,0.3);">',
                unsafe_allow_html=True,
            )
            username = st.text_input("用户名", placeholder="输入用户名")
            password = st.text_input("密码", type="password", placeholder="输入密码")

            if st.button("登 录", use_container_width=True):
                if not username or not password:
                    st.error("请输入用户名和密码")
                else:
                    ok, msg = do_login(username, password)
                    if ok:
                        st.success("登录成功！")
                        st.rerun()
                    else:
                        st.error(msg)

            st.markdown(
                '<div style="text-align:center;color:#6b7280;font-size:0.75rem;margin-top:1rem;">'
                '默认管理员: admin / admin123</div>',
                unsafe_allow_html=True,
            )
            st.markdown("</div>", unsafe_allow_html=True)


# ── 主导航栏 ──
def show_navbar():
    user = st.session_state.user
    cols = st.columns([1, 1, 1, 1, 1, 1, 2])
    pages = [
        ("query", "🔍 数据查询"),
        ("map", "🗺️ 地图看板"),
        ("plans", "📋 拜访计划"),
        ("history", "📈 拜访历史"),
        ("batch_import", "📥 补录"),
    ]
    idx = 0
    for name, label in pages:
        with cols[idx]:
            if st.button(label, use_container_width=True,
                          type="primary" if st.session_state.page == name else "secondary"):
                st.session_state.page = name
                st.rerun()
        idx += 1

    # 用户信息
    with cols[-1]:
        st.markdown(
            f'<div style="text-align:right;color:#e0e0e0;font-size:13px;padding:6px 0;">'
            f'{user["display_name"]} '
            f'<span style="font-size:11px;padding:1px 8px;border-radius:10px;background:rgba(0,212,170,0.15);color:#00d4aa;">{user["role"]}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    # 退出按钮单独放在最右边角落
    with cols[5]:
        if st.button("🚪 退出", use_container_width=True):
            do_logout()


# ── 页面路由 ──
def main():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    # 未登录 → 显示登录页
    if not st.session_state.token:
        show_login()
        return

    # 已登录 → 显示导航和对应页面
    st.markdown('<div class="main-title">私募基金拓客辅助系统</div>', unsafe_allow_html=True)
    show_navbar()

    page = st.session_state.page
    if page == "query":
        from pages.query import show_query_page
        show_query_page()
    elif page == "map":
        show_map_page()
    elif page == "plans":
        from pages.plans import show_plans_page
        show_plans_page()
    elif page == "history":
        from pages.history import show_history_page
        show_history_page()
    elif page == "batch_import":
        from pages.batch_import import show_batch_import_page
        show_batch_import_page()

    st.markdown('<div class="footer">数据来源：中国证券投资基金业协会（AMAC）</div>', unsafe_allow_html=True)


# ── 地图看板页面 ──
def show_map_page():
    st.markdown('<div class="filter-card">', unsafe_allow_html=True)
    st.markdown('<div class="filter-label">🗺️ 地图展示</div>', unsafe_allow_html=True)
    st.markdown(
        '<p style="color:#9ca3af;font-size:14px;">点击下方按钮在新标签页打开动态地图看板，查看全部私募分布情况。</p>',
        unsafe_allow_html=True,
    )
    if st.button("🗺️ 打开动态地图", use_container_width=True):
        token = st.session_state.token
        map_url = f"http://localhost:8000/map?token={token}"
        st.markdown(f'<meta http-equiv="refresh" content="0;url={map_url}">', unsafe_allow_html=True)
        st.success(f"地图已打开，如果未自动跳转请点击：[打开地图]({map_url})")

    st.markdown("</div>", unsafe_allow_html=True)

    # 查询后地图入口（显示在结果区域）
    if "last_query_params" in st.session_state and st.session_state.last_query_params:
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        st.markdown('<div class="filter-label">📌 将查询结果显示到地图</div>', unsafe_allow_html=True)
        st.markdown(
            '<p style="color:#9ca3af;font-size:14px;">将当前筛选结果发送到地图上查看分布。</p>',
            unsafe_allow_html=True,
        )
        token = st.session_state.token
        params = st.session_state.last_query_params
        qs = "&".join(f"{k}={v}" for k, v in params.items() if v)
        map_url = f"http://localhost:8000/map?token={token}&{qs}"
        if st.button("📌 在地图上显示当前筛选结果", use_container_width=True):
            st.markdown(f'<meta http-equiv="refresh" content="0;url={map_url}">', unsafe_allow_html=True)
            st.success(f"[打开筛选结果地图]({map_url})")


if __name__ == "__main__":
    main()
