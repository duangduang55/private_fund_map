"""系统设置页 + 修改密码"""

import os
import streamlit as st
import requests

API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8100")

HEADERS = None


def _auth_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"}


# ── 修改密码（全部用户） ──


def show_change_password():
    st.markdown("### 🔑 修改密码")

    with st.container():
        old_pw = st.text_input("当前密码", type="password", key="cp_old")
        new_pw = st.text_input("新密码", type="password", key="cp_new",
                               help="密码至少 6 位")
        confirm_pw = st.text_input("确认新密码", type="password", key="cp_confirm")

        if st.button("修改密码", use_container_width=True):
            if not old_pw or not new_pw or not confirm_pw:
                st.error("请填写完整信息")
                return
            if new_pw != confirm_pw:
                st.error("两次输入的新密码不一致")
                return
            if len(new_pw) < 6:
                st.error("新密码至少 6 位")
                return
            try:
                resp = requests.put(
                    f"{API_BASE}/api/auth/change-password",
                    json={"old_password": old_pw, "new_password": new_pw},
                    headers=_auth_headers(),
                    timeout=10,
                )
                if resp.ok:
                    st.success("密码修改成功！")
                else:
                    st.error(resp.json().get("detail", "修改失败"))
            except requests.ConnectionError:
                st.error("无法连接后端服务")
            except Exception as e:
                st.error(str(e))


# ── 系统设置（super_admin 专用） ──


def show_settings_page():
    st.markdown("### ⚙️ 系统设置")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 系统状态", "🔑 修改密码", "👥 用户管理", "📋 配置管理", "📡 飞书同步"])

    with tab1:
        _show_system_status()

    with tab2:
        _show_change_password_inline()

    with tab3:
        _show_user_management()

    with tab4:
        _show_config_management()

    with tab5:
        _show_feishu_sync()


def _show_system_status():
    """系统状态看板 + 重启服务"""
    st.markdown("#### 系统状态")

    try:
        resp = requests.get(
            f"{API_BASE}/api/admin/system-status",
            headers=_auth_headers(),
            timeout=10,
        )
        if not resp.ok:
            st.error("获取状态失败")
            return
        data = resp.json()
    except requests.ConnectionError:
        st.error("无法连接后端服务")
        return
    except Exception as e:
        st.error(str(e))
        return

    col1, col2, col3 = st.columns(3)

    with col1:
        backend_ok = data.get("backend", {}).get("status") == "running"
        st.metric(
            label="后端服务（FastAPI）",
            value="✅ 运行中" if backend_ok else "❌ 已停止",
            delta=None,
        )

    with col2:
        frontend_ok = data.get("frontend", {}).get("status") == "running"
        st.metric(
            label="前端服务（Streamlit）",
            value="✅ 运行中" if frontend_ok else "❌ 已停止",
            delta=None,
        )

    with col3:
        db_ok = data.get("database", {}).get("status") == "connected"
        st.metric(
            label="数据库（PostgreSQL）",
            value="✅ 已连接" if db_ok else "❌ 未连接",
            delta=None,
        )

    st.divider()

    # 重启服务
    st.markdown("#### 重启服务")
    st.caption("重启后端和前端服务，修改配置后需要重启才能生效。操作后页面会短暂断开，等待约 5 秒后刷新即可。")

    if st.button("🔄 重启服务", type="primary", use_container_width=True):
        try:
            resp = requests.post(
                f"{API_BASE}/api/admin/restart",
                headers=_auth_headers(),
                timeout=5,
            )
            if resp.ok:
                st.success("服务正在重启中，请等待 5 秒后刷新页面...")
                st.markdown(
                    '<meta http-equiv="refresh" content="5">',
                    unsafe_allow_html=True,
                )
            else:
                st.error(resp.json().get("detail", "重启失败"))
        except requests.ConnectionError:
            # 重启后后端断开是正常的，显示成功提示
            st.success("服务正在重启中，请等待 5 秒后刷新页面...")
            st.markdown(
                '<meta http-equiv="refresh" content="5">',
                unsafe_allow_html=True,
            )
        except Exception as e:
            st.error(str(e))
def _show_change_password_inline():
    """修改密码（内嵌到设置页 Tab）"""
    old_pw = st.text_input("当前密码", type="password", key="s_old")
    new_pw = st.text_input("新密码", type="password", key="s_new",
                           help="密码至少 6 位")
    confirm_pw = st.text_input("确认新密码", type="password", key="s_confirm")

    if st.button("修改密码", key="s_btn", use_container_width=True):
        if not old_pw or not new_pw or not confirm_pw:
            st.error("请填写完整信息")
            return
        if new_pw != confirm_pw:
            st.error("两次输入的新密码不一致")
            return
        if len(new_pw) < 6:
            st.error("新密码至少 6 位")
            return
        try:
            resp = requests.put(
                f"{API_BASE}/api/auth/change-password",
                json={"old_password": old_pw, "new_password": new_pw},
                headers=_auth_headers(),
                timeout=10,
            )
            if resp.ok:
                st.success("密码修改成功！")
            else:
                st.error(resp.json().get("detail", "修改失败"))
        except requests.ConnectionError:
            st.error("无法连接后端服务")
        except Exception as e:
            st.error(str(e))


def _show_user_management():
    """用户管理表格 + CRUD"""
    st.markdown("#### 用户列表")

    try:
        resp = requests.get(
            f"{API_BASE}/api/admin/users",
            headers=_auth_headers(),
            timeout=10,
        )
        if not resp.ok:
            st.error("获取用户列表失败")
            return
        users = resp.json().get("data", [])
    except requests.ConnectionError:
        st.error("无法连接后端服务")
        return

    # 用户表格
    df_data = [{
        "ID": u["id"],
        "用户名": u["username"],
        "显示名称": u["display_name"],
        "角色": {"super_admin": "超级管理员", "admin": "管理员", "member": "普通用户"}.get(u["role"], u["role"]),
        "创建时间": u["created_at"][:19] if u.get("created_at") else "",
    } for u in users]
    if df_data:
        st.dataframe(df_data, use_container_width=True, hide_index=True)

    st.divider()

    # ── 创建用户 ──
    st.markdown("#### 创建用户")
    col1, col2 = st.columns(2)
    with col1:
        new_username = st.text_input("用户名", key="nu_name")
        new_display = st.text_input("显示名称", key="nu_display")
    with col2:
        new_password = st.text_input("密码", type="password", key="nu_pwd",
                                     help="密码至少 6 位")
        new_role = st.selectbox(
            "角色",
            options=["member", "admin", "super_admin"],
            format_func=lambda x: {"super_admin": "超级管理员", "admin": "管理员", "member": "普通用户"}.get(x, x),
            key="nu_role",
        )
    if st.button("创建用户", key="nu_btn", use_container_width=True):
        if not new_username or not new_password:
            st.error("用户名和密码不能为空")
        elif len(new_password) < 6:
            st.error("密码至少 6 位")
        else:
            try:
                resp = requests.post(
                    f"{API_BASE}/api/admin/users",
                    json={"username": new_username, "password": new_password,
                          "display_name": new_display or new_username, "role": new_role},
                    headers=_auth_headers(),
                    timeout=10,
                )
                if resp.ok:
                    st.success(f"用户 {new_username} 创建成功")
                    st.rerun()
                else:
                    st.error(resp.json().get("detail", "创建失败"))
            except requests.ConnectionError:
                st.error("无法连接后端服务")

    st.divider()

    # ── 现有用户操作 ──
    st.markdown("#### 用户操作")
    user_options = {f"{u['display_name']}({u['username']})": u for u in users}
    selected_label = st.selectbox("选择用户", options=list(user_options.keys()), key="su_select")
    selected = user_options.get(selected_label)

    if selected:
        op_col1, op_col2, op_col3 = st.columns(3)
        with op_col1:
            # 编辑显示名称
            new_display_name = st.text_input("新显示名称", value=selected["display_name"], key="su_display")
            if st.button("更新名称", key="su_name_btn"):
                try:
                    resp = requests.put(
                        f"{API_BASE}/api/admin/users/{selected['id']}",
                        json={"display_name": new_display_name},
                        headers=_auth_headers(),
                        timeout=10,
                    )
                    if resp.ok:
                        st.success("更新成功")
                        st.rerun()
                    else:
                        st.error(resp.json().get("detail", "更新失败"))
                except requests.ConnectionError:
                    st.error("无法连接后端服务")

        with op_col2:
            # 修改角色
            new_role_val = st.selectbox(
                "新角色",
                options=["member", "admin", "super_admin"],
                index=["member", "admin", "super_admin"].index(selected["role"])
                if selected["role"] in ("member", "admin", "super_admin") else 0,
                format_func=lambda x: {"super_admin": "超级管理员", "admin": "管理员", "member": "普通用户"}.get(x, x),
                key="su_role",
            )
            if st.button("更新角色", key="su_role_btn"):
                try:
                    resp = requests.put(
                        f"{API_BASE}/api/admin/users/{selected['id']}",
                        json={"role": new_role_val},
                        headers=_auth_headers(),
                        timeout=10,
                    )
                    if resp.ok:
                        st.success("角色更新成功")
                        st.rerun()
                    else:
                        st.error(resp.json().get("detail", "更新失败"))
                except requests.ConnectionError:
                    st.error("无法连接后端服务")

        with op_col3:
            # 重置密码
            new_pwd_val = st.text_input("新密码（重置用）", type="password", key="su_pwd",
                                        help="密码至少 6 位")
            if st.button("重置密码", key="su_pwd_btn"):
                if len(new_pwd_val) < 6:
                    st.error("密码至少 6 位")
                else:
                    try:
                        resp = requests.post(
                            f"{API_BASE}/api/admin/users/{selected['id']}/reset-password",
                            json={"new_password": new_pwd_val},
                            headers=_auth_headers(),
                            timeout=10,
                        )
                        if resp.ok:
                            st.success("密码已重置")
                        else:
                            st.error(resp.json().get("detail", "重置失败"))
                    except requests.ConnectionError:
                        st.error("无法连接后端服务")

        # 删除用户
        if st.button("🗑️ 删除此用户", key="su_del_btn", type="primary"):
            if selected["id"] == st.session_state.user["id"]:
                st.error("不能删除自己")
            else:
                try:
                    resp = requests.delete(
                        f"{API_BASE}/api/admin/users/{selected['id']}",
                        headers=_auth_headers(),
                        timeout=10,
                    )
                    if resp.ok:
                        st.success("用户已删除")
                        st.rerun()
                    else:
                        st.error(resp.json().get("detail", "删除失败"))
                except requests.ConnectionError:
                    st.error("无法连接后端服务")


# 配置项中文释义
CONFIG_LABELS = {
    "TS_QUANT_DB_HOST": "量化数据库地址",
    "TS_QUANT_DB_PORT": "量化数据库端口",
    "TS_QUANT_DB_NAME": "量化数据库名",
    "TS_QUANT_DB_USER": "量化数据库用户",
    "TS_QUANT_DB_PASSWORD": "量化数据库密码",
    "FUND_MAP_DB_HOST": "业务数据库地址",
    "FUND_MAP_DB_PORT": "业务数据库端口",
    "FUND_MAP_DB_NAME": "业务数据库名",
    "FUND_MAP_DB_USER": "业务数据库用户",
    "FUND_MAP_DB_PASSWORD": "业务数据库密码",
    "JWT_SECRET": "JWT 签名密钥",
    "JWT_ALGORITHM": "JWT 加密算法",
    "JWT_EXPIRE_MINUTES": "JWT 过期时间（分钟）",
    "API_BASE_URL": "后端 API 地址",
}


def _show_config_management():
    """配置管理：读取/编辑 .env 键值对"""
    st.markdown("#### 系统配置")
    st.caption("⚠️ 修改配置后需重启服务才能生效")

    try:
        resp = requests.get(
            f"{API_BASE}/api/admin/config",
            headers=_auth_headers(),
            timeout=10,
        )
        if not resp.ok:
            st.error("获取配置失败")
            return
        config_data = resp.json().get("data", {})
    except requests.ConnectionError:
        st.error("无法连接后端服务")
        return

    if not config_data:
        st.info("暂无配置数据")
        return

    # 可编辑的键值对
    edited_config = {}
    st.markdown("编辑配置项：")
    for key in sorted(config_data.keys()):
        val = config_data[key]
        label = CONFIG_LABELS.get(key, key)
        new_val = st.text_input(f"{label}（{key}）", value=val, key=f"cfg_{key}")
        edited_config[key] = new_val

    if st.button("保存配置", use_container_width=True):
        try:
            resp = requests.post(
                f"{API_BASE}/api/admin/config",
                json={"config": edited_config},
                headers=_auth_headers(),
                timeout=10,
            )
            if resp.ok:
                st.success("配置已保存，重启服务后生效")
            else:
                st.error(resp.json().get("detail", "保存失败"))
        except requests.ConnectionError:
            st.error("无法连接后端服务")


def _cron_to_chinese(expr: str) -> str:
    """将 cron 5 段表达式解析为中文释义"""
    if not expr or not expr.strip():
        return ""

    parts = expr.strip().split()
    if len(parts) != 5:
        return "格式错误：需要 5 个字段（分 时 日 月 周）"

    minute, hour, day, month, weekday = parts

    W = {"0": "周日", "1": "周一", "2": "周二", "3": "周三",
         "4": "周四", "5": "周五", "6": "周六", "7": "周日"}

    def parse_f(v, unit, names=None):
        if v == '*':
            return None
        if v.startswith('*/'):
            return f"每{v[2:]}{unit}"
        if ',' in v:
            return '、'.join(names.get(x.strip(), x.strip()) for x in v.split(',')) if names else v
        if '-' in v:
            a, b = v.split('-', 1)
            return f"{names.get(a, a) if names else a}到{names.get(b, b) if names else b}"
        return names.get(v, v) if names else v

    md = parse_f(minute, "分钟")   # e.g. "30" | "*/30" | None
    hd = parse_f(hour, "小时")     # e.g. "12" | "*/2" | None
    dd = parse_f(day, "天")
    mo = parse_f(month, "个月")
    wd = parse_f(weekday, "周", W)

    # ── 组合逻辑 ──
    # 1. 纯步长
    if minute.startswith('*/') and hour == '*' and day == '*' and month == '*' and weekday == '*':
        return f"每{minute[2:]}分钟"
    if hour.startswith('*/') and minute == '0' and day == '*' and month == '*' and weekday == '*':
        return f"每{hour[2:]}小时"
    if minute == '*' and hour == '*' and day == '*' and month == '*' and weekday == '*':
        return "每分钟"

    def _time_str(hd, md, minute):
        if minute.isdigit() and hd:
            return f"{hd}:{minute.zfill(2)}"
        if hd and md:
            return f"{hd}{md}"
        return f"{hd}每分钟" if hd else ""

    # 2. 只有分钟指定
    if hour == '*' and day == '*' and month == '*' and weekday == '*':
        if minute.startswith('*/'):
            return f"每{minute[2:]}分钟"
        return f"每分钟第{minute.replace(',', '、')}分"

    # 3. 每天固定时间
    if day == '*' and month == '*' and weekday == '*':
        t = _time_str(hd, md, minute)
        return f"每天{t}"

    # 4. 每周固定时间
    if wd and day == '*' and month == '*':
        t = _time_str(hd, md, minute)
        return f"每{wd} {t}"

    # 5. 每月固定日期
    if dd and month == '*' and weekday == '*':
        t = _time_str(hd, md, minute)
        return f"每月{dd}号 {t}"

    # 6. 每年固定月日
    if mo and dd and weekday == '*':
        t = _time_str(hd, md, minute)
        return f"每年{mo}{dd}号 {t}"

    return "每分钟"



# ── 飞书同步 ──


def _show_feishu_sync():
    """飞书同步配置管理"""
    st.markdown("#### 飞书同步配置")

    # 加载当前配置
    try:
        resp = requests.get(
            f"{API_BASE}/api/admin/feishu/config",
            headers=_auth_headers(),
            timeout=10,
        )
        if not resp.ok:
            st.error("获取飞书配置失败")
            return
        config = resp.json().get("data", {})
    except requests.ConnectionError:
        st.error("无法连接后端服务")
        return

    # ── 区域 1：飞书同步配置 ──
    with st.expander("飞书同步配置", expanded=True):
        feishu_app_id = st.text_input("飞书 App ID", value=config.get("FEISHU_APP_ID", ""),
                                      placeholder="cli_xxxxx", key="fs_app_id")
        feishu_app_secret = st.text_input("飞书 App Secret", type="password",
                                          value=config.get("FEISHU_APP_SECRET", ""),
                                          placeholder="xxxxx", key="fs_app_secret")
        feishu_app_token = st.text_input("飞书 App Token", value=config.get("FEISHU_APP_TOKEN", ""),
                                         placeholder="xxxxx", key="fs_app_token")
        feishu_table_id = st.text_input("拜访记录表 ID", value=config.get("FEISHU_TABLE_ID", ""),
                                        placeholder="tblxxxxx", key="fs_table_id")
        feishu_org_dict_id = st.text_input("机构字典表 ID", value=config.get("FEISHU_ORG_DICT_TABLE_ID", ""),
                                           placeholder="tblxxxxx", key="fs_org_dict_id")

        if st.button("保存配置", key="fs_save", use_container_width=True):
            try:
                resp = requests.post(
                    f"{API_BASE}/api/admin/feishu/config",
                    json={
                        "FEISHU_APP_ID": feishu_app_id,
                        "FEISHU_APP_SECRET": feishu_app_secret,
                        "FEISHU_APP_TOKEN": feishu_app_token,
                        "FEISHU_TABLE_ID": feishu_table_id,
                        "FEISHU_ORG_DICT_TABLE_ID": feishu_org_dict_id,
                    },
                    headers=_auth_headers(),
                    timeout=10,
                )
                if resp.ok:
                    st.success("飞书配置已保存")
                    st.rerun()
                else:
                    st.error(resp.json().get("detail", "保存失败"))
            except requests.ConnectionError:
                st.error("无法连接后端服务")

    # ── 区域 2：飞书同步执行 ──
    with st.expander("飞书同步执行", expanded=True):
        # 手动同步
        st.markdown("##### 手动同步")
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("同步飞书表单", key="fs_sync", use_container_width=True,
                         help="从飞书多维表格拉取表单数据写入本地数据库"):
                try:
                    resp = requests.post(
                        f"{API_BASE}/api/admin/feishu/sync",
                        headers=_auth_headers(),
                        timeout=5,
                    )
                    st.success("同步任务已启动，请稍后查看日志" if resp.ok
                               else resp.json().get("detail", "启动失败"))
                except requests.ConnectionError:
                    st.error("无法连接后端服务")
        with c2:
            if st.button("同步机构字典", key="fs_sync_org_dict", use_container_width=True,
                         help="将本地机构数据同步到飞书机构字典表（跳过已存在）"):
                try:
                    with st.spinner("正在同步机构字典..."):
                        resp = requests.post(
                            f"{API_BASE}/api/admin/feishu/sync-org-dict",
                            json={"force": False},
                            headers=_auth_headers(),
                            timeout=300,
                        )
                    if resp.ok:
                        data = resp.json().get("data", {})
                        st.success(data.get("message", "同步完成"))
                    else:
                        st.error(resp.json().get("detail", "同步失败"))
                except requests.ConnectionError:
                    st.error("无法连接后端服务")
        with c3:
            if st.button("机构字典(强制)", key="fs_sync_org_dict_force", use_container_width=True,
                         help="强制覆盖飞书机构字典表（先删同名再创建）"):
                try:
                    with st.spinner("正在强制同步机构字典..."):
                        resp = requests.post(
                            f"{API_BASE}/api/admin/feishu/sync-org-dict",
                            json={"force": True},
                            headers=_auth_headers(),
                            timeout=600,
                        )
                    if resp.ok:
                        data = resp.json().get("data", {})
                        st.success(data.get("message", "强制同步完成"))
                    else:
                        st.error(resp.json().get("detail", "同步失败"))
                except requests.ConnectionError:
                    st.error("无法连接后端服务")

        # 自动同步
        st.markdown("##### 自动同步")
        try:
            auto_resp = requests.get(
                f"{API_BASE}/api/admin/feishu/auto-sync",
                headers=_auth_headers(),
                timeout=10,
            )
            auto_interval = auto_resp.json().get("data", {}).get("interval_minutes", 0) if auto_resp.ok else 0
        except requests.ConnectionError:
            auto_interval = 0

        auto_enabled = auto_interval > 0
        new_enabled = st.checkbox("启用自动同步", value=auto_enabled, key="fs_auto_enabled")
        new_interval = st.number_input(
            "同步间隔（分钟）",
            min_value=1, max_value=1440, value=max(auto_interval, 30),
            key="fs_auto_interval",
            disabled=not new_enabled,
        )

        if st.button("保存自动同步设置", key="fs_auto_save", use_container_width=True):
            interval_val = new_interval if new_enabled else 0
            try:
                resp = requests.post(
                    f"{API_BASE}/api/admin/feishu/auto-sync",
                    json={"interval_minutes": interval_val},
                    headers=_auth_headers(),
                    timeout=10,
                )
                if resp.ok:
                    st.success(f"自动同步间隔已设置为 {'关闭' if interval_val == 0 else f'{interval_val} 分钟'}")
                    st.rerun()
                else:
                    st.error(resp.json().get("detail", "保存失败"))
            except requests.ConnectionError:
                st.error("无法连接后端服务")

        # 定时同步
        st.markdown("##### 定时同步（Crontab）")
        try:
            cron_resp = requests.get(
                f"{API_BASE}/api/admin/feishu/cron-jobs",
                headers=_auth_headers(),
                timeout=10,
            )
            cron_jobs = cron_resp.json().get("data", []) if cron_resp.ok else []
        except requests.ConnectionError:
            cron_jobs = []

        if cron_jobs:
            cron_table = [{"标签": j.get("label", ""), "表达式": j.get("expression", "")} for j in cron_jobs]
            st.dataframe(cron_table, use_container_width=True, hide_index=True)
        else:
            st.caption("暂无定时同步任务")

        col1, col2 = st.columns([2, 2])
        with col1:
            new_cron_expr = st.text_input("Cron 表达式", value="*/30 * * * *",
                                          key="fs_cron_expr",
                                          help="格式：分 时 日 月 周")
            # 实时显示中文释义
            cron_desc = _cron_to_chinese(st.session_state.fs_cron_expr)
            if cron_desc:
                st.caption(f"📌 {cron_desc}")
        with col2:
            new_cron_label = st.text_input("任务标签", value="",
                                           key="fs_cron_label",
                                           placeholder="例如：每30分钟同步")

        if st.button("添加定时任务", key="fs_cron_add", use_container_width=True):
            if not new_cron_expr:
                st.error("请输入 cron 表达式")
            else:
                label = new_cron_label or new_cron_expr
                try:
                    resp = requests.post(
                        f"{API_BASE}/api/admin/feishu/cron-jobs",
                        json={"expression": new_cron_expr, "label": label},
                        headers=_auth_headers(),
                        timeout=10,
                    )
                    if resp.ok:
                        st.success(f"定时任务已添加：{new_cron_expr}")
                        st.rerun()
                    else:
                        st.error(resp.json().get("detail", "添加失败"))
                except requests.ConnectionError:
                    st.error("无法连接后端服务")

        if cron_jobs:
            del_options = {f"{j.get('label', '')} ({j.get('expression', '')})": j.get("label", "")
                           for j in cron_jobs}
            selected_del = st.selectbox("选择要删除的定时任务", options=list(del_options.keys()),
                                        key="fs_cron_del")
            if st.button("删除选中任务", key="fs_cron_del_btn", use_container_width=True):
                del_label = del_options[selected_del]
                try:
                    resp = requests.delete(
                        f"{API_BASE}/api/admin/feishu/cron-jobs",
                        params={"label": del_label},
                        headers=_auth_headers(),
                        timeout=10,
                    )
                    if resp.ok:
                        st.success(f"定时任务已删除：{del_label}")
                        st.rerun()
                    else:
                        st.error(resp.json().get("detail", "删除失败"))
                except requests.ConnectionError:
                    st.error("无法连接后端服务")

    # ── 区域 3：最近同步日志 ──
    with st.expander("最近同步日志", expanded=False):
        try:
            log_resp = requests.get(
                f"{API_BASE}/api/admin/feishu/logs",
                headers=_auth_headers(),
                timeout=10,
            )
            log_files = log_resp.json().get("data", {}).get("files", []) if log_resp.ok else []
        except requests.ConnectionError:
            log_files = []

        try:
            status_resp = requests.get(
                f"{API_BASE}/api/admin/feishu/status",
                headers=_auth_headers(),
                timeout=10,
            )
            recent_log = status_resp.json().get("data", {}).get("recent_log", "") if status_resp.ok else ""
        except requests.ConnectionError:
            recent_log = ""

        st.caption("最近同步日志（最新 10 行）：")
        st.code(recent_log or "暂无日志", language="text")

        if log_files:
            st.markdown("##### 日志文件列表")
            selected_log = st.selectbox("选择日志文件查看", options=log_files, key="fs_log_file")
            log_lines = st.number_input("显示行数", min_value=5, max_value=200, value=30,
                                        key="fs_log_lines")
            if st.button("查看日志", key="fs_log_view", use_container_width=True):
                try:
                    content_resp = requests.get(
                        f"{API_BASE}/api/admin/feishu/logs",
                        params={"file": selected_log, "lines": log_lines},
                        headers=_auth_headers(),
                        timeout=10,
                    )
                    if content_resp.ok:
                        content = content_resp.json().get("data", {}).get("content", "")
                        st.code(content or "(空)", language="text")
                    else:
                        st.error("获取日志失败")
                except requests.ConnectionError:
                    st.error("无法连接后端服务")
        else:
            st.caption("暂无日志文件")
