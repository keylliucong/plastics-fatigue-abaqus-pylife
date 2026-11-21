"""把验证/计算结果画成文献式图表 + 数据文件。

输入：
  --sn-curve  真实 S-N 拟合曲线 JSON（curve_real.json）
  --sn-data   真实 S-N 数据 CSV（含 load_amplitude_MPa/cycles/fracture 或 load/cycles/fracture）
  --history   桥接包目录（含 fields CSV，画应力历程）
  --damage    损伤结果目录（per_point.csv，画损伤分布）
  --out       输出目录（PNG + 对应数据 CSV）

输出图表（每张 PNG 配一个同名数据 CSV，保证可复核）：
  1. sn_curve.png        S-N 散点（断裂/run-out 分色）+ 拟合曲线 + 适用区间
  2. stress_history.png  选定材料点的应力-帧历程
  3. rainflow_loops.png  雨流闭合环幅值分布
  4. damage_map.png      各材料点损伤分布

注意：所有图均标注数据来源与适用边界，不把虚构参数画成真实材料结果。
运行（venv，含 matplotlib + pylife）：
  <venv>/Scripts/python.exe fatigue/plot_results.py --sn-curve ... --sn-data ... \
      --history ... --damage ... --out results/figures
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # 无界面后端，远程/批处理可运行
import matplotlib.pyplot as plt

# 中文字体：优先 Windows 微软雅黑/黑体，避免图上中文显示为方块。
from matplotlib import font_manager
for _fp in [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
            r"C:\Windows\Fonts\simsun.ttc"]:
    if Path(_fp).exists():
        font_manager.fontManager.addfont(_fp)
        plt.rcParams["font.sans-serif"] = [font_manager.FontProperties(fname=_fp).get_name()]
        break
plt.rcParams["axes.unicode_minus"] = False  # 正常显示负号


def save_data(df: pd.DataFrame, out: Path, name: str):
    df.to_csv(out / f"{name}.csv", index=False)


def plot_sn(curve_path: str, data_path: str, out: Path):
    curve = json.loads(Path(curve_path).read_text(encoding="utf-8"))
    df = pd.read_csv(data_path)
    amp_col = "load_amplitude_MPa" if "load_amplitude_MPa" in df.columns else "load"
    amp = df[amp_col].astype(float).to_numpy()
    cyc = df["cycles"].astype(float).to_numpy()
    frac = df["fracture"].astype(bool).to_numpy()

    k1 = float(curve["k_1"])
    ND = float(curve["ND"])
    SD = float(curve["SD"])
    # Basquin: 过 (SD, ND)，斜率 -1/k1 -> N = ND * (SD/S)^k1
    s_line = np.linspace(amp.min() * 0.9, amp.max() * 1.05, 200)
    n_line = ND * (SD / s_line) ** k1

    fig, ax = plt.subplots(figsize=(7, 5.2))
    ax.scatter(cyc[frac], amp[frac], c="#1f77b4", marker="o", s=55,
               label="断裂 (fracture)", zorder=3)
    if (~frac).any():
        ax.scatter(cyc[~frac], amp[~frac], c="#2ca02c", marker="s", s=70,
                   label="run-out (删失)", zorder=3)
    ax.plot(n_line, s_line, "-", color="#d62728", lw=2,
            label=f"MaxLike 拟合: k1={k1:.2f}, ND={ND:.2e}, SD={SD:.2f}")
    finite_levels = curve.get("finite_load_levels", [])
    if finite_levels:
        lo, hi = min(finite_levels), max(finite_levels)
        ax.axhspan(lo, hi, color="#d62728", alpha=0.08,
                   label=f"有效区间 {lo:.2f}–{hi:.2f} MPa")
    ax.set_xscale("log")
    ax.set_xlabel("循环数 N (对数)")
    ax.set_ylabel("应力幅 S_a (MPa)")
    # 标题简洁；完整数据来源放图底部居中，预留版面避免溢出遮挡图例。
    ax.set_title(f"S-N 曲线: {curve.get('material', 'N/A')}\n"
                 f"R={curve.get('R')}, f={curve.get('frequency')}")
    src = curve.get('source_csv', '')
    footer = f"数据来源: {src}" if src else ""
    if footer:
        fig.subplots_adjust(bottom=0.20)
        fig.text(0.5, 0.02, footer, ha="center", fontsize=8, color="#555")
    ax.grid(True, which="both", ls=":", alpha=0.5)
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(out / "sn_curve.png", dpi=160)
    plt.close(fig)

    save_data(pd.DataFrame({"amplitude_MPa": amp, "cycles": cyc,
                            "fracture": frac, "fit_cycles": ND * (SD / amp) ** k1}),
              out, "sn_curve_data")


def load_history(history_dir: Path) -> pd.DataFrame:
    files = sorted((history_dir / "fields").glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"无历程 CSV: {history_dir}")
    return pd.concat([pd.read_csv(f, dtype={"point_id": str}) for f in files],
                     ignore_index=True)


def plot_history(history_dir: Path, out: Path, point_id: str | None = None):
    df = load_history(history_dir)
    df["frame_id"] = pd.to_numeric(df["frame_id"], errors="coerce")
    comp_col = "S11" if "S11" in df.columns else "S11_MPa"
    pid = point_id or df["point_id"].iloc[0]
    g = df[df["point_id"] == pid].sort_values("frame_id")
    t = g["step_time"].astype(float).to_numpy()
    s = pd.to_numeric(g[comp_col], errors="coerce").to_numpy()

    fig, ax = plt.subplots(figsize=(8, 4.4))
    ax.plot(t, s, "-o", color="#1f77b4", ms=4, lw=1.5)
    ax.axhline(0, color="gray", lw=0.8)
    ax.set_xlabel("步时间 (用户确认单位)")
    ax.set_ylabel("应力 S11 (MPa)")
    ax.set_title(f"材料点应力历程: {pid}\n(真实 ODB 提取; 单位由用户确认)")
    ax.grid(True, ls=":", alpha=0.5)
    fig.tight_layout()
    fig.savefig(out / "stress_history.png", dpi=160)
    plt.close(fig)
    save_data(pd.DataFrame({"step_time": t, "S11_MPa": s}), out, "stress_history_data")


def plot_rainflow(history_dir: Path, out: Path):
    """雨流闭合环幅值分布（对每个材料点跑一遍）。"""
    import pylife.stress.rainflow as rainflow
    df = load_history(history_dir)
    df["frame_id"] = pd.to_numeric(df["frame_id"], errors="coerce")
    comp_col = "S11" if "S11" in df.columns else "S11_MPa"
    amps = []
    for pid, g in df.groupby("point_id"):
        s = pd.to_numeric(g.sort_values("frame_id")[comp_col], errors="coerce").to_numpy()
        if not np.isfinite(s).all():
            continue
        det = rainflow.ThreePointDetector(rainflow.FullRecorder())
        det.process(s, flush=True)
        loops = det.recorder.collective
        if len(loops):
            amps.extend(((loops["to"] - loops["from"]).abs() / 2.0).tolist())
    amps = np.array(amps)

    fig, ax = plt.subplots(figsize=(7, 4.4))
    if len(amps):
        ax.hist(amps, bins=20, color="#9467bd", edgecolor="white")
        ax.set_title(f"雨流闭合环幅值分布 (共 {len(amps)} 环, "
                     f"均值 {amps.mean():.2f} MPa)")
    else:
        ax.text(0.5, 0.5, "无闭合环", ha="center", va="center")
        ax.set_title("雨流闭合环幅值分布")
    ax.set_xlabel("应力幅 (MPa)")
    ax.set_ylabel("环数")
    ax.grid(True, ls=":", alpha=0.5)
    fig.tight_layout()
    fig.savefig(out / "rainflow_loops.png", dpi=160)
    plt.close(fig)
    save_data(pd.DataFrame({"loop_amplitude_MPa": amps}), out, "rainflow_loops_data")


def plot_damage(damage_dir: Path, out: Path):
    df = pd.read_csv(Path(damage_dir) / "per_point.csv")
    ok = df[df["status"] == "ok"].copy()
    if "damage_sum" not in ok.columns:
        return
    d = ok["damage_sum"].astype(float).to_numpy()
    ids = ok["point_id"].astype(str).to_numpy()

    fig, ax = plt.subplots(figsize=(9, 4.4))
    idx = np.arange(len(d))
    ax.bar(idx, d, color="#ff7f0e")
    ax.set_xlabel("材料点序号 (按 point_id 排序)")
    ax.set_ylabel("Miner 损伤小计 D")
    ax.set_title(f"逐材料点损伤 (共 {len(d)} 点, 最大 D={d.max():.3e}; "
                 f"虚构曲线仅验算时此值不代表真实寿命)")
    ax.grid(True, axis="y", ls=":", alpha=0.5)
    fig.tight_layout()
    fig.savefig(out / "damage_map.png", dpi=160)
    plt.close(fig)
    save_data(pd.DataFrame({"point_id": ids, "damage_sum": d}), out, "damage_map_data")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sn-curve")
    ap.add_argument("--sn-data")
    ap.add_argument("--history")
    ap.add_argument("--damage")
    ap.add_argument("--out", default="results/figures")
    ap.add_argument("--point-id", default=None)
    args = ap.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if args.sn_curve and args.sn_data:
        plot_sn(args.sn_curve, args.sn_data, out)
        print("[OK] sn_curve.png")
    if args.history:
        plot_history(Path(args.history), out, args.point_id)
        plot_rainflow(Path(args.history), out)
        print("[OK] stress_history.png, rainflow_loops.png")
    if args.damage:
        plot_damage(Path(args.damage), out)
        print("[OK] damage_map.png")
    print("图表与数据文件已写入:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
