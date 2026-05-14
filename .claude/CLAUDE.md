# Harness Engineering — 私有基金拓客系统

## 验证门禁

所有代码实现后必须自动验证：

```bash
# Python 语法检查
python3 -m py_compile backend/main.py backend/config.py backend/auth_utils.py backend/db_tsquant.py backend/db_fundmap.py
python3 -m py_compile app.py pages/*.py

# 代码风格检查
ruff check backend/ app.py pages/ --line-length=100

# 后端启动验证（检查导入）
python3 -c "from backend import main; print('FastAPI 导入 OK')"
```

## 项目特有约束

- **不修改数据库结构**（4 张业务表已固定：users/visit_cart/visit_plans/visit_feedback）
- **不修改只读查询**（ts_quant_db 的 private_fund_list/private_fund_detail 是只读来源）
- **JSONB 查询保护**：所有 `jsonb_array_elements()` 必须用 `COALESCE(..., '[]'::jsonb)` 包裹
- **Streamlit 页面**：新增页面需在 `pages/` 下创建，登录校验复用 `app.py` 中的模式
- **FastAPI 路由**：新增路由同步在 `backend/templates/` 下添加对应 HTML 模板
- **visit_plans.starred + visit_cart.starred**：`BOOLEAN DEFAULT false`，已有迁移脚本，不做额外修改

## 进度文件

- 多会话任务使用 `HARNESS_PROGRESS.md`
- 单会话任务在会话内通过 TodoWrite 追踪即可

## 强制更新约束

**变更项目代码后，必须同步更新以下两个文件：**

| 文件 | 用途 | 需更新的情况 |
|------|------|-------------|
| `CLAUDE.md` (根目录) | AI 背景层 | 新增 API 路由、修改数据库结构、新增页面 |
| `README.md` | 人类友好层 | 新增功能、修改运行方式、变更架构 |

## 快速启动验证

```bash
# 完整启动验证
bash start.sh

# 或分终端模式
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload  # 终端1
streamlit run app.py --server.port 8501                                    # 终端2
```
