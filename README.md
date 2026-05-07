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

### 待拜访清单（购物车）
- 地图标记弹窗 → 一键加入清单
- 侧滑窗口展示清单，支持逐条删除
- 清单数据按用户隔离
- 自动去重（同一条私募不能重复添加）

### 拜访计划
- 确认页面：展示管理规模、基金数量、办公地址、**命中原因**（产品名命中/高管履历命中）
- 确认后可**一键导出 PDF**（打印渲染，A4 专业排版）
- 填写拜访日期、拜访人，生成计划
- 计划列表：按状态统计（待拜访/已完成/已取消）、响应式表格
- 计划状态实时更新

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
│  Streamlit (端口8501)  │     │     FastAPI (端口8000)       │
│                       │     │                              │
│  · 用户登录            │HTTP │  · REST API (JSON)           │
│  · 数据查询/筛选        │◄───►│  · JWT 认证                  │
│  · 表格展示/Excel导出   │     │  · 动态地图 (Leaflet+HTML)   │
│  · 拜访计划/反馈表单    │     │  · 购物车 / 计划 / 反馈 CRUD  │
│  · 拜访历史查看/统计    │     │  · 确认 / 计划 / 反馈页面     │
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
| 地图瓦片 | 高德地图 WMS | — | https://webrd01.is.autonavi.com/... |

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
```

---

## 项目结构

```
private_fund_map/
├── app.py                      # Streamlit 主入口（多页面 + 登录）
├── start.sh                    # 一键启动脚本
├── config.ini.example          # 配置模板（复制为 config.ini 后填写真实信息）
├── README.md                   # 本文件
│
├── pages/                      # Streamlit 页面模块
│   ├── __init__.py
│   ├── query.py                # 数据查询与导出页面
│   ├── plans.py                # 拜访计划页面（Streamlit 版）
│   ├── history.py              # 拜访历史 + 统计仪表盘
│   └── batch_import.py         # 批量补录已拜访（搜索+反馈表单）
│
├── backend/                    # FastAPI 后端
│   ├── __init__.py
│   ├── main.py                 # 应用入口（全部 API 路由 + HTML 页面：地图/确认/计划/反馈）
│   ├── config.py               # 数据库配置 + JWT 配置（支持 config.ini / 环境变量）
│   ├── auth_utils.py           # JWT + bcrypt 认证工具
│   ├── db_tsquant.py           # ts_quant_db 查询（只读，含命中原因匹配）
│   ├── db_fundmap.py           # fund_map_db CRUD（业务数据）
│   └── templates/              # HTML 模板（FastAPI 直接渲染）
│       ├── map.html            # 动态地图页面（Leaflet + 高德）
│       ├── confirm.html        # 确认拜访计划页面
│       ├── plans.html          # 拜访计划列表页面
│       └── feedback.html       # 拜访反馈表单页面
│
└── .streamlit/
    └── config.toml             # Streamlit 主题配置
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
pip install fastapi uvicorn streamlit psycopg2-binary "python-jose[cryptography]" bcrypt pydantic requests openpyxl
```



### 配置数据库

```bash
# 1. 复制配置模板
cp config.ini.example config.ini
# 2. 编辑 config.ini，填入真实的数据库连接信息和 JWT 密钥
#    （config.ini 已被 .gitignore 排除，不会提交到仓库）
```

系统依赖两个 PostgreSQL 数据库：
- **ts_quant_db**（只读）：存储从 AMAC 爬取的私募机构数据
- **fund_map_db**（读写）：存储用户账号、拜访计划、反馈等业务数据

也可通过环境变量配置（优先级高于 config.ini）：
```bash
export FUND_MAP__ts_quant_db__password=your_password
export FUND_MAP__fund_map_db__password=your_password
export FUND_MAP__jwt__secret=your_random_secret
```

### 初始化数据库

首次使用需创建业务表（`fund_map_db` 中的 users、visit_cart、visit_plans、visit_feedback）：

```bash
# FastAPI 启动后会自动创建缺失的表
# 也可手动执行：
python3 -c "from backend.db_fundmap import init_db; init_db()"
```


### 方式一：一键启动（推荐）

```bash
bash start.sh
```

脚本自动执行：检查数据库连接 → 启动 FastAPI 后端 → 启动 Streamlit 前端

### 方式二：分终端启动

```bash
# 终端 1 — FastAPI 后端
cd private_fund_map
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# 终端 2 — Streamlit 前端
cd private_fund_map
streamlit run app.py --server.port 8501
```

### 访问地址

| 服务 | 地址 | 说明 |
|------|------|------|
| Streamlit 主界面 | http://localhost:8501 | 登录 → 查询 → 计划 → 历史 |
| FastAPI API | http://localhost:8000 | REST API |
| API 文档 (Swagger) | http://localhost:8000/docs | 交互式 API 调试 |
| 地图页面 | http://localhost:8000/map?token=xxx | 需 token 参数 |
| 确认计划 | http://localhost:8000/confirm?token=xxx | 命中原因 + PDF导出 |
| 计划列表 | http://localhost:8000/plans?token=xxx | 需 token 参数 |
| 拜访反馈 | http://localhost:8000/feedback?token=xxx&plan_id=xxx | 需 token + plan_id |

### 默认账号

| 用户名 | 密码 | 角色 |
|--------|------|------|
| admin | admin123 | 管理员（admin） |

---

## 数据库配置

系统依赖两个 PostgreSQL 数据库：

### ts_quant_db（只读 — 私募机构数据来源）

```python
{
    "host": "localhost",
    "port": 5432,
    "dbname": "ts_quant_db",
    "user": "db_query_user",
    "password": "your_password_here",
}
```

核心表：
- `private_fund_list` — 基金管理人摘要信息（地址、规模、省份、产品数等）
- `private_fund_detail` — 基金管理人详情 JSONB（产品列表、高管履历、会员信息等）

**查询注意事项**：
- JSONB 查询需使用 `jsonb_array_elements()` 展开数组，对 NULL 使用 `COALESCE(... , '[]'::jsonb)` 保护
- 已清算产品判断：`products.funds_after[i].investor_open_rate = '基金已清算'`
- Decimal('NaN') 值在 JSON 序列化时需转换为 None（已在 `db_tsquant.py` 中处理）

### fund_map_db（读写 — 业务数据）

```python
{
    "host": "localhost",
    "port": 5432,
    "dbname": "fund_map_db",
    "user": "fund_map_user",
    "password": "your_password_here",
}
```

4 张业务表：

| 表名 | 用途 | 关键字段 |
|------|------|----------|
| `users` | 用户账号 | username, password_hash, display_name, role |
| `visit_cart` | 待拜访清单 | user_id(FK), reg_num, org_name, office_coordinates |
| `visit_plans` | 拜访计划 | user_id(FK), reg_num, planned_date, visitor_name, status |
| `visit_feedback` | 拜访反馈 | visit_plan_id(FK UNIQUE), visit_status, tags, summary |

**注意事项**：
- `visit_cart` 使用 `ON CONFLICT DO NOTHING` 防止重复添加
- `visit_feedback.visit_plan_id` 有 UNIQUE 约束，一个计划只能有一条反馈（支持 UPSERT）
- 删除 `visit_cart` 或 `visit_plans` 记录使用 CASCADE 外键

### 用户创建新账号

通过 API 注册（需要 admin 权限后续可扩展注册页面）：

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"member1","password":"123456","display_name":"张三","role":"member"}'
```

---

## API 端点一览

| 方法 | 路径 | 说明 | 需认证 |
|------|------|------|--------|
| POST | /api/auth/login | 用户登录 | 否 |
| POST | /api/auth/register | 用户注册 | 否 |
| GET | /api/auth/me | 获取当前用户 | 是 |
| GET | /api/filters | 获取筛选选项 | 否 |
| GET | /api/funds | 基金查询 | 否 |
| GET | /api/map-data | 地图数据（含拜访标记） | 否 |
| GET | /api/cart | 获取购物车 | 是 |
| POST | /api/cart/add | 加入购物车 | 是 |
| DELETE | /api/cart/{id} | 删除购物车条目 | 是 |
| DELETE | /api/cart | 清空购物车 | 是 |
| POST | /api/plans/confirm | 购物车→计划确认 | 是 |
| POST | /api/plans/auto-expire | 自动过期7天未反馈计划 | 是 |
| POST | /api/plans/batch-import | 批量补录（仅计划） | 是 |
| POST | /api/plans/batch-import-with-feedback | 批量补录（含反馈） | 是 |
| POST | /api/plans/batch-import-simple | 批量补录（传reg_num自动查询） | 是 |
| POST | /api/match-reasons | 批量查询命中原因（产品名/高管履历） | 否 |
| GET | /api/plans | 获取计划列表 | 是 |
| POST | /api/feedback | 创建/更新反馈 | 是 |
| GET | /api/feedback/{plan_id} | 获取反馈 | 是 |
| GET | /api/history | 历史记录（含反馈） | 是 |
| GET | /api/stats | 统计概览 | 是 |
| GET | /api/visited-info | 已拜访信息（最新1条） | 否 |
| GET | /api/visited-history | 拜访历史（最多5条） | 否 |

---

## 使用流程

1. **登录系统** → 打开 Streamlit (localhost:8501)，使用 admin/admin123 登录
2. **查询筛选** → 在查询页选择条件，点击查询
3. **地图查看** → 点击"在地图上显示"或直接打开地图页面
4. **加入清单** → 在地图标记弹窗中点击"加入待拜访清单"
5. **确认计划** → 在侧滑窗口中点击"进入确认"，查看命中原因，填写日期和拜访人，可**导出PDF**后提交
6. **查看计划** → 在计划列表页查看所有拜访计划
7. **填写反馈** → 拜访完成后，点击计划旁的"填写反馈"
8. **查看历史** → 在 Streamlit 历史页面查看统计和完整记录
9. **批量补录** → 项目上线前已拜访的机构，在补录页搜索添加并补填反馈信息

---

## 注意事项

1. **PostgreSQL 必须提前启动**，两个数据库（ts_quant_db + fund_map_db）需已创建，表结构已就绪
2. **地图页面需要 token 参数**，直接访问 `/map` 会显示空白页。需通过 Streamlit"打开动态地图"按钮或手动拼接 URL：`/map?token=xxx`
3. **Python 版本**推荐 3.10+，bcrypt 库在低版本 Python 上可能编译失败
4. **高德瓦片依赖外网**，国内环境加载流畅，如瓦片加载失败请检查网络
5. **PDF导出**：确认拜访计划页面支持一键导出 PDF（浏览器打印渲染，A4 专业排版），Excel 导出通过 Streamlit 查询页面可用
6. **register API 暂未限制访问**，后续可添加 admin 权限校验
7. `--reload` 模式下修改 HTML 模板会自动生效，修改 Python 文件也会自动重载
8. **地图标记数量**建议控制在 5000 个以内，超过可能出现性能问题
9. **Decimal NaN**：PostgreSQL 的 `paid_capital` 字段可能出现 `NaN` 值，后端已做序列化转换处理
10. **JWT Token 有效期**默认 8 小时，过期需重新登录

---

## Phase 开发状态

| Phase | 内容 | 状态 |
|-------|------|------|
| Phase 1 | 基础设施 + 登录 + 地图动态化 | ✅ 已完成 |
| Phase 2 | 拜访计划工作流（购物车→确认→计划） | ✅ 已完成 |
| Phase 3 | 拜访反馈 + 历史管理 + 统计仪表盘 | ✅ 已完成 |
| 未来 | Docker 部署配置、权限管理增强、数据看板优化 | ⏳ 待定 |

---

## 地图标记颜色方案

| 管理规模 | 颜色 | 色值 |
|----------|------|------|
| 0-5亿元 | 绿色 | #4CAF50 |
| 5-10亿元 | 浅绿 | #8BC34A |
| 10-20亿元 | 黄色 | #FFC107 |
| 20-50亿元 | 橙色 | #FF9800 |
| 50-100亿元 | 红色 | #F44336 |
| 100亿元以上 | 紫色 | #9C27B0 |
| 未披露 | 灰色 | #9E9E9E |

### 拜访状态标记叠加

在管理规模颜色基础上，标记叠加以下修饰表示拜访状态：

| 状态 | 标记样式 | 说明 |
|------|----------|------|
| 未拜访 | 纯AUM色圆点 | 无任何修饰 |
| 待拜访 | AUM色圆点 + ⏳图标 | 有计划但尚未完成拜访 |
| 已拜访 | 灰色圆 + 虚线边框 + ✓ | 至少有一次已完成拜访记录 |

---

## 技术要点记录（供后续优化参考）

### 地图页面的 Token 注入
FastAPI 通过字符串替换方式注入 token（不使用 Jinja2 模板引擎）：
```python
html = html.replace("'{{ token }}'", repr(token_str))  # JS 上下文
html = html.replace("{{ token }}", token_str)           # HTML 上下文
```
原因：Jinja2 与 dict 类型存在兼容性问题（`TypeError: unhashable type: 'dict'`）

### 侧滑面板与地图联动
```css
body.cart-open #map { width: calc(100vw - 400px); }  /* 地图收缩 */
```
```javascript
// 面板切换后强制刷新地图
panel.classList.toggle('open');
document.body.classList.toggle('cart-open');
setTimeout(() => map.invalidateSize(), 350);
```
无遮罩层，侧滑面板与地图可同时交互。

### PostgreSQL Decimal NaN 处理
```python
if isinstance(v, Decimal) and v.is_nan():
    d[k] = None
elif isinstance(v, float) and math.isnan(v):
    d[k] = None
```

### 批量补录的 CHECK 约束兼容
`visit_feedback.visit_status` 字段有 CHECK 约束（仅允许：成功/未见到/已搬迁/地址有误/其他）。批量补录时使用 `visit_status='其他'` + tags 中添加 `'手动补录'` 的方式，而非直接传入 `'其他[手动补录]'`。
