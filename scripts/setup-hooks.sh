#!/bin/bash
# 安装 Git hooks（克隆仓库后首次执行）
set -e
HOOK_DIR="$(cd "$(dirname "$0")/.." && pwd)/.git/hooks"
echo "安装 pre-push hook..."
cp "$(dirname "$0")/pre-push.sh" "$HOOK_DIR/pre-push"
chmod +x "$HOOK_DIR/pre-push"
echo "完成。推送前会自动运行测试和检查 CHANGELOG。"
