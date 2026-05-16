"""系统管理 — 用户管理 + 配置管理"""

import psycopg2
import psycopg2.extras
from src.backend.auth_utils import hash_password, verify_password
from src.backend.config import FUND_MAP_DB, ENV_PATH
from src.backend.db_fundmap import create_user as db_create_user


def get_fm_conn():
    return psycopg2.connect(**FUND_MAP_DB)


# ── 用户管理 ──


def list_users() -> list[dict]:
    """获取所有用户列表（不含 password_hash）"""
    conn = get_fm_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, username, display_name, role, created_at, updated_at "
                "FROM users ORDER BY id"
            )
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def update_user(user_id: int, data: dict) -> bool:
    """更新用户信息（display_name, role）"""
    conn = get_fm_conn()
    try:
        with conn.cursor() as cur:
            fields = []
            values = []
            for key in ("display_name", "role"):
                if key in data and data[key]:
                    fields.append(f"{key} = %s")
                    values.append(data[key])
            if not fields:
                return False
            fields.append("updated_at = now()")
            values.append(user_id)
            cur.execute(
                f"UPDATE users SET {', '.join(fields)} WHERE id = %s",
                values,
            )
            conn.commit()
            return cur.rowcount > 0
    finally:
        conn.close()


def delete_user(user_id: int) -> bool:
    """删除用户（连带购物车、计划、反馈一起删除 — CASCADE）"""
    conn = get_fm_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()
            return cur.rowcount > 0
    finally:
        conn.close()


def reset_user_password(user_id: int, new_password: str) -> bool:
    """管理员重置指定用户的密码"""
    pw_hash = hash_password(new_password)
    conn = get_fm_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash = %s, updated_at = now() WHERE id = %s",
                (pw_hash, user_id),
            )
            conn.commit()
            return cur.rowcount > 0
    finally:
        conn.close()


def change_own_password(user_id: int, old_password: str, new_password: str) -> bool:
    """用户修改自己的密码（需验证旧密码）"""
    conn = get_fm_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT password_hash FROM users WHERE id = %s", (user_id,))
            row = cur.fetchone()
            if not row:
                return False
            if not verify_password(old_password, row["password_hash"]):
                return False
            pw_hash = hash_password(new_password)
            cur.execute(
                "UPDATE users SET password_hash = %s, updated_at = now() WHERE id = %s",
                (pw_hash, user_id),
            )
            conn.commit()
            return True
    finally:
        conn.close()


def create_user(username: str, password: str, display_name: str, role: str = "member") -> dict | None:
    """创建用户（封装 db_fundmap.create_user 自动哈希密码）"""
    pw_hash = hash_password(password)
    return db_create_user(username, pw_hash, display_name, role)


# ── 配置管理 ──


def read_env_config() -> dict:
    """读取 .env 文件的键值对（保留注释和空行仅用于定位，不返回）"""
    if not ENV_PATH.exists():
        return {}
    config = {}
    with open(ENV_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                config[key.strip()] = value.strip()
    return config


def save_env_config(config: dict) -> bool:
    """将键值对写回 .env 文件（保留注释和空行）"""
    if not ENV_PATH.exists():
        return False
    try:
        # 读取原文件，替换已有键值，追加新键
        with open(ENV_PATH, encoding="utf-8") as f:
            lines = f.readlines()

        updated_keys = set()
        new_lines = []
        for line in lines:
            stripped = line.strip()
            if "=" in stripped and not stripped.startswith("#"):
                key = stripped.partition("=")[0].strip()
                if key in config:
                    new_lines.append(f"{key}={config[key]}\n")
                    updated_keys.add(key)
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)

        # 追加新键（原文件中没有的）
        for key, value in config.items():
            if key not in updated_keys:
                new_lines.append(f"{key}={value}\n")

        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        return True
    except Exception:
        return False
