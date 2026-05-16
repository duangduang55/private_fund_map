"""飞书同步日志文件管理

提供按天切分的日志记录、文件列表查看、tail 读取、自动清理。
"""

import datetime
import logging
import re
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent / "logs"

# ── Logger 管理 ──

_logger = None
_current_log_date = None
_console_handler_added = False


def get_sync_logger() -> logging.Logger:
    """获取配置好的同步日志 Logger（按天切分，日志输出到 logs/ 目录）"""
    global _logger, _current_log_date, _console_handler_added

    today = datetime.date.today()

    if _logger is not None and today == _current_log_date:
        return _logger

    # 创建新 logger（日期变更或首次初始化）
    _logger = logging.getLogger("feishu_sync")
    _logger.handlers.clear()
    _logger.setLevel(logging.INFO)
    _logger.propagate = False  # 防止重复到根 logger

    # 文件 handler（按天）
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"feishu_sync_{today.strftime('%Y%m%d')}.log"
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    ))
    _logger.addHandler(fh)

    # 控制台 handler（仅首次添加）
    if not _console_handler_added:
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%H:%M:%S",
        ))
        _logger.addHandler(ch)
        _console_handler_added = True

    _current_log_date = today
    return _logger


# ── 文件管理 ──


_LOG_PATTERN = re.compile(r"^feishu_sync_(\d{8})\.log$")


def list_log_files() -> list[str]:
    """列出 logs/ 目录下的所有日志文件（按日期降序）"""
    if not LOG_DIR.exists():
        return []
    files = []
    for f in sorted(LOG_DIR.glob("feishu_sync_*.log"), reverse=True):
        if _LOG_PATTERN.match(f.name):
            files.append(f.name)
    return files


def tail_log(filename: str, n: int = 10) -> str:
    """读取指定日志文件的末尾 N 行（去空行）"""
    log_path = LOG_DIR / filename
    if not log_path.exists():
        return f"日志文件不存在: {filename}"
    try:
        with open(log_path, encoding="utf-8") as f:
            lines = f.readlines()
        tail = [ln.strip() for ln in lines[-n:] if ln.strip()]
        return "\n".join(tail) if tail else "(空)"
    except Exception as e:
        return f"读取日志失败: {e}"


def cleanup_old_logs(days: int = 10):
    """删除超过指定天数的日志文件"""
    if not LOG_DIR.exists():
        return
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    for f in LOG_DIR.glob("feishu_sync_*.log"):
        m = _LOG_PATTERN.match(f.name)
        if not m:
            continue
        try:
            file_date = datetime.datetime.strptime(m.group(1), "%Y%m%d")
            if file_date < cutoff:
                f.unlink()
        except (ValueError, OSError):
            pass
