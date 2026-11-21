"""对桥接包中的真实 ODB 应力历程做雨流+损伤计算（pyLife 2.3.1）。

桥接包由 abaqus python 从真实 ODB 提取；本脚本在独立环境计算。
计算前先执行桥接包结构校验（清单/哈希/组合键/缺帧/失效标记/应力基底），
并按 manifest.units 把源应力单位显式换算为 MPa；单位未确认时拒绝计算。
注意：Wöhler 曲线参数必须来自匹配牌号的真实疲劳试验；本脚本读取
--curve 指定的已拟合曲线 JSON（见 fit_sn_curve.py）。没有曲线则拒绝计算，
绝不虚构材料参数。

运行：
  <pyLife>/bin/python fatigue/analyze_real_bundle.py realrun/real_bundle \
      --curve realrun/curve.json --component S11 --out realrun/damage_results
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pylife.stress.rainflow as rainflow
from pylife.materiallaws import WoehlerCurve

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "bridge"))

from bundle_validation import validate_bundle  # noqa: E402


def load_bundle(d: Path) -> tuple[list[dict], pd.DataFrame]:
    m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    pts = list(csv.DictReader(open(d / "points.csv")))
    frames = []
    for f in sorted((d / "fields").glob("*.csv")):
        frames.extend(csv.DictReader(open(f)))
    return m, (pts, pd.DataFrame(frames))


def load_curve(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"缺少已拟合曲线 JSON: {path}")
    c = json.loads(p.read_text(encoding="utf-8"))
    for k in ("k_1", "ND", "SD"):
        if c.get(k) is None:
            raise ValueError(f"曲线缺少参数 {k}；请先拟合真实试验数据")
    return c


def preflight(bundle: Path, component: str, allow_unresolved_basis: bool):
    """返回 (report, problems)。problems 非空即拒绝计算。"""
    report = validate_bundle(bundle, component=component)
    problems: list[str] = []
    if report["errors"]:
        problems.extend(report["errors"])
        return report, problems

    units = report["units"]
    if units.get("stress_scale_to_MPa") is None:
        problems.append(units.get("problem")
                        or "源应力单位未确认；拒绝把未知单位数值当 MPa 计算")
    basis = report["basis"]
    if not basis["resolved"] and basis["shell_section_points"]:
        if not allow_unresolved_basis:
            problems.append(
                "应力基底未解析（local-unresolved）且包含壳/梁截面点；"
                "请在提取端用 --basis global/local 声明，或人工确认后加 "
                "--allow-unresolved-basis")
    # 实体积分点的基底提示已由 validate_bundle 写入 warnings，这里不重复。
    return report, problems


def loop_table(stress: np.ndarray):
    det = rainflow.ThreePointDetector(rainflow.FullRecorder())
    det.process(stress, flush=True)
    loops = det.recorder.collective.copy()
    return det, loops


def annotate_loops(loops: pd.DataFrame, levels: list[float]) -> pd.DataFrame:
    """补充幅值、应力比 R、是否超出曲线试验区间。"""
    loops["amplitude"] = (loops["to"] - loops["from"]).abs() / 2.0
    lo = loops[["from", "to"]].min(axis=1)
    hi = loops[["from", "to"]].max(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        loops["R"] = np.where(np.abs(hi) > 0, lo / hi, np.nan)
    if levels:
        lmin, lmax = min(levels), max(levels)
        loops["below_test_range"] = loops["amplitude"] < lmin
        loops["above_test_range"] = loops["amplitude"] > lmax
    else:
        loops["below_test_range"] = False
        loops["above_test_range"] = False
    return loops


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("bundle")
    ap.add_argument("--curve", required=True)
    ap.add_argument("--component", default="S11")
    ap.add_argument("--out", default="damage_results")
    ap.add_argument("--allow-unresolved-basis", action="store_true",
                    help="仅在人工确认壳/梁截面应力为全局分量时使用")
    args = ap.parse_args(argv)

    curve = load_curve(args.curve)
    bundle = Path(args.bundle)
    report, problems = preflight(bundle, args.component,
                                 args.allow_unresolved_basis)
    if problems:
        print("[拒绝计算] 桥接包未通过前置校验：", file=sys.stderr)
        for p in problems:
            print("  -", p, file=sys.stderr)
        return 2

    units = report["units"]
    scale = units["stress_scale_to_MPa"]
    levels = [float(x) for x in (curve.get("finite_load_levels") or [])]
    wc = WoehlerCurve(pd.Series({
        "k_1": float(curve["k_1"]), "ND": float(curve["ND"]),
        "SD": float(curve["SD"]),
        **({"k_2": float(curve["k_2"])} if curve.get("k_2") else {}),
    }))
    meta, (pts, df) = load_bundle(bundle)
    comp = args.component
    if comp not in df.columns:
        print(f"[拒绝计算] 桥接包无应力分量 {comp}; 实际: "
              f"{[c for c in df.columns]}", file=sys.stderr)
        return 2

    df = df.copy()
    # frame_id 来自 CSV 是字符串，必须按整数排序（'10' < '2' 会打乱历程）。
    df["frame_id"] = pd.to_numeric(df["frame_id"], errors="coerce")

    per_point = []
    det_residuals = 0
    for pid, g in df.groupby("point_id"):
        info = report["points"].get(pid, {})
        if info.get("missing_frames"):
            per_point.append({"point_id": pid, "status": "missing_frames",
                              "n_missing": len(info["missing_frames"])})
            continue
        if info.get("invalid_frames"):
            per_point.append({"point_id": pid, "status": "invalid_frames",
                              "n_invalid": len(info["invalid_frames"])})
            continue
        series = g.sort_values("frame_id")
        stress = (pd.to_numeric(series[comp], errors="coerce")
                  .to_numpy(dtype=float) * scale)
        if not np.isfinite(stress).all():
            # 真实 ODB 出现 NaN/失效：拒绝静默清理，记录并跳过该点。
            per_point.append({"point_id": pid, "status": "skipped_nonfinite",
                              "n_finite": int(np.isfinite(stress).sum())})
            continue
        det, loops = loop_table(stress)
        det_residuals += len(det.residuals)
        if len(loops) == 0:
            per_point.append({"point_id": pid, "status": "no_closed_loop"})
            continue
        loops = annotate_loops(loops, levels)
        loops["Nf"] = wc.basquin_cycles(loops["amplitude"])
        loops["damage"] = 1.0 / loops["Nf"]
        imax = loops["amplitude"].idxmax()
        amp_max = float(loops["amplitude"].max())
        if levels:
            lmin, lmax = min(levels), max(levels)
            coverage = ("below_test_range" if amp_max < lmin
                        else "above_test_range" if amp_max > lmax
                        else "within_test_range")
        else:
            coverage = "curve_range_unknown"
        r_at_max = float(loops.loc[imax, "R"]) if np.isfinite(
            loops.loc[imax, "R"]) else None
        per_point.append({
            "point_id": pid, "status": "ok",
            "closed_loops": int(len(loops)),
            "amplitude_max_MPa": amp_max,
            "amplitude_min_MPa": float(loops["amplitude"].min()),
            "R_at_max_amplitude": r_at_max,
            "R_min": float(np.nanmin(loops["R"])) if np.isfinite(
                np.nanmin(loops["R"])) else None,
            "R_max": float(np.nanmax(loops["R"])) if np.isfinite(
                np.nanmax(loops["R"])) else None,
            "n_loops_below_test_min": int(loops["below_test_range"].sum()),
            "n_loops_above_test_max": int(loops["above_test_range"].sum()),
            "curve_coverage": coverage,
            "damage_sum": float(loops["damage"].sum()),
        })

    res = pd.DataFrame(per_point)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    res.to_csv(out / "per_point.csv", index=False)
    ok = res[res["status"] == "ok"]

    curve_R = curve.get("R")
    r_mismatch = 0
    if curve_R is not None and not ok.empty and "R_at_max_amplitude" in ok:
        finite_r = pd.to_numeric(ok["R_at_max_amplitude"], errors="coerce")
        r_mismatch = int(((finite_r - float(curve_R)).abs() > 0.1).sum())

    below_pts = int((pd.to_numeric(ok.get("n_loops_below_test_min", pd.Series(dtype=int)),
                                   errors="coerce").fillna(0) > 0).sum()) if not ok.empty else 0
    above_pts = int((pd.to_numeric(ok.get("n_loops_above_test_max", pd.Series(dtype=int)),
                                   errors="coerce").fillna(0) > 0).sum()) if not ok.empty else 0
    amp_range = None
    if not ok.empty:
        amp_range = [float(ok["amplitude_max_MPa"].min()),
                     float(ok["amplitude_max_MPa"].max())]

    summary = {
        "schema": "fatigue-analysis-v2",
        "source_odb": meta.get("source"),
        "curve_material": curve.get("material"),
        "curve_source_csv": curve.get("source_csv"),
        "component": comp,
        "units": {
            "stress_source": units["stress_source"],
            "stress_standard": "MPa",
            "stress_scale_to_MPa": scale,
            "time_source": units["time_source"],
            "time_meaning": units["time_meaning"],
        },
        "basis": report["basis"],
        "validation": {
            "passed": report["passed"],
            "checks": report["checks"],
            "warnings": report["warnings"],
        },
        "n_points_total": int(len(res)),
        "n_points_ok": int(len(ok)),
        "n_points_skipped_nonfinite": int((res["status"] == "skipped_nonfinite").sum()),
        "n_points_invalid_frames": int((res["status"] == "invalid_frames").sum()),
        "n_points_missing_frames": int((res["status"] == "missing_frames").sum()),
        "n_points_no_closed_loop": int((res["status"] == "no_closed_loop").sum()),
        "total_residual_turning_points": det_residuals,
        "amplitude_max_range_MPa": amp_range,
        "curve_test_range_MPa": [min(levels), max(levels)] if levels else None,
        "curve_R_reference": curve_R,
        "n_points_below_curve_test_min": below_pts,
        "n_points_above_curve_test_max": above_pts,
        "n_points_R_mismatch": r_mismatch,
        "note": "真实 ODB 应力历程，源单位按 manifest 换算为 MPa；损伤为 Miner 小计，"
                "残余循环未闭合未计入。幅值低于曲线试验下限、或应力比与曲线参考 R "
                "不一致的点属于外推/错配，只能作方法学参考，不能作为零件寿命承诺。",
    }
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    for w in report["warnings"]:
        print("[警告]", w, file=sys.stderr)
    if not ok.empty:
        crit = ok.loc[ok["damage_sum"].idxmax()]
        print("最高损伤材料点:", crit["point_id"], "损伤小计:", crit["damage_sum"],
              "| 幅值:", crit["amplitude_max_MPa"], "MPa",
              "| R:", crit["R_at_max_amplitude"],
              "| 曲线覆盖:", crit["curve_coverage"])
        if levels and (crit["curve_coverage"] != "within_test_range"
                       or (curve_R is not None and crit["R_at_max_amplitude"] is not None
                           and abs(crit["R_at_max_amplitude"] - float(curve_R)) > 0.1)):
            print("[警告] 最高损伤点超出曲线试验区间或应力比不匹配，"
                  "该数值不能作为零件寿命结论。", file=sys.stderr)
    print("结果已写入:", out)
    if len(ok) == 0:
        print("[失败] 没有任何材料点通过校验并完成计算", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
