#!/usr/bin/env bash
# mcd-skills 一键安装脚本（麦麦 Skill 全家桶）
#
# 全部安装：
#   curl -fsSL https://zhaojjjjjj.github.io/mcd-skills/install.sh | bash
# 只装某一个：
#   curl -fsSL https://zhaojjjjjj.github.io/mcd-skills/install.sh | bash -s -- --only mcd-lottery-ev
#
# Windows 用户请在 Git Bash 里运行。
set -euo pipefail

REPO="Zhaojjjjjj/mcd-skills"
TARBALL="https://github.com/${REPO}/archive/refs/heads/main.tar.gz"
DEST="${WORKBUDDY_SKILLS_DIR:-$HOME/.workbuddy/skills}"
ONLY=""

while [ $# -gt 0 ]; do
  case "$1" in
    --only) ONLY="${2:-}"; shift 2 ;;
    -h|--help)
      echo "用法: bash install.sh [--only <skill名>]"
      echo "可选 skill: mcd-points-guardian mcd-fitmeal mcd-party-buddy mcd-lottery-ev"
      exit 0 ;;
    *) shift ;;
  esac
done

ALL_SKILLS="mcd-points-guardian mcd-fitmeal mcd-party-buddy mcd-lottery-ev"
SKILLS="${ONLY:-$ALL_SKILLS}"

command -v curl >/dev/null 2>&1 || { echo "❌ 需要 curl，请先安装"; exit 1; }
command -v tar >/dev/null 2>&1 || { echo "❌ 需要 tar，请先安装"; exit 1; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "⬇ 正在下载 mcd-skills ..."
curl -fsSL "$TARBALL" -o "$TMP/skills.tar.gz"
tar -xzf "$TMP/skills.tar.gz" -C "$TMP"
SRC="$TMP/mcd-skills-main/skills"

mkdir -p "$DEST"
ok=0
for s in $SKILLS; do
  if [ ! -f "$SRC/$s/SKILL.md" ]; then
    echo "⚠️  未找到 Skill：$s，已跳过"
    continue
  fi
  rm -rf "$DEST/$s"
  cp -r "$SRC/$s" "$DEST/$s"
  echo "✅ 已安装 $s → $DEST/$s"
  ok=$((ok+1))
done

echo ""
if [ "$ok" -gt 0 ]; then
  echo "🎉 安装完成（$ok 个 Skill）！"
  echo ""
  echo "下一步（只需做一次）："
  echo "  1. 打开 https://open.mcd.cn/mcp 申请 MCP Token（手机号登录 → 控制台 → 激活）"
  echo "  2. 在你的 MCP Client 里配好 https://mcp.mcd.cn（Streamable HTTP，Authorization: Bearer <Token>）"
  echo "  3. 直接对 Agent 说话，比如：\"我 3000 积分快过期了，帮我看看怎么换最划算\""
  echo ""
  echo "详细接入说明：https://github.com/Zhaojjjjjj/mcd-skills/blob/main/MCP_INTEGRATION.md"
else
  echo "❌ 没有安装任何 Skill，请检查 skill 名是否正确"
  exit 1
fi
