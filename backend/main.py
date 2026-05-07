"""FastAPI 主应用 — 私募基金拓客辅助系统后端"""

from fastapi import FastAPI, HTTPException, Depends, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import os

from backend.config import TS_QUANT_DB
from backend.auth_utils import hash_password, verify_password, create_token, decode_token
from backend.db_tsquant import (
    query_funds,
    query_funds_for_map,
    query_funds_by_reg_nums,
    check_match_reasons,
    load_distinct_values,
    parse_keywords,
    parse_product_range,
)
from backend.db_fundmap import (
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
    create_plans_from_cart,
    get_user_plans,
    get_feedback_by_plan_id,
    upsert_feedback,
    update_plan_status,
    get_plans_with_feedback,
    get_visit_stats,
    auto_expire_plans,
    batch_import_visited,
    batch_import_with_feedback,
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

MAP_HTML_PATH = os.path.join(os.path.dirname(__file__), "templates", "map.html")


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
    contact_obtained: bool = False
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
    # 注入 token（JS 中的和 HTML 中的）
    token_str = (token or "")
    html = html.replace("'{{ token }}'", repr(token_str))
    html = html.replace("{{ token }}", token_str)
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
    html = html.replace("{{ token }}", token_str)
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


# ── 命中原因 API ──────────────────────────────────────────────

@app.post("/api/match-reasons")
def api_match_reasons(req: MatchReasonsRequest):
    matches = check_match_reasons(req.reg_nums, req.product_keywords, req.executive_keywords)
    return {"data": matches}


# ── 拜访计划 API ───────────────────────────────────────────────

@app.post("/api/plans/confirm")
def api_confirm_plans(req: ConfirmPlanRequest, user: dict = Depends(get_current_user)):
    plans = create_plans_from_cart(user["id"], req.planned_date, req.visitor_name)
    return {"success": True, "count": len(plans), "data": plans}


@app.get("/api/plans")
def api_get_plans(user: dict = Depends(get_current_user)):
    auto_expire_plans()  # 每次查看计划时自动过期
    return {"data": get_user_plans(user["id"], user["role"])}


# ── 拜访反馈 API ──────────────────────────────────────────────

@app.get("/api/feedback/{plan_id}")
def api_get_feedback(plan_id: int, user: dict = Depends(get_current_user)):
    fb = get_feedback_by_plan_id(plan_id)
    return fb or {}


@app.post("/api/feedback")
def api_save_feedback(req: FeedbackRequest, user: dict = Depends(get_current_user)):
    fb = upsert_feedback(req.visit_plan_id, req.model_dump())
    if req.plan_status:
        update_plan_status(req.visit_plan_id, req.plan_status)
    return {"success": fb is not None, "data": fb}


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
    contact_obtained: bool = False
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


# ── 启动 ────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
