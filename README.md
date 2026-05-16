# 私募基金拓客辅助系统

私募基金团队拓客业务工具。整合数据查询、地图展示、拜访计划、反馈记录为一套多用户协作系统。

---

## 快速开始

### 环境要求

- **Python** ≥ 3.10
- **PostgreSQL** ≥ 15（需同时存在 `ts_quant_db` 和 `fund_map_db` 两个数据库）

### 安装与启动

```bash
# 1. 配置环境变量
cp config/.env.example config/.env
# 编辑 config/.env，填入数据库连接信息

# 2. 一键启动
bash start.sh
```

或分终端启动：

```bash
# 终端1 — FastAPI 后端（端口 8100）
python3 -m uvicorn src.backend.main:app --host 0.0.0.0 --port 8100 --reload

# 终端2 — Streamlit 前端（端口 8501）
streamlit run src/app.py --server.port 8501
```

### 访问地址

| 服务 | 地址 | 说明 |
|------|------|------|
| Streamlit 主界面 | http://localhost:8501 | 登录 → 查询 → 计划 → 历史 |
| FastAPI API | http://localhost:8100 | REST API |
| API 文档 (Swagger) | http://localhost:8100/docs | 交互式 API 调试 |
| 地图页面 | http://localhost:8100/map?token=xxx | 全国私募分布 |

### 默认账号

| 用户名 | 密码 | 角色 |
|--------|------|------|
| admin | admin123 | 管理员（admin） |

---

## 技术栈

| 组件 | 技术 | 版本 |
|------|------|------|
| 前端（查询/表单） | Streamlit | ≥1.28 |
| 前端（地图） | Leaflet + 高德瓦片 | Leaflet 1.9 |
| API 后端 | FastAPI | ≥0.104 |
| 数据库 | PostgreSQL | ≥15 |
| 认证 | JWT (python-jose) + bcrypt | — |

---

## 项目结构

```
private_fund_map/
├── src/                   # 源代码
│   ├── app.py             # Streamlit 主入口
│   ├── pages/             # Streamlit 页面模块
│   └── backend/           # FastAPI 后端
├── config/                # 项目配置
├── docs/                  # 文档
├── database/              # SQL 迁移脚本
├── logs/                  # 运行时日志
├── harness/               # Harness 流程产物
├── feishu_sync/           # 飞书同步插件
├── start.sh               # 一键启动脚本
└── README.md              # 本文件
```

---

## 使用流程

1. **登录** → Streamlit 界面使用 admin/admin123 登录
2. **查询筛选** → 选择条件查询私募机构
3. **地图查看** → 查看全国私募分布，点击标记查看详情
4. **加入清单** → 在地图中将目标机构加入待拜访清单
5. **确认计划** → 填写日期和拜访人，导出 PDF
6. **拜访反馈** → 拜访完成后填写反馈信息
7. **查看历史** → 统计概览和完整拜访记录

---

## 注意事项

1. PostgreSQL 必须提前启动，两个数据库需已创建
2. 地图页面需要 token 参数
3. 高德瓦片依赖外网，国内环境加载流畅
4. PDF 导出使用浏览器打印渲染（Ctrl+P / Cmd+P）
5. JWT Token 默认 8 小时有效
