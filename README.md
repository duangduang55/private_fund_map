# 私募基金拓客辅助系统

## 项目简介

本项目源于私募基金团队的实际拓客业务需求。团队通过走访私募机构开展客户拓展，面临数据不同步、工具脱节、缺少完整工作流闭环等问题。本系统将数据查询、地图展示、拜访计划、反馈记录整合为一套团队协作工具，实现从**筛选目标 → 查看分布 → 制定计划 → 拜访反馈**的完整工作流。

**数据来源**：中国证券投资基金业协会（AMAC）官网爬取的私募基金管理人公开数据。

---

## 功能列表

### 用户认证
- 用户名 + 密码登录，JWT（8小时有效）保持会话
- 双角色权限：admin（全部权限）、member（仅本人数据）
- 默认管理员：`admin` / `admin123`

### 私募数据查询
- 8 维筛选条件：办公省份、管理规模、企业性质、会员类型、机构类型、产品数量范围、产品名称模糊搜索（OR 多关键词）、高管履历模糊搜索（OR 多关键词）
- 默认排除已清算产品
- 结果表格中文列名展示，智能高亮命中列
- 一键 Excel 导出（含时间戳文件名）
- 结果批量"加入待拜访清单"
- 查询结果"在地图上显示"（携带筛选参数）

### 动态地图展示（Leaflet + 高德瓦片）
- 全国私募机构分布展示，标记按**管理规模**分色
- 图例切换：管理规模模式 ↔ 拜访状态模式
- 已拜访机构灰色特殊标记（虚线边框），避免重复拜访
- 三态拜访标记：已拜访（灰色带✓）、待拜访（AUM色带⏳）、未拜访（纯AUM色）
- 搜索框模糊匹配机构名称，匹配标记高亮跳动
- 标记点击弹窗：机构详情、高管/产品命中信息、详情页链接、"加入待拜访清单"按钮
- 已拜访弹窗展示最多5条拜访历史（含待拜访/已完成，按时间倒序）
- 右侧侧滑清单窗口，不遮挡地图操作
- 购物车条目支持⭐星标标记

### 待拜访清单（购物车）
- 地图标记弹窗 → 一键加入清单
- 侧滑窗口展示清单，支持逐条删除、加星标
- 清单数据按用户隔离
- 自动去重（同一条私募不能重复添加）

### 拜访计划
- **确认页面**：展示管理规模、基金数量、办公地址、**命中原因**（产品名命中/高管履历命中）
- 确认页面支持星标标记/取消
- 确认后自动生成本次提交的唯一 `batch_id`，同一批计划可统一管理
- **PDF 导出**（浏览器打印渲染，A4 专业排版，星标机构突出显示）
- 填写拜访日期、拜访人，生成计划
- **计划列表**：按状态统计（待拜访/已完成/已取消），星标机构 ⭐ 标识，响应式表格
- **拜访计划列**显示 `日期#批次ID` 格式，点击可进入批次详情页
- 计划状态实时更新（pending/completed/cancelled）

### 拜访反馈
- 从计划列表点击"填写反馈"
- 反馈表单：拜访状态（成功/未见到/已搬迁/地址有误/其他）、联系方式、名片、沟通摘要、沟通详情、标签（合作意向/不对外/不合作/需求高度匹配）、后续建议
- 同步更新计划状态
- 支持编辑已提交的反馈

### 拜访历史与统计
- admin 查看全部记录，member 仅看自己
- 多维筛选：状态、反馈情况、拜访结果
- 统计概览：总计划数、待拜访、已完成、已取消、已反馈、成功拜访数
- CSV 导出

### 批次管理
- 每次确认提交自动生成 batch_id，同一批计划共享批次号
- **批次详情页**（Streamlit）：展示批次信息卡片，机构明细表格（含操作/查看列）
- **批次机构地图**：地图显示该批次所有机构，星标机构**更大图标（40px）**+金色边框发光+弹窗常开
- **批次详情打印/PDF导出**：全宽表格，百分比列宽，星标特殊标识

### 星标标记系统
- 地图购物车：支持 ⭐ 星标标记重要机构
- 确认页面：标记/取消星标
- 确认后星标状态同步到拜访计划
- **全平台展示**：计划列表、拜访历史、批次详情、地图弹窗，星标机构名称旁均显示 ⭐

### 批量补录（已拜访）
- 机构模糊搜索，从私募库中查找目标
- 搜索结果列表展示（名称、登记编号、管理规模），每条记录带 + 按钮
- 添加后展开完整反馈表单：简要总结、联系情况、沟通详情、标签、后续建议
- 提交后自动创建已完成拜访计划 + 反馈记录（状态=已完成，visit_status=其他，tags含"手动补录"）

---

## 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                   用户浏览器 (Browser)                        │
└──────────┬─────────────────────────────────┬────────────────┘
           │                                 │
           ▼                                 ▼
┌──────────────────────┐     ┌──────────────────────────────┐
│  Streamlit (端口8501)  │     │     FastAPI (端口8100)       │
│                       │     │                              │
│  · 用户登录            │HTTP │  · REST API (JSON)           │
│  · 数据查询/筛选        │◄───►│  · JWT 认证                  │
│  · 表格展示/Excel导出   │     │  · 动态地图 (Leaflet+HTML)   │
│  · 拜访计划/反馈表单    │     │  · 购物车 / 计划 / 反馈 CRUD  │
│  · 拜访历史/统计        │     │  · 确认 / 计划 / 反馈页面     │
│  · 批次详情/地图        │     │  · 批次地图 / 打印页面        │
└──────────┬────────────┘     └──────────┬───────────────────┘
           │                              │
           ▼                              ▼
┌──────────────────────┐     ┌──────────────────────────────┐
│  ts_quant_db (只读)   │     │  fund_map_db (读写)           │
│  · private_fund_list  │     │  · users (用户账号)           │
│  · private_fund_detail│     │  · visit_cart (购物车)        │
│  (私募机构数据来源)     │     │  · visit_plans (拜访计划)     │
│                       │     │  · visit_feedback (拜访反馈)   │
└──────────────────────┘     └──────────────────────────────┘
```

### 技术选型

| 组件 | 技术 | 版本 | 说明 |
|------|------|------|------|
| 前端（查询/表单） | Streamlit | ≥1.28 | Python 原生，快速构建数据应用 |
| 前端（地图） | Leaflet + 高德瓦片 | Leaflet 1.9 | 国产地图源，国内加载流畅 |
| API 后端 | FastAPI | ≥0.104 | 轻量异步，自动 OpenAPI 文档 |
| 数据库 | PostgreSQL | ≥15 | 双数据库设计，读写分离 |
| 认证 | JWT (python-jose) + bcrypt | — | 无状态 token 鉴权 |

### Python 依赖

```
fastapi>=0.104.0          # Web 框架
uvicorn>=0.24.0           # ASGI 服务器
streamlit>=1.28.0         # 数据应用前端
psycopg2-binary>=2.9.9    # PostgreSQL 驱动
python-jose[cryptography]>=3.3.0  # JWT 编解码
bcrypt>=4.1.2             # 密码哈希
pydantic>=2.5.0           # 数据验证
requests>=2.31.0          # HTTP 客户端（Streamlit 调用 API）
openpyxl>=3.1.2           # Excel 导出
python-dotenv>=1.0.0      # .env 文件加载
```

---

## 项目结构

```
private_fund_map/
├── app.py                      # Streamlit 主入口（多页面路由 + 登录）
├── start.sh                    # 一键启动脚本
├── .env.example                # 环境变量模板
├── requirements_doc.md         # 需求文档（参考）
├── CLAUDE.md                   # AI 协作说明
├── README.md                   # 本文件
│
├── pages/                      # Streamlit 页面模块
│   ├── __init__.py
│   ├── query.py                # 数据查询与导出页面
│   ├── plans.py                # 拜访计划页面（Streamlit 版）
│   ├── history.py              # 拜访历史 + 统计仪表盘
│   ├── batch_detail.py         # 批次详情页面
│   └── batch_import.py         # 批量补录已拜访
│
├── backend/                    # FastAPI 后端
│   ├── __init__.py
│   ├── main.py                 # 全部 API 路由 + HTML 页面
│   ├── config.py               # 数据库配置 + JWT 密钥
│   ├── auth_utils.py           # JWT + bcrypt 认证工具
│   ├── db_tsquant.py           # ts_quant_db 查询（只读）
│   ├── db_fundmap.py           # fund_map_db CRUD（业务数据）
│   └── templates/              # HTML 模板（FastAPI 直接渲染）
│       ├── map.html            # 动态地图页面（Leaflet + 高德）
│       ├── confirm.html        # 确认拜访计划
│       ├── plans.html          # 拜访计划列表
│       ├── feedback.html       # 拜访反馈表单
│       ├── detail.html         # 私募拜访记录详情
│       ├── batch_map.html      # 批次机构地图
│       └── batch_detail_print.html  # 批次详情打印
│
└── .streamlit/
    └── config.toml             # Streamlit 主题配置（暗色主题）
```

---

## 运行方式

### 环境要求

- **Python** ≥ 3.10
- **PostgreSQL** ≥ 15（需同时存在 `ts_quant_db` 和 `fund_map_db` 两个数据库）
- **pip 依赖**：详见上方列表

### 安装依赖

```bash
cd private_fund_map
pip install -r requirements_doc.md  # 或手动安装上方列出的包
```

### 方式一：一键启动（推荐）

```bash
bash start.sh
```

脚本自动执行：检查数据库连接 → 启动 FastAPI 后端 → 启动 Streamlit 前端

### 方式二：分终端启动

```bash
# 终端 1 — FastAPI 后端（端口 8100）
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8100 --reload

# 终端 2 — Streamlit 前端（端口 8501）
streamlit run app.py --server.port 8501
```

### 访问地址

| 服务 | 地址 | 说明 |
|------|------|------|
| Streamlit 主界面 | http://localhost:8501 | 登录 → 查询 → 计划 → 历史 |
| FastAPI API | http://localhost:8100 | REST API |
| API 文档 (Swagger) | http://localhost:8100/docs | 交互式 API 调试 |
| 地图页面 | http://localhost:8100/map?token=xxx | 全国私募分布 |
| 确认计划 | http://localhost:8100/confirm?token=xxx | 命中原因 + PDF导出 |
| 计划列表 | http://localhost:8100/plans?token=xxx | 响应式计划表格 |
| 拜访反馈 | http://localhost:8100/feedback?token=xxx&plan_id=xxx | |
| 私募详情 | http://localhost:8100/detail?token=xxx&reg_num=xxx | 拜访记录详情 |
| 批次地图 | http://localhost:8100/batch-map?token=xxx&batch_id=xxx | |
| 批次打印 | http://localhost:8100/batch-detail-print?token=xxx&batch_id=xxx | |

### 默认账号

| 用户名 | 密码 | 角色 |
|--------|------|------|
| admin | admin123 | 管理员（admin） |

---

## 数据库配置

系统依赖两个 PostgreSQL 数据库。配置从 `.env` 文件加载（复制 `.env.example` 为 `.env` 修改即可）。

### ts_quant_db（只读 — 私募机构数据来源）

```python
{"host": "localhost", "port": 5432, "dbname": "ts_quant_db",
 "user": "db_query_user", "password": "123456789"}
```

核心表：
- `private_fund_list` — 基金管理人摘要信息（拍平表，含地址、规模、省份、坐标等）
- `private_fund_detail` — 基金管理人详情 JSONB（产品列表、高管履历、会员信息）

### fund_map_db（读写 — 业务数据）

```python
{"host": "localhost", "port": 5432, "dbname": "fund_map_db",
 "user": "fund_map_user", "password": "123456789"}
```

4 张业务表：

| 表名 | 用途 | 关键字段 |
|------|------|----------|
| `users` | 用户账号 | username, password_hash, display_name, role |
| `visit_cart` | 待拜访清单 | user_id, reg_num, org_name, **starred**, office_coordinates |
| `visit_plans` | 拜访计划 | user_id, reg_num, planned_date, visitor_name, status, **starred**, batch_id |
| `visit_feedback` | 拜访反馈 | visit_plan_id(UNIQUE), visit_status, tags, summary |

---

## API 端点一览

| 方法 | 路径 | 说明 | 需认证 |
|------|------|------|--------|
| POST | /api/auth/login | 用户登录 | 否 |
| POST | /api/auth/register | 用户注册 | 否 |
| GET | /api/auth/me | 获取当前用户 | 是 |
| GET | /api/filters | 获取筛选选项 | 否 |
| GET | /api/funds | 基金查询（8维+分页） | 否 |
| GET | /api/map-data | 地图数据 | 否 |
| GET | /api/cart | 获取购物车 | 是 |
| POST | /api/cart/add | 加入购物车 | 是 |
| POST | /api/cart/toggle-star/{id} | 切换星标 | 是 |
| DELETE | /api/cart/{id} | 删除购物车条目 | 是 |
| DELETE | /api/cart | 清空购物车 | 是 |
| POST | /api/plans/confirm | 购物车→计划确认 | 是 |
| GET | /api/plans | 计划列表 | 是 |
| GET | /api/plans/by-batch/{id} | 按批次查询 | 是 |
| POST | /api/plans/toggle-star/{id} | 设置星标 | 是 |
| POST | /api/plans/unstar/{id} | 取消星标 | 是 |
| POST | /api/feedback | 创建/更新反馈 | 是 |
| GET | /api/feedback/{plan_id} | 获取反馈 | 是 |
| GET | /api/history | 历史记录 | 是 |
| GET | /api/stats | 统计概览 | 是 |
| POST | /api/match-reasons | 查询命中原因 | 否 |
| POST | /api/fund-links | 批量查详情URL | 否 |
| GET | /api/fund-profile/{reg_num} | 机构详细信息 | 是 |

**HTML 页面**（FastAPI 渲染）：
| 路径 | 说明 | 参数 |
|------|------|------|
| /map | 动态地图 | token |
| /confirm | 确认计划 | token |
| /plans | 计划列表 | token |
| /feedback | 反馈表单 | token, plan_id |
| /detail | 私募详情 | token, reg_num |
| /batch-map | 批次地图 | token, batch_id |
| /batch-detail-print | 批次打印 | token, batch_id |

---

## 使用流程

1. **登录系统** → 打开 Streamlit (localhost:8501)，使用 admin/admin123 登录
2. **查询筛选** → 在查询页选择条件，点击查询
3. **地图查看** → 点击"在地图上显示"或直接打开地图页面
4. **加入清单** → 在地图标记弹窗中点击"加入待拜访清单"
5. **标记星标** → 在购物车中 ⭐ 标记重要机构
6. **确认计划** → 填写日期和拜访人，确认星标，导出 PDF 后提交
7. **查看计划** → 在计划列表页或 Streamlit 拜访计划页查看
8. **批次详情** → 点击 `日期#批次ID` 进入批次详情页
9. **批次地图** → 在批次详情页点击"在地图上查看"
10. **填写反馈** → 拜访完成后，点击计划旁的"填写反馈"
11. **查看历史** → 在历史页面查看统计和完整记录
12. **批量补录** → 已拜访的机构在补录页搜索添加并补填反馈信息

---

## 注意事项

1. **PostgreSQL 必须提前启动**，两个数据库（ts_quant_db + fund_map_db）需已创建
2. **地图页面需要 token 参数**，直接访问 `/map` 会显示空白页
3. **高德瓦片依赖外网**，国内环境加载流畅
4. **PDF导出**：使用浏览器打印渲染（Ctr+P / Cmd+P），选择"另存为 PDF"
5. **`--reload` 模式下**修改 HTML 模板或 Python 文件会自动生效
6. **地图标记数量**建议控制在 5000 个以内
7. **JWT Token 有效期**默认 8 小时，过期需重新登录
8. **JS 模板注入**：token 通过字符串替换注入 HTML（`{{ token }}`），不使用 Jinja2

---

## 开发状态

| 功能 | 状态 |
|------|------|
| 基础设施（FastAPI + Streamlit + JWT） | ✅ |
| 私募数据查询 + Excel 导出 | ✅ |
| 动态地图（Leaflet + 高德瓦片） | ✅ |
| 购物车（待拜访清单）CRUD + 星标 | ✅ |
| 拜访计划生成/确认/PDF导出 | ✅ |
| 拜访计划分组管理（batch_id） | ✅ |
| 拜访反馈表单 + 编辑 | ✅ |
| 拜访历史 + 统计仪表盘 | ✅ |
| 批量补录已拜访 | ✅ |
| 计划列表页（FastAPI 响应式） | ✅ |
| 批次详情页（操作/反馈/查看） | ✅ |
| 私募拜访记录详情页 | ✅ |
| 批次机构地图（星标突出） | ✅ |
| 批次详情打印/PDF导出 | ✅ |
| 全平台星标展示 | ✅ |
