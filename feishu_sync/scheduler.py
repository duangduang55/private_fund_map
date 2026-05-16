"""飞书同步 crontab 定时任务管理

通过系统 crontab 管理飞书同步的定时执行。
cron 任务定义存储在 feishu_config/config.json 的 cron_jobs 数组中。
crontab 是执行器，config.json 是配置源（唯一事实来源）。
"""

import logging
import subprocess
import sys
from pathlib import Path

from feishu_sync.config import get_cron_jobs, save_cron_jobs

log = logging.getLogger("feishu_sync.scheduler")

# 同步脚本路径
SYNC_DIR = Path(__file__).resolve().parent
SYNC_SCRIPT = SYNC_DIR / "sync.py"

# crontab 标记前缀
CRON_MARKER_PREFIX = "# feishu-sync-cron:"


def _cron_marker(label: str) -> str:
    """生成 cron 任务标记行"""
    return f"{CRON_MARKER_PREFIX}{label}"


def get_current_crontab() -> str:
    """获取当前用户的 crontab 内容"""
    try:
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return result.stdout
        if "no crontab" in result.stderr.lower():
            return ""
        return result.stderr
    except FileNotFoundError:
        log.error("crontab 命令不可用，请确认系统已安装 cron")
        return ""
    except Exception as e:
        log.error(f"读取 crontab 失败: {e}")
        return ""


def set_crontab(content: str) -> bool:
    """设置当前用户的 crontab"""
    try:
        proc = subprocess.run(
            ["crontab"],
            input=content,
            capture_output=True, text=True, timeout=10,
        )
        if proc.returncode != 0:
            log.error(f"设置 crontab 失败: {proc.stderr}")
            return False
        return True
    except FileNotFoundError:
        log.error("crontab 命令不可用")
        return False
    except Exception as e:
        log.error(f"设置 crontab 异常: {e}")
        return False


# ── 核心操作 ──


def sync_crontab() -> bool:
    """将 config.json 中的 cron_jobs 与系统 crontab 完全同步

    1. 移除所有 feishu-sync-cron 标记的旧任务
    2. 从 config.json 读取当前 cron_jobs
    3. 安装所有任务到 crontab
    """
    jobs = get_cron_jobs()
    crontab = get_current_crontab()

    # 移除所有 feishu-sync-cron 标记的旧任务（及其上一行表达式）
    new_lines = []
    skip_next = False
    for line in crontab.splitlines():
        if skip_next:
            skip_next = False
            continue
        if line.strip().startswith(CRON_MARKER_PREFIX):
            skip_next = True
            continue
        new_lines.append(line)

    # 去除末尾空行
    while new_lines and new_lines[-1].strip() == "":
        new_lines.pop()

    # 添加当前任务
    for job in jobs:
        expression = job.get("expression", "").strip()
        label = job.get("label", "").strip()
        if not expression:
            continue
        if not label:
            label = expression  # fallback: 用表达式做标签
        cron_line = f"{expression} cd {SYNC_DIR} && {sys.executable} {SYNC_SCRIPT} >/dev/null 2>&1"
        new_lines.append(cron_line)
        new_lines.append(_cron_marker(label))

    new_lines.append("")  # 结尾空行
    return set_crontab("\n".join(new_lines))


# ── CRUD ──


def list_cron_jobs() -> list[dict]:
    """从 config.json 获取所有 cron 任务"""
    return get_cron_jobs()


def add_cron_job(expression: str, label: str) -> bool:
    """添加一条 cron 任务到 config.json 并同步 crontab"""
    if not expression or not expression.strip():
        log.error("cron 表达式不能为空")
        return False

    jobs = get_cron_jobs()

    # 检查 label 是否已存在
    label_key = label or expression
    for job in jobs:
        if job.get("label") == label_key:
            log.error(f"cron 任务标签已存在: {label_key}")
            return False

    jobs.append({"expression": expression.strip(), "label": label_key})
    if not save_cron_jobs(jobs):
        return False

    return sync_crontab()


def remove_cron_job(label: str) -> bool:
    """从 config.json 移除一条 cron 任务并同步 crontab"""
    if not label:
        return False

    jobs = get_cron_jobs()
    filtered = [j for j in jobs if j.get("label") != label]

    if len(filtered) == len(jobs):
        log.warning(f"未找到 cron 任务: {label}")
        return False

    if not save_cron_jobs(filtered):
        return False

    return sync_crontab()


def update_cron_job(old_label: str, expression: str, new_label: str = "") -> bool:
    """更新一条 cron 任务的表达式和/或标签"""
    jobs = get_cron_jobs()
    found = False
    for job in jobs:
        if job.get("label") == old_label:
            job["expression"] = expression.strip()
            if new_label:
                job["label"] = new_label
            found = True
            break

    if not found:
        log.warning(f"未找到 cron 任务: {old_label}")
        return False

    if not save_cron_jobs(jobs):
        return False

    return sync_crontab()


# ── 兼容旧版 API ──


def get_sync_schedule() -> str | None:
    """获取当前 crontab 中的第一条同步调度表达式（兼容旧版）"""
    crontab = get_current_crontab()
    for line in crontab.splitlines():
        if line.strip().startswith(CRON_MARKER_PREFIX):
            lines = crontab.splitlines()
            idx = lines.index(line)
            if idx > 0:
                return lines[idx - 1].strip()
    return None


def install_cron(expression: str = "*/30 * * * *") -> bool:
    """安装 crontab 定时同步任务（兼容旧版：自动添加第一条）"""
    jobs = get_cron_jobs()
    label = f"auto-{expression.replace(' ', '-')}"
    # 检查是否已存在相同标签
    for job in jobs:
        if job.get("label") == label:
            log.info(f"cron 任务已存在: {label}")
            return sync_crontab()  # 重新同步以确保生效
    # 添加新任务
    return add_cron_job(expression, label)


def uninstall_cron() -> bool:
    """卸载所有 crontab 定时同步任务（兼容旧版）"""
    jobs = get_cron_jobs()
    if not jobs:
        return sync_crontab()  # 清空 crontab 中所有 feishu 任务
    if not save_cron_jobs([]):
        return False
    return sync_crontab()


def get_cron_status() -> dict:
    """获取 crontab 状态（兼容旧版）"""
    expression = get_sync_schedule()
    installed = expression is not None

    # 读取最近日志
    last_log = None
    try:
        from feishu_sync.log_manager import list_log_files, tail_log
        files = list_log_files()
        if files:
            last_log = tail_log(files[0], n=5)
    except Exception:
        pass

    return {
        "installed": installed,
        "expression": expression,
        "last_log": last_log,
    }
