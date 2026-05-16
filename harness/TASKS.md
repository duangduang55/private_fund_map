# Implementation Plan: 飞书同步配置管理

## Overview

在 `feishu_sync/` 模块内实现配置参数 JSON 文件管理、自动/定时同步 CRUD、日志文件管理，并通过 Web UI 提供全生命周期管理能力。模块保持自包含，可整体打包复用。

## Architecture Decisions

- **配置存储：** `feishu_config/config.json` 使用 `_comment_` 前缀 key 存放中文释义，Python json 自然保留
- **向后兼容：** 保持 `config.env` 可读，但写操作只写 JSON
- **cron 数据源：** config.json 的 `cron_jobs` 数组为唯一事实来源，crontab 由其同步生成
- **日志轮转：** 使用 `logging.handlers.TimedRotatingFileHandler` 按天切分，不引入第三方库
- **后台线程：** FastAPI startup 事件启动 `threading.Thread` daemon，不引入 Celery/APScheduler

## Task List

### Phase 1: Foundation

#### Task 1: 创建 feishu_config/ 目录 + JSON 配置管理

**Description:** 新建 `feishu_sync/feishu_config/` 目录，创建 `config.json.example` 模板，从现有 `config.env` 迁移初始配置到 JSON。更新 `feishu_sync/config.py` 支持 JSON 读写。

**Acceptance criteria:**
- [ ] `feishu_config/config.json.example` 存在，含中文注释 key 和占位值，无敏感信息
- [ ] `feishu_config/` 加入 `.gitignore`
- [ ] `config.py.load_config()` 优先读 JSON，fallback 到 config.env
- [ ] `config.py.save_to_json()` 正确写 JSON 文件，保留注释 key
- [ ] `config.py.get_all_config_json()` 返回含 cron_jobs 的完整配置对象
- [ ] 测试：Python 语法检查通过

**Verification:**
- [ ] `python3 -m py_compile feishu_sync/config.py`

**Dependencies:** None

**Files:**
- `feishu_sync/feishu_config/config.json.example` (新)
- `feishu_sync/feishu_config/config.json` (新，自动生成)
- `feishu_sync/config.py` (改)
- `.gitignore` (改)

---

#### Task 2: 创建 log_manager.py + 更新 sync.py 日志

**Description:** 创建 `feishu_sync/log_manager.py`，提供日志文件按天切分、列表查看、tail 读取、自动清理功能。更新 `sync.py` 使用新的日志系统，输出到 `feishu_sync/logs/feishu_sync_日期.log`。

**Acceptance criteria:**
- [ ] `log_manager.get_sync_logger()` 返回 logger，输出到 `logs/feishu_sync_YYYYMMDD.log`
- [ ] `log_manager.list_log_files()` 返回日志文件列表（按日期降序）
- [ ] `log_manager.tail_log(filename, n=10)` 返回文件末尾 N 行
- [ ] `log_manager.cleanup_old_logs(days=10)` 删除超期日志
- [ ] `sync.py` 使用新 logger，日志输出到 logs/ 目录
- [ ] `scheduler.py` 日志也走新 logger（如果直接使用 logging.getLogger）

**Verification:**
- [ ] `python3 -m py_compile feishu_sync/log_manager.py feishu_sync/sync.py`
- [ ] 运行同步，确认 `feishu_sync/logs/` 下生成日期日志文件

**Dependencies:** Task 1

**Files:**
- `feishu_sync/log_manager.py` (新)
- `feishu_sync/sync.py` (改)
- `feishu_sync/logs/.gitkeep` (新)

---

#### Task 3: 更新 scheduler.py 支持多条 cron 任务 CRUD

**Description:** 改造 `feishu_sync/scheduler.py`，支持多条 cron 任务的增删改查。cron 任务定义存储在 config.json 的 `cron_jobs` 数组中，scheduler 操作 crontab 与之同步。

**Acceptance criteria:**
- [ ] `list_cron_jobs()` 从 config.json 读取并返回 cron_jobs 列表
- [ ] `add_cron_job(expression, label)` 添加到 config.json 并安装到 crontab
- [ ] `remove_cron_job(label)` 从 config.json 和 crontab 删除
- [ ] `update_cron_job(old_label, expression, new_label)` 更新
- [ ] `sync_crontab()` 将 config.json 的 cron_jobs 与 crontab 完全同步
- [ ] crontab 使用 `# feishu-sync-cron:{label}` 标记区分不同任务

**Verification:**
- [ ] `python3 -m py_compile feishu_sync/scheduler.py`
- [ ] 无法直接运行测试（crontab 操作需要权限），代码审查确认正确性

**Dependencies:** Task 1 (需要 config.json 读写)

**Files:**
- `feishu_sync/scheduler.py` (改)

---

### Phase 2: Backend Features

#### Task 4: 后端 API — 新增自动同步、cron CRUD、日志管理路由

**Description:** 在 `backend/main.py` 新增 API 路由：
- `GET/POST /api/admin/feishu/auto-sync` — 自动同步配置
- `GET/POST/DELETE/PUT /api/admin/feishu/cron-jobs` — 定时同步 CRUD
- `GET /api/admin/feishu/logs` — 日志文件列表/内容

同时更新现有 `GET /api/admin/feishu/config` 和 `POST /api/admin/feishu/config` 以使用新的 JSON 配置。

**Acceptance criteria:**
- [ ] 新增 `FeishuAutoSyncRequest` / `FeishuCronJobRequest` / `FeishuLogRequest` Pydantic 模型
- [ ] auto-sync API 可读写自动同步间隔
- [ ] cron-jobs API 支持增删改查
- [ ] logs API 支持列出文件和读取内容（tail）
- [ ] 所有新 API 需要 `require_super_admin` 权限
- [ ] 现有 feishu/config 和 feishu/status API 正常工作

**Verification:**
- [ ] `python3 -m py_compile backend/main.py`
- [ ] `ruff check backend/main.py --line-length=100`

**Dependencies:** Task 1, Task 2, Task 3

**Files:**
- `backend/main.py` (改)

---

#### Task 5: 自动同步后台线程

**Description:** 在 `backend/main.py` 添加 FastAPI startup 事件，启动后台线程 `auto_sync_worker`。线程按 `FEISHU_SYNC_INTERVAL_MINUTES` 间隔执行同步，可通过 API 动态调整。间隔为 0 时停止执行。

**Acceptance criteria:**
- [ ] 应用启动时根据 config.json 间隔启动后台线程
- [ ] 线程 daemon=True，不阻塞主进程退出
- [ ] 调用 `feishu_sync.sync.sync_once()` 执行同步
- [ ] 使用 log_manager 的 logger 记录线程活动日志
- [ ] 通过 auto-sync API 可动态启停或修改间隔
- [ ] 线程异常不会导致应用崩溃（try/except 包裹）

**Verification:**
- [ ] `python3 -c "from backend.main import app; print('OK')"` # 验证导入
- [ ] 启动后端，观察日志确认线程启动

**Dependencies:** Task 4 (API routes), Task 2 (log_manager)

**Files:**
- `backend/main.py` (改)

---

### Phase 3: Frontend

#### Task 6: Streamlit UI 更新

**Description:** 更新 `pages/settings.py` 的 `_show_feishu_sync()` 函数：
- 区域 1：飞书同步配置表单（保留，支持 JSON 读写）
- 区域 2：飞书同步执行 — 手动同步 + 自动同步间隔 + 定时同步 CRUD 表格+表单
- 区域 3：最近同步日志 — tail 展示 + 日志文件选择器

**Acceptance criteria:**
- [ ] 配置表单正常显示并保存到 JSON
- [ ] 手动同步按钮正常工作
- [ ] 自动同步开关+间隔输入可设置
- [ ] 定时同步列表表格显示所有 cron 任务
- [ ] 可添加/删除 cron 任务
- [ ] 最近同步日志显示 tail=10 行
- [ ] 日志文件下拉框可切换查看不同日志
- [ ] 所有操作有 loading/成功/错误反馈

**Verification:**
- [ ] `python3 -m py_compile pages/settings.py`
- [ ] `ruff check pages/settings.py --line-length=100`

**Dependencies:** Task 4, Task 5

**Files:**
- `pages/settings.py` (改)

---

## Checkpoints

### Checkpoint 1: After Phase 1 (Tasks 1-3)
- [ ] `python3 -m py_compile feishu_sync/config.py feishu_sync/log_manager.py feishu_sync/sync.py feishu_sync/scheduler.py`
- [ ] `ruff check feishu_sync/ --line-length=100`
- [ ] config.json 可正常读写
- [ ] 日志可正常写入 logs/ 目录

### Checkpoint 2: After Phase 2 (Tasks 4-5)
- [ ] `python3 -c "from backend.main import app; print('OK')"`
- [ ] `ruff check backend/main.py --line-length=100`
- [ ] 后端可启动，API 可调用

### Checkpoint 3: After Phase 3 (Task 6)
- [ ] `ruff check pages/settings.py --line-length=100`
- [ ] `python3 -m py_compile pages/settings.py`
- [ ] 完整启动验证：`bash start.sh`

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| crontab 命令不可用（Docker/no root） | 定时同步不可用 | API 返回清晰错误信息，不影响其他功能 |
| JSON 文件并发写入冲突 | 配置丢失 | 操作频率极低（人工操作），暂不加锁 |
| 后台线程异常终止 | 自动同步停摆 | try/except 包裹，线程内捕获所有异常 |

## Open Questions

- 自动同步的"开关"设计：用 `enabled: bool` 还是 `interval=0 表示关闭`？→ 暂用 `interval=0 表示关闭`，简单统一
- 日志文件自动清理时机：每次查看日志列表时清理，还是后台定时清理？→ 每次查看日志列表和每次同步完成时清理，够用
