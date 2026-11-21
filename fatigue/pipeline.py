"""端到端疲劳流程演练（纯合成数据）。

目的：在没有 Windows / Abaqus 2024 / 真实 ODB / 真实材料数据的本机环境，
按项目 SOP 的数据契约把整条计算链跑通一次，验证接口、单位与算术链路。

本脚本 **不是** 真实零件寿命结果：
  - 应力历程是人工合成的有符号单轴序列，不代表任何 Abaqus ODB 输出；
  - Wöhler 参数是虚构的教学参数，不代表 PC/ABS 或任何真实材料；
  - 未调用 Abaqus、未读取 ODB、未拟合试验、未Mean应力/温度/频率修正；
  - 残余循环未闭合、不计入总损伤；不声称完整寿命或可信预测。

运行：
  <pylife-check>/bin/python fatigue/pipeline.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pylife.stress.rainflow as rainflow
from pylife.materiallaws import WoehlerCurve

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OUT = REPO / "results" / "synthetic_pipeline"
DISCLAIMER = (
    "SYNTHETIC DEMONSTRATION ONLY — 合成应力历程与虚构 Wöhler 参数，"
    "未读取真实 ODB、未拟合真实材料、未做均值/温度/频率修正，"
    "不构成任何零件的真实寿命预测或验证结果。"
)


# ---------------------------------------------------------------------------
# 1. 合成“桥接包”：模拟由 ODB 提取后、符合 PRD v1 数据契约的材料点历程
# ---------------------------------------------------------------------------
def build_synthetic_bundle() -> dict:
    """生成一个最小但完整的合成桥接包（内存对象）。

    包含 1 个实体积分点与 1 个壳截面点（两个截面点），体现
    PRD 要求的材料点键唯一性与壳截面点不合并原则。
    """
    # 统一单轴有符号应力（MPa）。三个材料点共用同一段合成历程，便于手算核对。
    # 该序列与 pylife_synthetic_check.py 一致：两个闭合循环 + 未闭合残余。
    stress = [0.0, 10.0, -10.0, 10.0, -10.0, 10.0, -10.0, 0.0]
    frames = list(range(len(stress)))
    step_time = [float(i) for i in frames]  # 源时间单位：秒（合成）

    points = [
        {
            "point_id": "P-1::3::1::",
            "instance": "P-1", "element_label": 3, "integration_point": 1,
            "section_point_number": None, "section_point_description": None,
            "element_type": "C3D8R", "output_position": "INTEGRATION_POINT",
        },
        {
            "point_id": "S-1::7::1::SP1",
            "instance": "S-1", "element_label": 7, "integration_point": 1,
            "section_point_number": 1, "section_point_description": "SHELL TOP SURFACE",
            "element_type": "S4R", "output_position": "INTEGRATION_POINT",
        },
        {
            "point_id": "S-1::7::1::SP2",
            "instance": "S-1", "element_label": 7, "integration_point": 1,
            "section_point_number": 2, "section_point_description": "SHELL BOTTOM SURFACE",
            "element_type": "S4R", "output_position": "INTEGRATION_POINT",
        },
    ]

    fields = []
    for pt in points:
        for f, s, t in zip(frames, stress, step_time):
            fields.append({
                "point_id": pt["point_id"], "frame_id": f, "step_time_s": t,
                "S11_MPa": s,  # 直接以标准化应力保存；源单位确认见 manifest
                "valid": True,
            })

    manifest = {
        "schema": "bridge-bundle-v1-synthetic",
        "source": "synthetic://not-an-odb",
        "disclaimer": DISCLAIMER,
        "units": {"stress_source": "MPa", "stress_standard": "MPa",
                  "time_source": "s", "time_meaning": "物理时间(合成)"},
        "step": "Step-1", "step_domain": "TIME",
        "n_points": len(points), "n_frames": len(frames),
        "n_field_rows": len(fields),
        "stress_component": "S11",
    }
    # 虚构的教学 Wöhler 参数（非任何真实材料）。
    fatigue = {
        "material": "SYNTHETIC-TEACHING",
        "curve": {"k_1": 5.0, "ND": 1e6, "SD": 10.0, "k_2": 5.0},
        "stress_definition": "幅值", "R_reference": -1.0,
        "note": "虚构参数，仅验证 k1/低幅段/单位算术，不可用于设计。",
    }
    return {"manifest": manifest, "points": points, "fields": fields,
            "fatigue": fatigue}


# ---------------------------------------------------------------------------
# 2. 数据契约校验（对应 PRD FR-04/FR-05/FR-07 与本征检查）
# ---------------------------------------------------------------------------
def validate_bundle(b: dict) -> dict:
    checks: dict[str, object] = {}
    m, pts, rows = b["manifest"], b["points"], b["fields"]

    ids = [p["point_id"] for p in pts]
    checks["point_id_unique"] = len(ids) == len(set(ids))

    df = pd.DataFrame(rows)
    expected = m["n_points"] * m["n_frames"]
    checks["row_count_matches"] = len(df) == expected == m["n_field_rows"]

    checks["all_stress_finite"] = bool(np.isfinite(df["S11_MPa"].to_numpy()).all())

    ordered = True
    for pid, g in df.groupby("point_id"):
        if not g["step_time_s"].is_monotonic_increasing:
            ordered = False
        if g["frame_id"].nunique() != m["n_frames"]:
            ordered = False
    checks["frames_ordered_and_complete"] = ordered
    checks["at_least_two_instants"] = m["n_frames"] >= 2

    checks["units_confirmed"] = (
        m["units"]["stress_standard"] == "MPa" and m["units"]["time_source"] == "s"
    )
    checks["shell_section_points_preserved"] = any(
        p["section_point_number"] is not None for p in pts
    ) and any(p["section_point_number"] is None for p in pts)

    failed = [k for k, v in checks.items() if v is not True]
    checks["passed"] = not failed
    checks["failed"] = failed
    return checks


# ---------------------------------------------------------------------------
# 3. 疲劳链路：逐点雨流 → 虚构 Wöhler → Miner 损伤 → 寿命/场映射
# ---------------------------------------------------------------------------
def compute_fatigue(b: dict) -> tuple[pd.DataFrame, dict]:
    params = b["fatigue"]["curve"]
    curve = WoehlerCurve(pd.Series(params))

    loop_rows = []
    for pt in b["points"]:
        pid = pt["point_id"]
        series = (pd.DataFrame(b["fields"])
                  .query("point_id == @pid")
                  .sort_values("frame_id"))
        stress = series["S11_MPa"].to_numpy()

        det = rainflow.ThreePointDetector(rainflow.FullRecorder())
        det.process(stress, flush=True)
        loops = det.recorder.collective.copy()
        loops["amplitude_MPa"] = (loops["to"] - loops["from"]).abs() / 2.0
        loops["mean_MPa"] = (loops["to"] + loops["from"]) / 2.0
        loops["point_id"] = pid
        loops["Nf_synthetic"] = curve.basquin_cycles(loops["amplitude_MPa"])
        loops["damage_closed"] = 1.0 / loops["Nf_synthetic"]
        loop_rows.append(loops)

    all_loops = pd.concat(loop_rows, ignore_index=True) if loop_rows else pd.DataFrame()

    per_point = (all_loops.groupby("point_id")
                 .agg(closed_loops=("amplitude_MPa", "size"),
                      damage_closed=("damage_closed", "sum"))
                 .reset_index())
    per_point["cycles_to_failure_synthetic"] = 1.0 / per_point["damage_closed"]
    # 谱块时长（合成）：128 帧视为 1 个谱块；块寿命 = 失效循环数 / 每块循环数。
    # 每块含 2 个闭合循环，故 block_life = cycles_to_failure / 2。
    per_point["cycles_per_block"] = 2.0
    per_point["blocks_to_failure_synthetic"] = (
        per_point["cycles_to_failure_synthetic"] / per_point["cycles_per_block"]
    )

    critical = per_point.loc[per_point["damage_closed"].idxmax(), "point_id"]
    summary = {
        "disclaimer": DISCLAIMER,
        "curve_params": params,
        "closed_loops_total": int(len(all_loops)),
        "critical_point": critical,
        "residuals_excluded": True,
        "note": "残余循环未闭合、未计入损伤；无真实材料/零件寿命含义。",
    }
    return per_point, summary


# ---------------------------------------------------------------------------
# 4. 手算核对：保证雨流与损伤算术链路可追溯
# ---------------------------------------------------------------------------
def self_test(per_point: pd.DataFrame) -> dict:
    checks: dict[str, object] = {}
    # 合成历程每个材料点应得到 2 个闭合循环，幅值均为 10 MPa。
    checks["two_closed_loops_per_point"] = bool((per_point["closed_loops"] == 2).all())
    # k1=5, SD=10, ND=1e6：10 MPa 恰为参考点，basquin_cycles=1e6。
    checks["Nf_10MPa_is_1e6"] = bool(np.isclose(1.0 / (per_point["damage_closed"] / 2.0), 1e6).all())
    # 每点损伤 = 2/1e6 = 2e-6。
    checks["damage_per_point_2e-6"] = bool(np.allclose(per_point["damage_closed"], 2e-6))
    checks["blocks_to_failure_2p5e5"] = bool(np.allclose(per_point["blocks_to_failure_synthetic"], 2.5e5))
    checks["passed"] = all(v is True for k, v in checks.items() if k != "passed")
    return checks


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    b = build_synthetic_bundle()
    v = validate_bundle(b)
    per_point, summary = compute_fatigue(b)
    t = self_test(per_point)

    if not v["passed"]:
        raise RuntimeError(f"数据契约校验失败: {v['failed']}")
    if not t["passed"]:
        raise RuntimeError(f"手算核对失败: {t}")

    # 持久化结果（均为合成演示）。
    per_point.to_csv(OUT / "per_point_damage.csv", index=False)
    (OUT / "validation.json").write_text(
        json.dumps({"contract": v, "self_test": t, "summary": summary},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "manifest.json").write_text(
        json.dumps(b["manifest"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "README.md").write_text(
        "# 合成流程演练结果\n\n" + DISCLAIMER + "\n\n"
        "本目录由 `fatigue/pipeline.py` 生成，仅验证整条计算链的接口、单位与算术；"
        "不含真实 ODB、真实材料试验或可信寿命。\n",
        encoding="utf-8")

    print("=== 合成端到端流程演练 ===")
    print(DISCLAIMER)
    print("数据契约校验:", {k: v[k] for k in v if k != "failed"})
    print("手算核对:", t)
    print("逐点损伤:")
    print(per_point.to_string(index=False))
    print("关键材料点:", summary["critical_point"])
    print("结果已写入:", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
