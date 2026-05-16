# 私募基金拓客辅助系统 — AI 背景层

## 项目概述

私募基金团队拓客业务工具。整合数据查询、地图展示、拜访计划、反馈记录为一套多用户协作系统。

**数据来源**：中国证券投资基金业协会（AMAC）官网爬取的私募基金管理人公开数据。

---

## 项目结构

```
private_fund_map/
├── src/                        # 源代码
│   ├── app.py                  # Streamlit 主入口（登录 + 多页面路由）
│   ├── __init__.py
│   ├── pages/                  # Streamlit 页面模块
│   │   ├── __init__.py
│   │   ├── query.py            # 数据查询与导出
│   │   ├── plans.py            # 拜访计划（Streamlit 版）
│   │   ├── history.py          # 拜访历史 + 统计
│   │   ├── batch_detail.py     # 批次详情
│   │   ├── batch_import.py     # 批量补录
│   │   └── settings.py         # 系统设置 + 修改密码
│   └── backend/                # FastAPI 后端
│       ├── __init__.py
│       ├── main.py             # 全部 API 路由 + HTML 页面渲染
│       ├── config.py           # 数据库连接 + JWT 配置
│       ├── auth_utils.py       # JWT 生成/验证 + bcrypt
│       ├── db_admin.py         # 管理员操作
│       ├── db_tsquant.py       # ts_quant_db 只读查询
│       ├── db_fundmap.py       # fund_map_db CRUD
│       ├── static/             # 静态资源
│       │   ├── style.css
│       │   ├── icons.js
│       │   └── icons.svg
│       └── templates/          # HTML 模板
│           ├── map.html
│           ├── batch_map.html
│           ├── batch_detail_print.html
│           ├── confirm.html
│           ├── confirm_del_plan.html
│           ├── plans.html
│           ├── feedback.html
│           └── detail.html
├── config/                     # 项目配置
│   ├── .env                    # 环境变量（已 .gitignore）
│   ├── .env.example            # 环境变量模板
│   └── config.ini.example      # 配置模板
├── docs/                       # 文档
│   └── requirements_doc.md
├── database/                   # 数据库迁移
│   ├── 004_add_super_admin_role.sql
│   └── 005_remove_contact_obtained.sql
├── logs/                       # 运行时日志
├── harness/                    # Harness 流程产物
├── feishu_sync/                # 飞书同步插件
│   ├── __init__.py
│   ├── config.py
│   ├── api.py
│   ├── db.py
│   ├── sync.py
│   ├── scheduler.py
│   ├── log_manager.py
│   └── import_org_dict.py
├── team-work/                  # 多角色协作工作流
├── .streamlit/
│   └── config.toml
├── start.sh                    # 一键启动脚本
├── restart.sh                  # 重启脚本
├── CLAUDE.md                   # AI 背景层（本文件）
├── README.md                   # 人类友好层
└── .claude/
    └── CLAUDE.md               # Harness Engineering 约束
```

---

## 目录结构约定

| 目录 | 用途 |
|------|------|
| `config/` | 项目配置文件 |
| `docs/` | 需求文档、技术文档、用户手册、说明文档 |
| `database/` | SQL 文件、迁移脚本、数据初始化脚本 |
| `logs/` | 运行时日志文件 |
| `harness/` | Harness 流程产物 |
| `src/` | 源代码 |

- 新产生的文件必须按此规则归入对应目录
- 不属于以上分类的放在合理位置即可

---

## 技术架构

```
Streamlit (8501)       FastAPI (8100)        PostgreSQL (5432)
  [登录/查询/表单]         [REST API]           ts_quant_db (只读)
                   ◄──►  [JWT 认证]      ◄──►   private_fund_list
                   ◄──►  [HTML 页面渲染]         private_fund_detail
                                              fund_map_db (读写)
                                                users
                                                visit_cart
                                                visit_plans
                                                visit_feedback
```

| 组件 | 技术 | 版本 |
|------|------|------|
| 前端（查询/表单） | Streamlit | ≥1.28 |
| 前端（地图） | Leaflet + 高德瓦片 | Leaflet 1.9 |
| API 后端 | FastAPI | ≥0.104 |
| 数据库 | PostgreSQL | ≥15 |
| 认证 | JWT (python-jose) + bcrypt | — |

---

## 数据库

### ts_quant_db（只读 — AMAC 公开数据）

| 表 | 说明 |
|----|------|
| `private_fund_list` | 基金管理人摘要信息（拍平表），含坐标、规模等 |
| `private_fund_detail` | 基金管理人详情（JSONB），含产品列表、高管履历 |

**JSONB 关键路径**：`parsed_data->'products'->'funds_after'`（产品数组），`parsed_data->'executives'`（高管数组）。NULL 保护用 `COALESCE(..., '[]'::jsonb)`。

### fund_map_db（读写 — 业务数据）

| 表 | 说明 | 关键字段 |
|----|------|---------|
| `users` | 用户 | username, password_hash, display_name, role |
| `visit_cart` | 待拜访清单 | user_id, reg_num, org_name, org_aum, starred |
| `visit_plans` | 拜访计划 | user_id, batch_id, status, planned_date, visitor_name, starred |
| `visit_feedback` | 拜访反馈 | visit_plan_id (UNIQUE), visit_status, tags |

**角色体系**：`super_admin` → `admin` → `member`

---

## API 路由一览

| 方法 | 路径 | 说明 | 需认证 |
|------|------|------|--------|
| POST | `/api/auth/login` | 登录 | 否 |
| POST | `/api/auth/register` | 注册 | 否 |
| GET | `/api/auth/me` | 当前用户 | 是 |
| PUT | `/api/auth/change-password` | 修改密码 | 是 |
| GET/POST | `/api/admin/users` | 用户管理 | super_admin |
| PUT/DELETE | `/api/admin/users/{id}` | 编辑/删除用户 | super_admin |
| POST | `/api/admin/users/{id}/reset-password` | 重置密码 | super_admin |
| GET/POST | `/api/admin/config` | 系统配置 | super_admin |
| GET | `/api/admin/system-status` | 系统状态 | super_admin |
| POST | `/api/admin/restart` | 重启服务 | super_admin |
| GET | `/api/filters` | 筛选项 | 否 |
| GET | `/api/funds` | 基金查询（8维+分页） | 否 |
| GET | `/api/map-data` | 地图数据 | 否 |
| GET/POST/DELETE | `/api/cart` | 购物车 CRUD | 是 |
| POST | `/api/cart/toggle-star/{id}` | 星标 | 是 |
| GET | `/api/plans` | 计划列表 | 是 |
| POST | `/api/plans/confirm` | 购物车→计划 | 是 |
| DELETE | `/api/plans/{id}` | 删除计划 | 是 |
| DELETE | `/api/plans/batch/{batch_id}` | 删除批次 | 是 |
| POST | `/api/plans/toggle-star/{id}` | 设置星标 | 是 |
| POST | `/api/plans/unstar/{id}` | 取消星标 | 是 |
| POST | `/api/plans/auto-expire` | 自动过期 | 是 |
| POST | `/api/plans/batch-import` | 批量补录计划 | 是 |
| POST | `/api/plans/batch-import-with-feedback` | 批量补录含反馈 | 是 |
| POST | `/api/plans/batch-import-simple` | 批量补录简化 | 是 |
| GET | `/api/feedback/{plan_id}` | 获取反馈 | 是 |
| POST | `/api/feedback` | 保存反馈 | 是 |
| GET | `/api/user-tags` | 用户标签 | 是 |
| GET | `/api/history` | 拜访历史 | 是 |
| GET | `/api/stats` | 统计概览 | 是 |
| GET | `/api/visited-info` | 已拜访信息（最新1条） | 否 |
| GET | `/api/visited-history` | 拜访历史（最多5条） | 否 |
| POST | `/api/fund-links` | 批量查询详情页URL | 否 |
| GET | `/api/fund-profile/{reg_num}` | 机构详情+标签+拜访 | 是 |
| POST | `/api/match-reasons` | 批量查询命中原因 | 否 |
| GET/POST | `/api/admin/feishu/config` | 飞书配置 | super_admin |
| POST | `/api/admin/feishu/sync` | 手动同步 | super_admin |
| POST | `/api/admin/feishu/sync-org-dict` | 同步组织字典 | super_admin |
| GET | `/api/admin/feishu/status` | 同步状态 | super_admin |
| GET/POST | `/api/admin/feishu/auto-sync` | 自动同步配置 | super_admin |
| GET/POST/PUT/DELETE | `/api/admin/feishu/cron-jobs` | 定时任务 | super_admin |
| GET | `/api/admin/feishu/logs` | 同步日志 | super_admin |
| GET | `/map` | 地图页面（Leaflet+高德） | token |
| GET | `/confirm` | 确认拜访计划 | token |
| GET | `/plans` | 计划列表页 | token |
| GET | `/feedback` | 反馈表单页 | token |
| GET | `/detail` | 拜访记录详情 | token |
| GET | `/batch-map` | 批次机构地图 | token |
| GET | `/batch-detail-print` | 批次打印/PDF导出 | token |
| GET | `/confirm-del-plan` | 删除确认 | token |

---

## 运行方式

```bash
# 完整启动
bash start.sh

# 或分终端
python3 -m uvicorn src.backend.main:app --host 0.0.0.0 --port 8100 --reload
streamlit run src/app.py --server.port 8501
```

| 服务 | 地址 |
|------|------|
| Streamlit | http://localhost:8501 |
| FastAPI | http://localhost:8100 |
| Swagger | http://localhost:8100/docs |

| 账号 | 密码 | 角色 |
|------|------|------|
| admin | admin123 | admin |

---

## 编码约定

- **数据库**：不修改表结构，JSONB 查询需 COALESCE 保护
- **HTML 模板**：Token 通过字符串替换注入（`{{ token }}`），不使用 Jinja2
- **地图**：Leaflet + 高德瓦片，标记按 AUM 分色
- **Python**：ruff 检查（line-length=100），不修改 `src/` 以外文件的代码风格
- **飞书配置**：`feishu_sync/feishu_config/config.json` 存储敏感配置，已 .gitignore
- **Streamlit 页面**：在 `src/pages/` 下创建，复用 `st.session_state.token` 鉴权模式
- **后端新路由**：在 `src/backend/main.py` 中添加，Pydantic 定义请求模型
