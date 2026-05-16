"""FastAPI 主应用 — 私募基金拓客辅助系统后端"""

from fastapi import FastAPI, HTTPException, Depends, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
import secrets
import string
import sys
import threading
from pathlib import Path

from src.backend.auth_utils import hash_password, verify_password, create_token, decode_token
from src.backend.db_admin import (
    list_users,
    create_user as admin_create_user,
    update_user,
    delete_user,
    reset_user_password,
    change_own_password,
    read_env_config,
    save_env_config,
)
from src.backend.db_tsquant import (
    query_funds,
    query_funds_for_map,
    query_funds_by_reg_nums,
    check_match_reasons,
    load_distinct_values,
    parse_keywords,
    parse_product_range,
)
from src.backend.db_fundmap import (
    get_user_by_username,
    get_user_by_id,
    create_user,
    get_visit_status_reg_nums,
    get_latest_visit_info,
    get_visit_history,
    get_cart_items,
    add_to_cart,
    remove_from_cart,
    clear_cart,
    toggle_cart_star,
    set_plan_star,
    get_plan_owner_id,
    create_plans_from_cart,
    get_user_plans,
    get_plans_by_batch,
    get_feedback_by_plan_id,
    upsert_feedback,
    update_plan_status,
    get_plans_with_feedback,
    get_visit_stats,
    auto_expire_plans,
    batch_import_visited,
    batch_import_with_feedback,
    delete_plan,
    delete_plans_by_batch,
    get_user_tags,
    get_all_visit_records,
    get_fund_tags,
)

# ── FastAPI 应用 ────────────────────────────────────────────────
app = FastAPI(title="私募基金拓客辅助系统 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件（共享 CSS、图标等）
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

MAP_HTML_PATH = os.path.join(os.path.dirname(__file__), "templates", "map.html")
BATCH_MAP_HTML_PATH = os.path.join(os.path.dirname(__file__), "templates", "batch_map.html")
BATCH_DETAIL_PRINT_HTML_PATH = os.path.join(os.path.dirname(__file__), "templates", "batch_detail_print.html")


# ── 依赖：获取当前用户 ──────────────────────────────────────────
async def get_current_user(authorization: str = Header(None, alias="Authorization", include_in_schema=False)):
    """从 Authorization header 解析 token 并返回用户"""
    if not authorization:
        raise HTTPException(status_code=401, detail="未提供认证信息")
    token = authorization.replace("Bearer ", "")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")
    user = get_user_by_id(int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


async def require_super_admin(user: dict = Depends(get_current_user)):
    """仅 super_admin 可访问"""
    if user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="仅超级管理员可执行此操作")
    return user


# ── 请求模型 ────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    display_name: str
    role: str = "member"

class CartAddRequest(BaseModel):
    reg_num: str
    org_name: str
    org_aum: str = ""
    fund_count: int = 0
    office_address: str = ""
    lat: float = 0
    lng: float = 0

class ConfirmPlanRequest(BaseModel):
    planned_date: str  # YYYY-MM-DD
    visitor_name: str

class FeedbackRequest(BaseModel):
    visit_plan_id: int
    visit_date: str = ""
    visitor_name: str = ""
    visit_status: str = "其他"
    has_business_card: bool = False
    has_contact_info: bool = False
    summary: str = ""
    communication_detail: str = ""
    follow_up_suggestions: str = ""
    tags: list[str] = []
    plan_status: str = ""  # 同步更新计划状态：completed / cancelled

class BatchImportItem(BaseModel):
    reg_num: str
    org_name: str = ""
    org_aum: str = ""
    fund_count: int = 0
    office_address: str = ""
    office_coordinates: str = ""
    planned_date: str = ""
    visitor_name: str = ""

class MatchReasonsRequest(BaseModel):
    reg_nums: list[str]
    product_keywords: list[str] = []
    executive_keywords: list[str] = []

class BatchImportSimpleRequest(BaseModel):
    reg_nums: list[str]
    visitor_name: str = ""
    planned_date: str = ""


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    display_name: str
    role: str = "member"


class UpdateUserRequest(BaseModel):
    display_name: str | None = None
    role: str | None = None


class ResetPasswordRequest(BaseModel):
    new_password: str


class SaveConfigRequest(BaseModel):
    config: dict[str, str]

class FeishuConfigRequest(BaseModel):
    FEISHU_APP_ID: str = ""
    FEISHU_APP_SECRET: str = ""
    FEISHU_APP_TOKEN: str = ""
    FEISHU_TABLE_ID: str = ""
    FEISHU_ORG_DICT_TABLE_ID: str = ""

class FeishuSyncResponse(BaseModel):
    success: bool
    data: dict | None = None
    message: str = ""

class FeishuAutoSyncRequest(BaseModel):
    interval_minutes: int = 0

class FeishuCronJobRequest(BaseModel):
    expression: str
    label: str = ""
    old_label: str = ""  # 更新时使用

class FeishuLogQuery(BaseModel):
    file: str = ""
    lines: int = 10


# ── 认证 API ────────────────────────────────────────────────────

@app.post("/api/auth/login")
def login(req: LoginRequest):
    user = get_user_by_username(req.username)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_token(user["id"], user["username"], user["role"])
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "display_name": user["display_name"],
            "role": user["role"],
        },
    }


@app.post("/api/auth/register")
def register(req: RegisterRequest):
    if get_user_by_username(req.username):
        raise HTTPException(status_code=400, detail="用户名已存在")
    pw_hash = hash_password(req.password)
    user = create_user(req.username, pw_hash, req.display_name, req.role)
    if not user:
        raise HTTPException(status_code=400, detail="创建用户失败")
    return {"message": "用户创建成功", "user": user}


@app.get("/api/auth/me")
def me(user: dict = Depends(get_current_user)):
    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user["display_name"],
        "role": user["role"],
    }


# ── 修改密码 API ──────────────────────────────────────────────

@app.put("/api/auth/change-password")
def api_change_password(req: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    ok = change_own_password(user["id"], req.old_password, req.new_password)
    if not ok:
        raise HTTPException(status_code=400, detail="旧密码错误或用户不存在")
    return {"success": True}


# ── 管理 API（仅 super_admin） ──────────────────────────────────

@app.get("/api/admin/users")
def api_admin_list_users(_: dict = Depends(require_super_admin)):
    return {"data": list_users()}


@app.post("/api/admin/users")
def api_admin_create_user(req: CreateUserRequest, _: dict = Depends(require_super_admin)):
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位")
    if req.role not in ("super_admin", "admin", "member"):
        raise HTTPException(status_code=400, detail="无效的角色类型")
    from src.backend.db_fundmap import get_user_by_username
    if get_user_by_username(req.username):
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = admin_create_user(req.username, req.password, req.display_name, req.role)
    if not user:
        raise HTTPException(status_code=400, detail="创建用户失败")
    return {"success": True, "user": user}


@app.put("/api/admin/users/{user_id}")
def api_admin_update_user(user_id: int, req: UpdateUserRequest, _: dict = Depends(require_super_admin)):
    if req.role is not None and req.role not in ("super_admin", "admin", "member"):
        raise HTTPException(status_code=400, detail="无效的角色类型")
    data = {}
    if req.display_name is not None:
        data["display_name"] = req.display_name
    if req.role is not None:
        data["role"] = req.role
    if not data:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")
    ok = update_user(user_id, data)
    if not ok:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"success": True}


@app.delete("/api/admin/users/{user_id}")
def api_admin_delete_user(user_id: int, _: dict = Depends(require_super_admin)):
    ok = delete_user(user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"success": True}


@app.post("/api/admin/users/{user_id}/reset-password")
def api_admin_reset_password(user_id: int, req: ResetPasswordRequest, _: dict = Depends(require_super_admin)):
    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位")
    ok = reset_user_password(user_id, req.new_password)
    if not ok:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"success": True}


@app.get("/api/admin/config")
def api_admin_get_config(_: dict = Depends(require_super_admin)):
    return {"data": read_env_config()}


@app.post("/api/admin/config")
def api_admin_save_config(req: SaveConfigRequest, _: dict = Depends(require_super_admin)):
    ok = save_env_config(req.config)
    if not ok:
        raise HTTPException(status_code=500, detail="保存配置失败")
    return {"success": True, "message": "配置已保存，重启服务后生效"}


@app.get("/api/admin/system-status")
def api_system_status(_: dict = Depends(require_super_admin)):
    """检查系统各组件运行状态"""
    status = {
        "backend": {"status": "running", "port": 8100},
        "frontend": {"status": "stopped", "port": 8501},
        "database": {"status": "disconnected"},
    }
    # 检查前端（Streamlit）
    try:
        import urllib.request
        req = urllib.request.Request("http://localhost:8501", method="HEAD")
        urllib.request.urlopen(req, timeout=3)
        status["frontend"]["status"] = "running"
    except Exception:
        pass
    # 检查数据库
    try:
        from src.backend.config import FUND_MAP_DB
        import psycopg2
        conn = psycopg2.connect(**FUND_MAP_DB, connect_timeout=3)
        conn.close()
        status["database"]["status"] = "connected"
    except Exception:
        pass
    return status


@app.post("/api/admin/restart")
def api_restart(_: dict = Depends(require_super_admin)):
    """重启后端和前端服务"""
    import subprocess
    restart_script = os.path.join(os.path.dirname(__file__), "..", "..", "restart.sh")
    subprocess.Popen(
        ["nohup", "bash", restart_script],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return {"success": True, "message": "服务正在重启，请稍候..."}


# ── 筛选选项 API ───────────────────────────────────────────────

@app.get("/api/filters")
def get_filters():
    return load_distinct_values()


# ── 基金查询 API ───────────────────────────────────────────────

@app.get("/api/funds")
def api_query_funds(
    authorization: str = None,
    office_provinces: str = Query(None),
    org_aums: str = Query(None),
    member_types: str = Query(None),
    ins_types: str = Query(None),
    ent_natures: str = Query(None),
    product_range: str = Query(None),
    product_name_query: str = Query(None),
    exclude_liquidated: bool = Query(True),
    executive_query: str = Query(None),
    org_name_query: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20000, ge=1, le=50000),
):
    """基金查询 API（为 Streamlit 提供 JSON 数据）"""
    params = {
        "office_provinces": office_provinces.split(",") if office_provinces else None,
        "org_aums": org_aums.split(",") if org_aums else None,
        "member_types": member_types.split(",") if member_types else None,
        "ins_types": ins_types.split(",") if ins_types else None,
        "ent_natures": ent_natures.split(",") if ent_natures else None,
        "product_range": parse_product_range(product_range or ""),
        "product_keywords": parse_keywords(product_name_query or ""),
        "exclude_liquidated": exclude_liquidated,
        "executive_keywords": parse_keywords(executive_query or ""),
        "org_name_keywords": parse_keywords(org_name_query or ""),
    }
    funds = query_funds(params)
    total = len(funds)
    start = (page - 1) * page_size
    end = start + page_size
    return {"total": total, "page": page, "page_size": page_size, "data": funds[start:end]}


# ── 地图数据 API ───────────────────────────────────────────────

@app.get("/api/map-data")
def map_data(
    authorization: str = None,
    office_provinces: str = Query(None),
    org_aums: str = Query(None),
    member_types: str = Query(None),
    ins_types: str = Query(None),
    ent_natures: str = Query(None),
    product_range: str = Query(None),
    product_name_query: str = Query(None),
    exclude_liquidated: bool = Query(True),
    executive_query: str = Query(None),
    org_name_query: str = Query(None),
):
    """返回地图展示格式的基金数据 + 已拜访信息"""
    params = {
        "office_provinces": office_provinces.split(",") if office_provinces else None,
        "org_aums": org_aums.split(",") if org_aums else None,
        "member_types": member_types.split(",") if member_types else None,
        "ins_types": ins_types.split(",") if ins_types else None,
        "ent_natures": ent_natures.split(",") if ent_natures else None,
        "product_range": parse_product_range(product_range or ""),
        "product_keywords": parse_keywords(product_name_query or ""),
        "exclude_liquidated": exclude_liquidated,
        "executive_keywords": parse_keywords(executive_query or ""),
        "org_name_keywords": parse_keywords(org_name_query or ""),
    }
    funds = query_funds_for_map(params)
    completed_set, pending_set = get_visit_status_reg_nums()
    return {"total": len(funds), "data": funds, "visited_reg_nums": list(completed_set), "pending_reg_nums": list(pending_set)}


# ── 地图页面 ────────────────────────────────────────────────────

@app.get("/map", response_class=HTMLResponse)
def map_page(token: str = Query(None)):
    """动态地图页面"""
    with open(MAP_HTML_PATH, encoding="utf-8") as f:
        html = f.read()
    token_str = (token or "")
    html = html.replace("'{{ token }}'", repr(token_str))
    html = html.replace("{{ token }}", token_str)
    return HTMLResponse(html)


@app.get("/batch-map", response_class=HTMLResponse)
def batch_map_page(token: str = Query(None), batch_id: str = Query("")):
    """批次机构地图页面"""
    with open(BATCH_MAP_HTML_PATH, encoding="utf-8") as f:
        html = f.read()
    token_str = (token or "")
    html = html.replace("'{{ token }}'", repr(token_str))
    html = html.replace("{{ token }}", token_str)
    html = html.replace("'{{ batch_id }}'", repr(batch_id))
    html = html.replace("{{ batch_id }}", batch_id)
    return HTMLResponse(html)


@app.get("/batch-detail-print", response_class=HTMLResponse)
def batch_detail_print_page(token: str = Query(None), batch_id: str = Query("")):
    """批次详情打印页面（PDF导出）"""
    with open(BATCH_DETAIL_PRINT_HTML_PATH, encoding="utf-8") as f:
        html = f.read()
    token_str = (token or "")
    html = html.replace("'{{ token }}'", repr(token_str))
    html = html.replace("{{ token }}", token_str)
    html = html.replace("'{{ batch_id }}'", repr(batch_id))
    html = html.replace("{{ batch_id }}", batch_id)
    return HTMLResponse(html)


CONFIRM_DEL_PLAN_HTML_PATH = os.path.join(os.path.dirname(__file__), "templates", "confirm_del_plan.html")

@app.get("/confirm-del-plan", response_class=HTMLResponse)
def confirm_del_plan_page(token: str = Query(None), plan_id: str = Query(""), batch_id: str = Query(""), redirect: str = Query("")):
    """删除确认页面"""
    with open(CONFIRM_DEL_PLAN_HTML_PATH, encoding="utf-8") as f:
        html = f.read()
    return HTMLResponse(html)


@app.get("/confirm", response_class=HTMLResponse)
def confirm_page(token: str = Query(None)):
    """确认拜访计划页面"""
    with open(os.path.join(os.path.dirname(__file__), "templates", "confirm.html"), encoding="utf-8") as f:
        html = f.read()
    token_str = (token or "")
    html = html.replace("'{{ token }}'", repr(token_str))
    return HTMLResponse(html)


PLANS_HTML_PATH = os.path.join(os.path.dirname(__file__), "templates", "plans.html")

@app.get("/plans", response_class=HTMLResponse)
def plans_page(token: str = Query(None)):
    """拜访计划列表页面"""
    with open(PLANS_HTML_PATH, encoding="utf-8") as f:
        html = f.read()
    token_str = (token or "")
    # 解析用户信息用于前端权限控制
    payload = decode_token(token_str)
    user_id = int(payload["sub"]) if payload else 0
    role = payload.get("role", "member") if payload else "member"
    html = html.replace("{{ token }}", token_str)
    html = html.replace("{{ user_id }}", str(user_id))
    html = html.replace("{{ role }}", role)
    return HTMLResponse(html)


# ── 购物车 API ──────────────────────────────────────────────────

@app.get("/api/cart")
def api_get_cart(user: dict = Depends(get_current_user)):
    return {"data": get_cart_items(user["id"])}


@app.post("/api/cart/add")
def api_add_cart(req: CartAddRequest, user: dict = Depends(get_current_user)):
    ok = add_to_cart(user["id"], req.model_dump())
    return {"success": ok}


@app.delete("/api/cart/{cart_id}")
def api_remove_cart(cart_id: int, user: dict = Depends(get_current_user)):
    ok = remove_from_cart(cart_id, user["id"])
    return {"success": ok}


@app.delete("/api/cart")
def api_clear_cart(user: dict = Depends(get_current_user)):
    clear_cart(user["id"])
    return {"success": True}


@app.post("/api/cart/toggle-star/{cart_id}")
def api_toggle_cart_star(cart_id: int, user: dict = Depends(get_current_user)):
    ok = toggle_cart_star(cart_id, user["id"])
    return {"success": ok}


@app.post("/api/plans/toggle-star/{plan_id}")
def api_toggle_plan_star(plan_id: int, user: dict = Depends(get_current_user)):
    ok = set_plan_star(plan_id, user["id"], True)
    return {"success": ok}


@app.post("/api/plans/unstar/{plan_id}")
def api_unstar_plan(plan_id: int, user: dict = Depends(get_current_user)):
    ok = set_plan_star(plan_id, user["id"], False)
    return {"success": ok}


# ── 删除拜访计划 ──

@app.delete("/api/plans/{plan_id}")
def api_delete_plan(plan_id: int, user: dict = Depends(get_current_user)):
    ok = delete_plan(plan_id, user["id"], user["role"])
    if not ok:
        raise HTTPException(status_code=404, detail="未找到该记录或无权限删除")
    return {"success": True}


@app.delete("/api/plans/batch/{batch_id}")
def api_delete_batch(batch_id: str, user: dict = Depends(get_current_user)):
    count = delete_plans_by_batch(batch_id, user["id"], user["role"])
    return {"success": True, "deleted_count": count}


# ── 命中原因 API ──────────────────────────────────────────────

@app.post("/api/match-reasons")
def api_match_reasons(req: MatchReasonsRequest):
    matches = check_match_reasons(req.reg_nums, req.product_keywords, req.executive_keywords)
    return {"data": matches}


# ── 拜访计划 API ───────────────────────────────────────────────

def _generate_batch_id() -> str:
    """生成6位短随机ID"""
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(6))


@app.post("/api/plans/confirm")
def api_confirm_plans(req: ConfirmPlanRequest, user: dict = Depends(get_current_user)):
    batch_id = _generate_batch_id()
    plans = create_plans_from_cart(user["id"], req.planned_date, req.visitor_name, batch_id)
    return {"success": True, "count": len(plans), "data": plans, "batch_id": batch_id}


@app.get("/api/plans")
def api_get_plans(user: dict = Depends(get_current_user)):
    auto_expire_plans()  # 每次查看计划时自动过期
    return {"data": get_user_plans(user["id"], user["role"])}


@app.get("/api/plans/by-batch/{batch_id}")
def api_get_plans_by_batch(batch_id: str, user: dict = Depends(get_current_user)):
    """查询某批次下的所有拜访计划"""
    return {"data": get_plans_by_batch(batch_id)}


# ── 拜访反馈 API ──────────────────────────────────────────────

@app.get("/api/feedback/{plan_id}")
def api_get_feedback(plan_id: int, user: dict = Depends(get_current_user)):
    fb = get_feedback_by_plan_id(plan_id)
    return fb or {}


@app.post("/api/feedback")
def api_save_feedback(req: FeedbackRequest, user: dict = Depends(get_current_user)):
    # 权限检查：仅 super_admin 可编辑他人记录
    plan_owner = get_plan_owner_id(req.visit_plan_id)
    if plan_owner is None:
        raise HTTPException(status_code=404, detail="拜访计划不存在")
    if user["role"] != "super_admin" and plan_owner != user["id"]:
        raise HTTPException(status_code=403, detail="无权操作非本人创建的记录")
    fb = upsert_feedback(req.visit_plan_id, req.model_dump())
    if req.plan_status:
        # 取消时把原因同步写入 visit_plans.remark
        remark = req.summary if req.plan_status == "cancelled" else ""
        update_plan_status(req.visit_plan_id, req.plan_status, remark)
    return {"success": fb is not None, "data": fb}


# ── 用户标签 API ───────────────────────────────────────────────

@app.get("/api/user-tags")
def api_get_user_tags(user: dict = Depends(get_current_user)):
    return get_user_tags(user["id"])


# ── 拜访历史 API（含反馈信息） ───────────────────────────────

@app.get("/api/history")
def api_get_history(user: dict = Depends(get_current_user)):
    auto_expire_plans()
    return {"data": get_plans_with_feedback(user["id"], user["role"])}


# ── 统计 API ─────────────────────────────────────────────────

@app.get("/api/stats")
def api_get_stats(user: dict = Depends(get_current_user)):
    return get_visit_stats(user["id"], user["role"])


# ── 自动过期 API ────────────────────────────────────────────

@app.post("/api/plans/auto-expire")
def api_auto_expire(user: dict = Depends(get_current_user)):
    count = auto_expire_plans()
    return {"success": True, "expired_count": count}


# ── 批量补录 API ────────────────────────────────────────────

@app.post("/api/plans/batch-import")
def api_batch_import(items: list[BatchImportItem], user: dict = Depends(get_current_user)):
    records = [item.model_dump() for item in items]
    count = batch_import_visited(user["id"], records)
    return {"success": True, "imported_count": count}


class BatchImportWithFeedbackItem(BaseModel):
    reg_num: str
    org_name: str = ""
    org_aum: str = ""
    fund_count: int = 0
    office_address: str = ""
    office_coordinates: str = ""
    planned_date: str = ""
    visitor_name: str = ""
    summary: str = ""
    has_business_card: bool = False
    has_contact_info: bool = False
    communication_detail: str = ""
    follow_up_suggestions: str = ""
    tags: list[str] = []


@app.post("/api/plans/batch-import-with-feedback")
def api_batch_import_with_feedback(items: list[BatchImportWithFeedbackItem], user: dict = Depends(get_current_user)):
    records = [item.model_dump() for item in items]
    count = batch_import_with_feedback(user["id"], records)
    return {"success": True, "imported_count": count}


@app.post("/api/plans/batch-import-simple")
def api_batch_import_simple(req: BatchImportSimpleRequest, user: dict = Depends(get_current_user)):
    """便捷补录：传入 reg_num 列表，自动从数据库查询机构信息"""
    reg_nums = [r.strip() for r in req.reg_nums if r.strip()]
    if not reg_nums:
        return {"success": False, "imported_count": 0}
    funds = query_funds_by_reg_nums(reg_nums)
    records = []
    for f in funds:
        records.append({
            "reg_num": f["reg_num"],
            "org_name": f.get("org_name", ""),
            "org_aum": f.get("org_aum", ""),
            "fund_count": f.get("fund_count", 0),
            "office_address": f.get("office_address", ""),
            "office_coordinates": f.get("office_coordinates", ""),
            "planned_date": req.planned_date,
            "visitor_name": req.visitor_name,
        })
    found_regs = {f["reg_num"] for f in funds}
    for rn in reg_nums:
        if rn not in found_regs:
            records.append({
                "reg_num": rn,
                "org_name": rn,
                "org_aum": "",
                "fund_count": 0,
                "office_address": "",
                "office_coordinates": "",
                "planned_date": req.planned_date,
                "visitor_name": req.visitor_name,
            })
    count = batch_import_visited(user["id"], records)
    return {"success": True, "imported_count": count, "total_input": len(reg_nums), "found": len(funds)}


# ── 反馈页面 ─────────────────────────────────────────────────

FEEDBACK_HTML_PATH = os.path.join(os.path.dirname(__file__), "templates", "feedback.html")

@app.get("/feedback", response_class=HTMLResponse)
def feedback_page(token: str = Query(""), plan_id: int = Query(0)):
    with open(FEEDBACK_HTML_PATH, encoding="utf-8") as f:
        html = f.read()
    html = html.replace("'{{ token }}'", repr(token))
    html = html.replace("{{ token }}", token)
    html = html.replace("'{{ plan_id }}'", repr(plan_id))
    html = html.replace("{{ plan_id }}", str(plan_id))
    return HTMLResponse(html)


# ── 已拜访信息 API（供地图使用） ──────────────────────────────

@app.get("/api/visited-info")
def api_visited_info(reg_num: str = Query("")):
    if not reg_num:
        return {}
    info = get_latest_visit_info(reg_num)
    return info or {}


@app.get("/api/visited-history")
def api_visited_history(reg_num: str = Query("")):
    if not reg_num:
        return {"data": []}
    return {"data": get_visit_history(reg_num)}


# ── 机构链接查询 API ───────────────────────────────────────

class FundLinksRequest(BaseModel):
    reg_nums: list[str]

@app.post("/api/fund-links")
def api_fund_links(req: FundLinksRequest):
    """根据 reg_num 列表批量查询 detail_url"""
    funds = query_funds_by_reg_nums(req.reg_nums)
    return {"data": {f["reg_num"]: f.get("detail_url", "") for f in funds}}


# ── 私募拜访记录详情 API ─────────────────────────────────

@app.get("/api/fund-profile/{reg_num}")
def api_fund_profile(reg_num: str, user: dict = Depends(get_current_user)):
    """获取私募的详细信息 + 标签 + 拜访记录"""
    # 从 ts_quant_db 获取机构基本信息
    funds = query_funds_by_reg_nums([reg_num])
    fund_info = funds[0] if funds else {"reg_num": reg_num}
    # 从 fund_map_db 获取标签和拜访记录
    tags = get_fund_tags(reg_num)
    visits = get_all_visit_records(reg_num)
    return {"fund": fund_info, "tags": tags, "visits": visits}


# ── 飞书同步 API ─────────────────────────────────────────

_FEISHU_ROOT = Path(__file__).resolve().parent.parent.parent

# ── 自动同步后台线程 ──

_auto_sync_thread: threading.Thread | None = None
_auto_sync_stop = threading.Event()


def _auto_sync_worker():
    """后台线程：按 config.json 间隔自动执行飞书同步"""
    while not _auto_sync_stop.is_set():
        try:
            from feishu_sync.config import get_sync_interval
            from feishu_sync.log_manager import get_sync_logger
            log = get_sync_logger()

            interval = get_sync_interval()
            if interval <= 0:
                _auto_sync_stop.wait(60)
                continue

            log.info(f"[自动同步] 按间隔 {interval} 分钟执行")
            from feishu_sync.sync import sync_once
            result = sync_once()
            log.info(f"[自动同步] {result['message']}")

            _auto_sync_stop.wait(interval * 60)
        except Exception as e:
            try:
                from feishu_sync.log_manager import get_sync_logger
                get_sync_logger().error(f"[自动同步] 异常: {e}")
            except Exception:
                pass
            _auto_sync_stop.wait(30)


def _start_auto_sync():
    """启动自动同步后台线程"""
    global _auto_sync_thread
    if _auto_sync_thread and _auto_sync_thread.is_alive():
        return
    _auto_sync_stop.clear()
    _auto_sync_thread = threading.Thread(target=_auto_sync_worker, daemon=True)
    _auto_sync_thread.start()


def _stop_auto_sync():
    """停止自动同步后台线程"""
    _auto_sync_stop.set()
    global _auto_sync_thread
    if _auto_sync_thread:
        _auto_sync_thread.join(timeout=5)
        _auto_sync_thread = None


@app.on_event("startup")
def startup_auto_sync():
    _start_auto_sync()


@app.on_event("shutdown")
def shutdown_auto_sync():
    _stop_auto_sync()


@app.get("/api/admin/feishu/config")
def api_feishu_get_config(_: dict = Depends(require_super_admin)):
    from feishu_sync.config import load_config, get_all_config_json
    load_config()
    return {"data": get_all_config_json()}


@app.post("/api/admin/feishu/config")
def api_feishu_save_config(req: FeishuConfigRequest, _: dict = Depends(require_super_admin)):
    from feishu_sync.config import save_to_json
    config = req.model_dump()
    config = {k: v for k, v in config.items() if v}
    ok = save_to_json(config)
    if not ok:
        raise HTTPException(status_code=500, detail="保存飞书配置失败")
    return {"success": True, "message": "飞书配置已保存"}


@app.post("/api/admin/feishu/sync")
def api_feishu_trigger_sync(_: dict = Depends(require_super_admin)):
    """手动触发一次飞书同步（后台进程异步执行）"""
    import subprocess
    script = _FEISHU_ROOT / "feishu_sync" / "sync.py"
    subprocess.Popen(
        [sys.executable, str(script)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return {"success": True, "message": "同步任务已启动，请稍后查看日志"}


@app.post("/api/admin/feishu/sync-org-dict")
def api_feishu_sync_org_dict(req: dict, _: dict = Depends(require_super_admin)):
    """手动触发飞书机构字典同步"""
    from feishu_sync.import_org_dict import sync_org_dict
    force = req.get("force", False)
    result = sync_org_dict(force=force)
    return {"success": True, "data": result}


@app.get("/api/admin/feishu/status")
def api_feishu_get_status(_: dict = Depends(require_super_admin)):
    from feishu_sync.config import load_config, get_all_config_json
    from feishu_sync.scheduler import get_cron_status
    from feishu_sync.log_manager import list_log_files, tail_log
    load_config()

    cron_info = get_cron_status()
    config = get_all_config_json()

    # 最近日志
    recent_log = ""
    try:
        files = list_log_files()
        if files:
            recent_log = tail_log(files[0], n=10)
    except Exception:
        pass

    return {
        "data": {
            "config": config,
            "cron": cron_info,
            "recent_log": recent_log,
        }
    }


@app.get("/api/admin/feishu/auto-sync")
def api_feishu_get_auto_sync(_: dict = Depends(require_super_admin)):
    """获取自动同步配置"""
    from feishu_sync.config import get_sync_interval
    return {
        "data": {
            "interval_minutes": get_sync_interval(),
        }
    }


@app.post("/api/admin/feishu/auto-sync")
def api_feishu_set_auto_sync(req: FeishuAutoSyncRequest, _: dict = Depends(require_super_admin)):
    """设置自动同步间隔（保存到 config.json）"""
    from feishu_sync.config import save_to_json
    interval = max(0, req.interval_minutes)
    ok = save_to_json({"FEISHU_SYNC_INTERVAL_MINUTES": interval})
    if not ok:
        raise HTTPException(status_code=500, detail="保存自动同步配置失败")
    return {"success": True, "message": f"自动同步间隔已设为 {interval} 分钟"}


@app.get("/api/admin/feishu/cron-jobs")
def api_feishu_list_cron_jobs(_: dict = Depends(require_super_admin)):
    """列出所有定时同步任务"""
    from feishu_sync.scheduler import list_cron_jobs
    return {"data": list_cron_jobs()}


@app.post("/api/admin/feishu/cron-jobs")
def api_feishu_add_cron_job(req: FeishuCronJobRequest, _: dict = Depends(require_super_admin)):
    """添加定时同步任务"""
    from feishu_sync.scheduler import add_cron_job
    if not req.expression:
        raise HTTPException(status_code=400, detail="cron 表达式不能为空")
    ok = add_cron_job(req.expression, req.label)
    if not ok:
        raise HTTPException(status_code=500, detail="添加定时任务失败，可能标签重复或 crontab 不可用")
    return {"success": True, "message": f"定时任务已添加：{req.expression}"}


@app.delete("/api/admin/feishu/cron-jobs")
def api_feishu_delete_cron_job(label: str = Query(""), _: dict = Depends(require_super_admin)):
    """删除定时同步任务"""
    from feishu_sync.scheduler import remove_cron_job
    if not label:
        raise HTTPException(status_code=400, detail="请指定要删除的任务标签")
    ok = remove_cron_job(label)
    if not ok:
        raise HTTPException(status_code=404, detail=f"未找到定时任务: {label}")
    return {"success": True, "message": f"定时任务已删除: {label}"}


@app.put("/api/admin/feishu/cron-jobs")
def api_feishu_update_cron_job(req: FeishuCronJobRequest, _: dict = Depends(require_super_admin)):
    """更新定时同步任务"""
    from feishu_sync.scheduler import update_cron_job
    if not req.old_label:
        raise HTTPException(status_code=400, detail="请指定要更新的任务原标签")
    if not req.expression:
        raise HTTPException(status_code=400, detail="cron 表达式不能为空")
    ok = update_cron_job(req.old_label, req.expression, req.label)
    if not ok:
        raise HTTPException(status_code=404, detail=f"未找到定时任务: {req.old_label}")
    return {"success": True, "message": "定时任务已更新"}


@app.get("/api/admin/feishu/logs")
def api_feishu_get_logs(
    _: dict = Depends(require_super_admin),
    file: str = Query(""),
    lines: int = Query(10),
):
    """获取日志文件列表或指定日志内容"""
    from feishu_sync.log_manager import list_log_files, tail_log, cleanup_old_logs

    # 每次查看时自动清理超期日志
    cleanup_old_logs(days=10)

    if file:
        content = tail_log(file, n=lines)
        return {"data": {"file": file, "content": content}}
    else:
        files = list_log_files()
        return {"data": {"files": files}}


# ── 详情页面 ─────────────────────────────────────────────

DETAIL_HTML_PATH = os.path.join(os.path.dirname(__file__), "templates", "detail.html")

@app.get("/detail", response_class=HTMLResponse)
def detail_page(token: str = Query(""), reg_num: str = Query("")):
    with open(DETAIL_HTML_PATH, encoding="utf-8") as f:
        html = f.read()
    payload = decode_token(token)
    user_id = int(payload["sub"]) if payload else 0
    role = payload.get("role", "member") if payload else "member"
    html = html.replace("'{{ token }}'", repr(token))
    html = html.replace("{{ token }}", token)
    html = html.replace("'{{ reg_num }}'", repr(reg_num))
    html = html.replace("{{ reg_num }}", reg_num)
    html = html.replace("{{ user_id }}", str(user_id))
    html = html.replace("{{ role }}", role)
    return HTMLResponse(html)


# ── 启动 ────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8100)
