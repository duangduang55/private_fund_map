# 私募基金拓客辅助系统 — AI 背景层

## 项目概述

私募基金团队拓客业务工具。整合数据查询、地图展示、拜访计划、反馈记录为一套多用户协作系统，实现**筛选目标 → 查看分布 → 制定计划 → 拜访反馈**完整工作流。

**数据来源**：中国证券投资基金业协会（AMAC）官网爬取的私募基金管理人公开数据。

---

## 项目结构

```
private_fund_map/
├── app.py                      # Streamlit 主入口（登录 + 多页面路由）
├── start.sh                    # 一键启动脚本（检查DB → 启动FastAPI → 启动Streamlit）
├── .env.example                # 环境变量模板
├── CLAUDE.md                   # AI 背景层（本文件）
├── README.md                   # 人类友好层
├── requirements_doc.md         # 原始需求文档（参考）
│
├── pages/                      # Streamlit 页面模块
│   ├── __init__.py
│   ├── query.py                # 数据查询与导出页面
│   ├── plans.py                # 拜访计划页面（Streamlit 版）
│   ├── history.py              # 拜访历史 + 统计仪表盘
│   ├── batch_detail.py         # 批次详情页面（含操作/查看/PDF导出/地图）
│   └── batch_import.py         # 批量补录已拜访（搜索+反馈表单）
│
├── backend/                    # FastAPI 后端
│   ├── __init__.py
│   ├── main.py                 # 应用入口（全部 API 路由 + HTML 页面渲染）
│   ├── config.py               # 数据库连接配置 + JWT 密钥
│   ├── auth_utils.py           # JWT 生成/验证 + bcrypt 密码哈希
│   ├── db_tsquant.py           # ts_quant_db 只读查询（机构数据 + 命中原因匹配）
│   ├── db_fundmap.py           # fund_map_db CRUD（业务数据：用户/购物车/计划/反馈）
│   └── templates/              # HTML 模板（FastAPI 直接渲染，无 Jinja2）
│       ├── map.html            # 动态地图页面（Leaflet + 高德瓦片）
│       ├── confirm.html        # 确认拜访计划页面（含命中原因 + PDF 导出）
│       ├── plans.html          # 拜访计划列表页面
│       ├── feedback.html       # 拜访反馈表单页面
│       ├── detail.html         # 私募拜访记录详情页面
│       ├── batch_map.html      # 批次机构地图页面（Leaflet）
│       └── batch_detail_print.html  # 批次详情打印/PDF导出页面
│
├── .claude/
│   └── CLAUDE.md               # Harness Engineering 约束层（验证门禁、项目约束）
│
└── .streamlit/
    └── config.toml             # Streamlit 主题配置（暗色主题）
```

---

## 技术架构

```
Streamlit (8501)       FastAPI (8000)        PostgreSQL (5432)
  [登录界面]               [REST API]           ts_quant_db (只读)
  [数据查询/导出]    ◄──►  [JWT 认证]      ◄──►   private_fund_list
  [拜访计划/反馈]          [地图/确认/计划]        private_fund_detail
  [历史/统计]              [HTML 页面渲染] 
                                              fund_map_db (读写)
                                                users
                                                visit_cart
                                                visit_plans
                                                visit_feedback
```

| 组件 | 技术 | 版本 | 说明 |
|------|------|------|------|
| 前端（查询/表单） | Streamlit | ≥1.28 | Python 原生，快速构建数据应用 |
| 前端（地图） | Leaflet + 高德瓦片 | Leaflet 1.9 | 国产地图源 |
| API 后端 | FastAPI | ≥0.104 | 轻量异步，自动 OpenAPI |
| 数据库 | PostgreSQL | ≥15 | 双库设计，读写分离 |
| 认证 | JWT (python-jose) + bcrypt | — | 无状态 token 鉴权 |

---

## 数据库配置

### 配置方式（从 .env 加载）

所有数据库连接参数、JWT 密钥、API 地址均通过 `.env` 文件配置。
复制 `.env.example` 为 `.env` 后修改即可。配置项：

```
TS_QUANT_DB_HOST/PORT/NAME/USER/PASSWORD  —  ts_quant_db 连接参数
FUND_MAP_DB_HOST/PORT/NAME/USER/PASSWORD  —  fund_map_db 连接参数
JWT_SECRET / JWT_ALGORITHM / JWT_EXPIRE_MINUTES  —  JWT 认证配置
API_BASE_URL  —  前端连接后端的 API 地址
```

### ts_quant_db（只读 — 私募机构数据来源）
```python
{"host": "localhost", "port": 5432, "dbname": "ts_quant_db",
 "user": "db_query_user", "password": "123456789"}
```

#### `private_fund_list` — 基金管理人摘要信息（拍平表）

| 字段 | 类型 | 说明 |
|------|------|------|
| reg_num | VARCHAR(20) PK | 登记编号 |
| sys_id | VARCHAR(20) | 系统 ID |
| org_name | VARCHAR(200) | 机构名称 |
| lic_num | VARCHAR(50) | 营业执照号 |
| leg_person | VARCHAR(50) | 法定代表人 |
| act_controller | TEXT | 实际控制人 |
| est_date | DATE | 成立时间 |
| reg_date | DATE | 登记时间 |
| has_products | VARCHAR(2) | 是否有产品 |
| org_aum | VARCHAR(20) | 管理规模（如"0-5亿元"） |
| detail_url | TEXT | 详情页 URL |
| reg_address | TEXT | 注册地址 |
| reg_province | VARCHAR(50) | 注册省份 |
| reg_city | VARCHAR(50) | 注册城市 |
| fund_count | INTEGER | 基金数量 |
| paid_capital | DECIMAL(20,4) | 实缴资本(万) |
| reg_capital | DECIMAL(20,4) | 认缴资本(万) |
| emp_num | INT | 全职员工人数 |
| fund_pra_num | INT | 从业人员数 |
| reg_coordinates | VARCHAR(100) | 注册地坐标("纬度,经度") |
| office_coordinates | VARCHAR(100) | 办公地坐标("纬度,经度") |
| office_address | TEXT | 办公地址 |
| office_province | VARCHAR(50) | 办公省份 |
| office_city | VARCHAR(50) | 办公城市 |
| has_special_notice | VARCHAR(2) | 是否有特别提示 |
| has_credit_notice | VARCHAR(2) | 是否有信用提示 |
| ent_nature | VARCHAR(50) | 企业性质 |
| ins_type | VARCHAR(100) | 机构类型 |
| main_invest_type | TEXT | 主要投资类型 |
| member_type | VARCHAR(50) | 会员类型 |
| org_form | VARCHAR(100) | 组织形式 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

#### `private_fund_detail` — 基金管理人详情（JSONB）

| 字段 | 类型 | 说明 |
|------|------|------|
| reg_num | VARCHAR(20) PK | 登记编号 |
| org_name | VARCHAR(200) | 机构名称 |
| org_aum | VARCHAR(20) | 管理规模 |
| parsed_data | JSONB NOT NULL | 完整详情 JSON |

**JSONB 关键路径**：

| 业务 | JSON路径 | 说明 |
|------|----------|------|
| 产品列表 | `parsed_data->'products'->'funds_after'` | 核心产品数组 |
| 产品状态 | `->'investor_open_rate'` | "基金已清算"=已清算 |
| 高管列表 | `parsed_data->'executives'` | 高管数组 |
| 高管履历 | `executives[].resumes[].employer` | 任职单位 |
| 会员类型 | `parsed_data->'member_info'->>'member_type'` | 会员类型 |

**关键查询**：
- JSONB 展开用 `jsonb_array_elements()`，NULL 用 `COALESCE(..., '[]'::jsonb)` 保护
- 已清算产品判断：`investor_open_rate = '基金已清算'`
- Decimal('NaN') 序列化需转 None

### fund_map_db（读写 — 业务数据）
```python
{"host": "localhost", "port": 5432, "dbname": "fund_map_db",
 "user": "fund_map_user", "password": "123456789"}
```

#### `users` — 用户账号

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PK | 用户 ID |
| username | VARCHAR(50) UNIQUE | 登录用户名 |
| password_hash | TEXT | bcrypt 哈希密码 |
| display_name | VARCHAR(100) | 显示名称 |
| role | VARCHAR(20) | admin/member |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

#### `visit_cart` — 待拜访清单（购物车）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PK | 记录 ID |
| user_id | INTEGER FK→users | 所属用户 |
| reg_num | VARCHAR(20) | 登记编号 |
| org_name | VARCHAR(200) | 机构名称 |
| org_aum | VARCHAR(20) | 管理规模 |
| fund_count | INTEGER | 基金数量 |
| office_address | TEXT | 办公地址 |
| office_coordinates | VARCHAR(100) | 办公地坐标 |
| created_at | TIMESTAMP | 添加时间 |

#### `visit_plans` — 拜访计划

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PK | 计划 ID |
| reg_num | VARCHAR(20) | 登记编号 |
| org_name | VARCHAR(200) | 机构名称 |
| org_aum | VARCHAR(20) | 管理规模 |
| fund_count | INTEGER | 基金数量 |
| office_address | TEXT | 办公地址 |
| office_coordinates | VARCHAR(100) | 办公地坐标 |
| planned_date | DATE | 计划拜访日期 |
| visitor_name | VARCHAR(100) | 拜访人 |
| user_id | INTEGER FK→users | 创建人 |
| batch_id | VARCHAR(12) | 批次 ID（同一批确认的计划共享） |
| status | VARCHAR(20) | pending/completed/cancelled |
| remark | TEXT | 备注 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

#### `visit_feedback` — 拜访反馈

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PK | 反馈 ID |
| visit_plan_id | INTEGER FK→visit_plans UNIQUE | 关联计划 |
| visit_date | DATE | 拜访日期 |
| visitor_name | VARCHAR(100) | 拜访人 |
| visit_status | VARCHAR(20) | 成功/未见到/已搬迁/地址有误/其他 |
| contact_obtained | BOOLEAN | 是否获取联系方式 |
| has_business_card | BOOLEAN | 是否有名片 |
| has_contact_info | BOOLEAN | 是否获取联系信息 |
| summary | TEXT | 摘要 |
| communication_detail | TEXT | 沟通情况 |
| follow_up_suggestions | TEXT | 后续跟进建议 |
| tags | TEXT[] | 标签数组 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

---

## 设计系统

2026-05 重构为企业蓝灰专业风格，去除所有渐变和发光效果。

### 颜色 Token

| Token | 值 | 用途 |
|-------|-----|------|
| `--bg-primary` | `#0f172a` | 页面背景 |
| `--bg-secondary` | `#1e293b` | 卡片/面板背景 |
| `--border-default` | `#334155` | 默认边框 |
| `--text-primary` | `#f1f5f9` | 主文本 |
| `--text-secondary` | `#94a3b8` | 次要文本 |
| `--text-muted` | `#64748b` | 灰色信息 |
| `--accent` | `#2563eb` | 主色（蓝色） |
| `--success` | `#16a34a` | 成功 |
| `--warning` | `#d97706` | 警告 |
| `--danger` | `#dc2626` | 危险 |

### CSS 来源

- **Streamlit 页面**: `app.py` 中的 `CUSTOM_CSS` 变量
- **HTML 模板**: `backend/templates/*.html` 的内联 `<style>` 块
- **Streamlit 主题**: `.streamlit/config.toml`（仅基础色）

### 改造原则

1. 纯色背景代替 `linear-gradient`
2. 无 `text-shadow` 发光效果
3. 无 hover 动画（`translateY` 等）
4. 按钮纯色 `#2563eb`，hover 变深 `#1d4ed8`
5. 圆角从 12px 简化为 6px
6. 标签去大写、去 letter-spacing
7. 地图弹窗/状态选择器等交互性元素的配色同步更新

---

## API 端点一览

| 方法 | 路径 | 说明 | 需认证 |
|------|------|------|--------|
| POST | `/api/auth/login` | 用户登录 | 否 |
| POST | `/api/auth/register` | 用户注册 | 否 |
| GET | `/api/auth/me` | 获取当前用户 | 是 |
| GET | `/api/filters` | 获取筛选下拉选项 | 否 |
| GET | `/api/funds` | 基金查询（8维筛选+分页） | 否 |
| GET | `/api/map-data` | 地图数据（含已拜访标记） | 否 |
| GET | `/api/cart` | 获取购物车 | 是 |
| POST | `/api/cart/add` | 加入购物车 | 是 |
| POST | `/api/cart/toggle-star/{cart_id}` | 切换购物车条目星标 | 是 |
| DELETE | `/api/cart/{id}` | 删除购物车条目 | 是 |
| DELETE | `/api/cart` | 清空购物车 | 是 |
| POST | `/api/match-reasons` | 批量查询命中原因（产品名/高管履历） | 否 |
| POST | `/api/plans/confirm` | 购物车→计划确认（返回生成计划列表） | 是 |
| GET | `/api/plans` | 获取计划列表 | 是 |
| GET | `/api/plans/by-batch/{batch_id}` | 按批次查询所有计划（含反馈信息） | 是 |
| POST | `/api/plans/toggle-star/{plan_id}` | 设置计划星标 | 是 |
| POST | `/api/plans/unstar/{plan_id}` | 取消计划星标 | 是 |
| POST | `/api/plans/auto-expire` | 自动过期7天未反馈计划 | 是 |
| POST | `/api/plans/batch-import` | 批量补录（仅计划） | 是 |
| POST | `/api/plans/batch-import-with-feedback` | 批量补录（含反馈） | 是 |
| POST | `/api/plans/batch-import-simple` | 批量补录（传reg_num自动查询并创建） | 是 |
| GET | `/api/feedback/{plan_id}` | 获取反馈 | 是 |
| POST | `/api/feedback` | 创建/更新反馈 | 是 |
| GET | `/api/history` | 历史记录（含反馈信息） | 是 |
| GET | `/api/stats` | 统计概览 | 是 |
| GET | `/api/visited-info` | 已拜访信息（最新1条） | 否 |
| GET | `/api/visited-history` | 拜访历史（最多5条） | 否 |
| POST | `/api/fund-links` | 批量查询机构AMAC详情页URL | 否 |
| GET | `/api/fund-profile/{reg_num}` | 机构详细信息+标签+拜访记录 | 是 |
| GET | `/map` | 动态地图页面（HTML，Leaflet+高德） | 需token |
| GET | `/confirm` | 确认拜访计划页面（HTML，含命中原因） | 需token |
| GET | `/plans` | 计划列表页面（HTML，响应式表格） | 需token |
| GET | `/feedback` | 反馈表单页面（HTML） | 需token+plan_id |
| GET | `/detail` | 私募拜访记录详情页面（HTML） | 需token+reg_num |
| GET | `/batch-map` | 批次机构地图页面（HTML，星标突出） | 需token+batch_id |
| GET | `/batch-detail-print` | 批次详情打印/PDF导出页面（HTML） | 需token+batch_id |

---

## 运行方式

### 完整启动
```bash
cd /Users/zhanglei/claudecode_data/quant_data/private_fund_map
bash start.sh
```
start.sh 会自动检测 Python 环境（优先 venv/ → .venv/ → conda → 系统 python3），
从 `.env` 加载数据库配置，然后启动 FastAPI 后端和 Streamlit 前端。
如需在新设备上使用：复制 `.env.example` 为 `.env`，修改配置，然后直接运行 `start.sh`。

### 分终端启动
```bash
# 终端1 — FastAPI 后端
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# 终端2 — Streamlit 前端
streamlit run app.py --server.port 8501
```

### 访问地址
| 服务 | 地址 |
|------|------|
| Streamlit | http://localhost:8501 |
| FastAPI API | http://localhost:8000 |
| Swagger 文档 | http://localhost:8000/docs |
| 地图页面 | http://localhost:8000/map?token=xxx |

### 默认账号
| 用户名 | 密码 | 角色 |
|--------|------|------|
| admin | admin123 | admin |

---

## 编码约定

- **数据库**：不修改表结构，JSONB 查询需 COALESCE 保护
- **HTML 模板**：Token 通过字符串替换注入（{{ token }}），不使用 Jinja2
- **地图标记**：Leaflet + 高德瓦片，标记按 AUM 分色
- **Python**：ruff 检查（line-length=100），bcrypt 密码哈希
- **Streamlit 页面**：复用 `app.py` 中的 `st.session_state.token` 鉴权模式
- **后端新路由**：在 `backend/main.py` 中添加，Pydantic 定义请求模型

---

## 实现状态

| 功能 | 状态 |
|------|------|
| 基础设施（FastAPI + Streamlit + JWT） | ✅ |
| 私募数据查询 + Excel 导出 | ✅ |
| 动态地图（Leaflet + 高德瓦片） | ✅ |
| 购物车（待拜访清单）CRUD | ✅ |
| 拜访计划生成/确认/PDF导出 | ✅ |
| 拜访反馈表单 | ✅ |
| 拜访历史 + 统计仪表盘 | ✅ |
| 批量补录已拜访 | ✅ |
| 拜访计划分组管理（batch_id） | ✅ |
| 计划列表页（FastAPI 渲染，响应式表格） | ✅ |
| 批次详情页（操作/反馈/查看 列） | ✅ |
| 私募拜访记录详情页 | ✅ |
| 批次机构地图（星标突出显示） | ✅ |
| 批次详情打印/PDF导出 | ✅ |
| 购物车/计划加星标标记 | ✅ |
| 全平台星标图标展示 | ✅ |
