#!/bin/bash
# 私募基金拓客辅助系统 — 重启脚本
# 委托给 start.sh（start.sh 已内置杀旧进程逻辑）

cd "$(dirname "$0")"
exec bash start.sh
