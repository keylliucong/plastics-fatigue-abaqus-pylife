#!/usr/bin/env bash
# 一条命令跑通合成端到端流程：生成桥接包 → 逐点损伤 → 独立重读核对。
# 仅合成数据，不代表真实 Abaqus / 真实 ODB / 真实材料寿命。
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO"

PY="${PYLIFE_PYTHON:-/Users/liucong/Documents/Codex/2026-11-15/abaqus-pylife-pc-abs/work/pylife-check/bin/python}"
if [ ! -x "$PY" ]; then
  echo "未找到 pyLife 2.3.1 解释器：$PY" >&2
  echo "请设置环境变量 PYLIFE_PYTHON 指向已安装 pyLife 2.3.1 的 python。" >&2
  exit 2
fi

echo "== 1/2 生成合成桥接包并计算逐点损伤 =="
"$PY" fatigue/pipeline.py

echo "== 2/2 独立进程重读桥接包并核对 =="
"$PY" fatigue/bridge_adapter.py results/synthetic_pipeline/bridge_bundle

echo "合成端到端流程通过（数据契约、雨流、Wöhler/Miner、独立重读一致）。"
echo "注意：全部为合成演示，不含真实 ODB / 材料 / 零件寿命。"
