"""对桥接包中的真实 ODB 应力历程做雨流+损伤计算（pyLife 2.3.1）。

桥接包由 abaqus python 从真实 ODB 提取；本脚本在独立环境计算。
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
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import pylife.stress.rainflow as rainflow
from pylife.materiallaws import WoehlerCurve


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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("bundle")
    ap.add_argument("--curve", required=True)
    ap.add_argument("--component", default="S11")
    ap.add_argument("--out", default="damage_results")
    args = ap.parse_args(argv)

    curve = load_curve(args.curve)
    wc = WoehlerCurve(pd.Series({
        "k_1": float(curve["k_1"]), "ND": float(curve["ND"]), "SD": float(curve["SD"]),
        **({"k_2": float(curve["k_2"])} if curve.get("k_2") else {}),
    }))
    meta, (pts, df) = load_bundle(Path(args.bundle))

    comp = args.component
    if comp not in df.columns:
        raise ValueError(f"桥接包无应力分量 {comp}; 实际: {list(df.columns)}")

    per_point = []
    det_residuals = 0
    # frame_id 来自 CSV 是字符串，必须按整数排序（'10' < '2' 会打乱历程）。
    df = df.copy()
    df["frame_id"] = pd.to_numeric(df["frame_id"], errors="coerce")
    for pid, g in df.groupby("point_id"):
        series = g.sort_values("frame_id")
        stress = pd.to_numeric(series[comp], errors="coerce").to_numpy()
        if not np.isfinite(stress).all():
            # 真实 ODB 出现 NaN/失效：拒绝静默清理，记录并跳过该点。
            per_point.append({"point_id": pid, "status": "skipped_nonfinite",
                              "n_finite": int(np.isfinite(stress).sum())})
            continue
        det = rainflow.ThreePointDetector(rainflow.FullRecorder())
        det.process(stress, flush=True)
        det_residuals += len(det.residuals)
        loops = det.recorder.collective.copy()
        if len(loops) == 0:
            per_point.append({"point_id": pid, "status": "no_closed_loop"})
            continue
        loops["amplitude"] = (loops["to"] - loops["from"]).abs() / 2.0
        loops["Nf"] = wc.basquin_cycles(loops["amplitude"])
        loops["damage"] = 1.0 / loops["Nf"]
        per_point.append({
            "point_id": pid, "status": "ok",
            "closed_loops": int(len(loops)),
            "amplitude_max_MPa": float(loops["amplitude"].max()),
            "damage_sum": float(loops["damage"].sum()),
        })

    res = pd.DataFrame(per_point)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    res.to_csv(out / "per_point.csv", index=False)
    ok = res[res["status"] == "ok"]
    summary = {
        "schema": "fatigue-analysis-v1",
        "source_odb": meta.get("source"),
        "curve_material": curve.get("material"),
        "curve_source_csv": curve.get("source_csv"),
        "component": comp,
        "n_points_total": int(len(res)),
        "n_points_ok": int(len(ok)),
        "n_points_skipped_nonfinite": int((res["status"] == "skipped_nonfinite").sum()),
        "n_points_no_closed_loop": int((res["status"] == "no_closed_loop").sum()),
        "total_residual_turning_points": det_residuals,
        "note": "真实 ODB 应力历程；损伤用真实拟合曲线，残余循环未闭合未计入；"
                "此结果仍是教学工况，不是产品零件寿命验证。",
    }
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not ok.empty:
        crit = ok.loc[ok["damage_sum"].idxmax()]
        print("最高损伤材料点:", crit["point_id"], "损伤小计:", crit["damage_sum"])
    print("结果已写入:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
