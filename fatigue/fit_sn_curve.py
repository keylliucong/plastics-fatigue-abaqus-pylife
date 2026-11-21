"""真实恒幅 S–N 数据拟合 Wöhler 曲线（pyLife 2.3.1）。

输入 CSV 列：load(应力幅,MPa), cycles(循环数), fracture(bool，run-out=False)。
pyLife 的 FatigueData/MaxLikeFull 处理断裂与 run-out，输出 k_1, ND, SD, TN, TS。

运行：
  <pyLife-2.3.1>/bin/python fatigue/fit_sn_curve.py sn_data.csv --out curve.json \
      --material NAME --R -1 --temp 23C --freq 5Hz

注意：
  - 只用实际试验数据；本脚本不会用虚构数据冒充结果。
  - 拟合数据须来自匹配牌号/工艺/工况；验证集不得参与拟合。
  - 少于两个有限区应力水平时 pyLife 会告警或给出 NaN，脚本据此拒绝输出。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from pylife.materialdata.woehler import FatigueData, MaxLikeFull, Elementary

REQUIRED = {"load", "cycles", "fracture"}


def load_data(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    missing = REQUIRED - set(df.columns)
    if missing:
        raise ValueError(f"缺少必需列: {sorted(missing)}")
    df = df[["load", "cycles", "fracture"]].dropna()
    df["load"] = pd.to_numeric(df["load"])
    df["cycles"] = pd.to_numeric(df["cycles"])
    df["fracture"] = df["fracture"].astype(bool)
    if (df["load"] <= 0).any() or (df["cycles"] <= 0).any():
        raise ValueError("load 与 cycles 必须为正")
    if len(df) < 3:
        raise ValueError("至少 3 条数据点才能拟合")
    return df


def fit(df: pd.DataFrame, method: str = "maxlike") -> dict:
    fd = FatigueData(df)
    finite = fd.finite_zone
    if finite.load.nunique() < 2:
        raise ValueError("有限区少于两个不同应力水平，无法拟合斜率")
    fitter = MaxLikeFull(fd) if method == "maxlike" else Elementary(fd)
    wc = fitter.analyze()
    out = {k: (None if v is None or (isinstance(v, float) and np.isnan(v)) else float(v))
           for k, v in wc.items()}
    if out.get("k_1") is None or out["k_1"] <= 0:
        raise ValueError(f"拟合得到有效斜率失败: {out}")
    out["method"] = method
    out["n_points"] = int(len(df))
    out["n_fracture"] = int(df["fracture"].sum())
    out["n_runout"] = int((~df["fracture"]).sum())
    out["finite_load_levels"] = sorted(float(x) for x in finite.load.unique())
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv")
    ap.add_argument("--out", default="curve.json")
    ap.add_argument("--method", choices=["maxlike", "elementary"], default="maxlike")
    ap.add_argument("--material", default="")
    ap.add_argument("--R", type=float, default=None)
    ap.add_argument("--temp", default="")
    ap.add_argument("--freq", default="")
    args = ap.parse_args(argv)

    df = load_data(args.csv)
    result = fit(df, args.method)
    result.update({
        "schema": "sn-curve-fit-v1",
        "material": args.material, "R": args.R,
        "temperature": args.temp, "frequency": args.freq,
        "source_csv": str(Path(args.csv).resolve()),
        "note": "由真实恒幅试验数据拟合；适用区间见 finite_load_levels；外推需另行验证。",
    })
    Path(args.out).write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"拟合完成: {args.out}")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
