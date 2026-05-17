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

# 2. 检查 CHANGELOG.md 是否被修改
if ! git diff --cached --name-only HEAD 2>/dev/null | grep -q "CHANGELOG.md"; then
    echo ""
    echo "  ⚠ 提醒: 本次推送未修改 CHANGELOG.md，别忘了记录更新内容。"
fi

echo ""
echo "检查通过，正在推送..."
