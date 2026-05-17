#!/bin/bash
# 推送前自动运行测试 + 检查更新记录
echo ""
echo "=================================="
echo "  推送前检查"
echo "=================================="

# 1. 跑测试
python -W ignore run_tests.py
if [ $? -ne 0 ]; then
    echo ""
    echo "测试未通过，推送已取消。请修复后重试。"
    exit 1
fi

# 2. 检查 CHANGELOG.md 是否在最新 commit 中被修改
changed=$(git diff --name-only HEAD~1 2>/dev/null | grep "CHANGELOG.md")
if [ -z "$changed" ]; then
    echo ""
    echo "  ⚠ 提醒: 本次 commit 未修改 CHANGELOG.md"
    echo "     请把改动总结写到 Unreleased 区（不要只写一句'修复bug'）"
fi

echo ""
echo "检查通过，正在推送..."
