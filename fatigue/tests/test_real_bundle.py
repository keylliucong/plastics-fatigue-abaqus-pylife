"""真实桥接包分析入口回归测试（pyLife 2.3.1）。

覆盖审查后修复的回归点：
  - 同一物理载荷下，源单位 MPa 与 Pa 的幅值/损伤结果一致；
  - 缺帧、valid=false 的材料点被逐点排除，不再静默进入损伤；
  - 单位未确认时拒绝计算（退出码 2）；
  - 壳/梁截面点基底未解析时拒绝计算，显式允许后才算；
  - S-N 拟合兼容 load_amplitude_MPa 模板列名，fracture 严格解析。

运行：
  <含 pyLife 的 python> fatigue/tests/test_real_bundle.py
"""

import contextlib
import csv
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "fatigue"))
sys.path.insert(0, str(REPO / "bridge"))

import numpy as np  # noqa: E402
import analyze_real_bundle as arb  # noqa: E402
import fit_sn_curve  # noqa: E402
from bundle_validation import _sha256  # noqa: E402
from contract import BundleWriter  # noqa: E402
import units  # noqa: E402

SRC = REPO / "realrun" / "bridge_cyclic"
CURVE = {
    "schema": "sn-curve-fit-v1",
    "material": "TEST-Rodrigues2026",
    "R": 0.05,
    "k_1": 4.66,
    "ND": 8.9e5,
    "SD": 2.43,
    "finite_load_levels": [2.52, 2.68, 3.15, 4.5, 6.3, 8.0, 10.0, 13.39],
}


def _field_files(bundle: Path):
    return sorted((bundle / "fields").glob("*.csv"))


def read_rows(bundle: Path):
    return [r for f in _field_files(bundle) for r in csv.DictReader(open(f, newline=""))]


def write_rows(bundle: Path, rows):
    header = list(rows[0].keys())
    with open(_field_files(bundle)[0], "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(rows)


def rehash(bundle: Path):
    m = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    files = _field_files(bundle)
    rows = [r for f in files for r in csv.DictReader(open(f, newline=""))]
    m["n_field_rows"] = len(rows)
    m["files"] = {p.relative_to(bundle).as_posix():
                  {"bytes": p.stat().st_size, "sha256": _sha256(p)} for p in files}
    (bundle / "manifest.json").write_text(
        json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_analysis(bundle: Path, out: Path, curve: Path, extra=()) -> int:
    args = [str(bundle), "--curve", str(curve), "--out", str(out), *extra]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        return arb.main(args)


def copy_bundle(tmp: Path, name: str) -> Path:
    d = tmp / name
    shutil.copytree(SRC, d)
    return d


def test_unit_invariance(tmp: Path, curve: Path):
    mpa = copy_bundle(tmp, "mpa")
    pa = copy_bundle(tmp, "pa")
    scale = 1e6
    rows = read_rows(pa)
    for r in rows:
        for c in ("S11", "S22", "S33", "S12", "S13", "S23"):
            if r.get(c, "") not in ("", None):
                r[c] = repr(float(r[c]) * scale)
    write_rows(pa, rows)
    m = json.loads((pa / "manifest.json").read_text(encoding="utf-8"))
    m["units"] = {"stress_source": "Pa", "stress_standard": "MPa",
                  "stress_scale_to_MPa": 1e-6,
                  "time_source": "s", "time_meaning": "physical"}
    (pa / "manifest.json").write_text(json.dumps(m, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
    rehash(pa)

    out_a, out_b = tmp / "dmg_mpa", tmp / "dmg_pa"
    rc_a = run_analysis(mpa, out_a, curve)
    rc_b = run_analysis(pa, out_b, curve)
    assert rc_a == 0 and rc_b == 0, (rc_a, rc_b)

    import pandas as pd
    a = pd.read_csv(out_a / "per_point.csv").set_index("point_id")
    b = pd.read_csv(out_b / "per_point.csv").set_index("point_id")
    assert list(a.index) == list(b.index)
    aa = a["amplitude_max_MPa"].astype(float)
    bb = b["amplitude_max_MPa"].astype(float)
    assert np.allclose(aa, bb, rtol=1e-5, atol=0), (aa.head(), bb.head())
    assert np.allclose(a["damage_sum"].astype(float), b["damage_sum"].astype(float),
                       rtol=1e-4), "Pa 与 MPa 输入应得到一致损伤"
    print("[PASS] units: MPa 与 Pa 输入的幅值/损伤一致")


def test_missing_frame_excluded(tmp: Path, curve: Path):
    b = copy_bundle(tmp, "missing")
    rows = read_rows(b)
    pid = rows[0]["point_id"]
    drop_frame = "5"
    kept = [r for r in rows if not (r["point_id"] == pid
                                    and r["frame_id"] == drop_frame)]
    assert len(kept) == len(rows) - 1
    write_rows(b, kept)
    rehash(b)

    out = tmp / "dmg_missing"
    rc = run_analysis(b, out, curve)
    assert rc == 0, rc
    import pandas as pd
    df = pd.read_csv(out / "per_point.csv").set_index("point_id")
    assert df.loc[pid, "status"] == "missing_frames"
    assert (df["status"] == "ok").sum() == 31
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["n_points_missing_frames"] == 1
    print("[PASS] analysis: 缺帧点被排除，其余 31 点仍计算")


def test_invalid_flag_excluded(tmp: Path, curve: Path):
    b = copy_bundle(tmp, "invalid")
    rows = read_rows(b)
    victim = rows[3]
    victim["valid"] = "false"
    write_rows(b, rows)
    rehash(b)

    out = tmp / "dmg_invalid"
    rc = run_analysis(b, out, curve)
    assert rc == 0, rc
    import pandas as pd
    df = pd.read_csv(out / "per_point.csv").set_index("point_id")
    assert df.loc[victim["point_id"], "status"] == "invalid_frames"
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["n_points_invalid_frames"] == 1
    print("[PASS] analysis: valid=false 的点被排除")


def test_unconfirmed_units_refused(tmp: Path, curve: Path):
    b = copy_bundle(tmp, "nounit")
    m = json.loads((b / "manifest.json").read_text(encoding="utf-8"))
    m["units"] = {"stress_source": "UNCONFIRMED", "stress_standard": "MPa",
                  "time_source": "s", "time_meaning": "unknown"}
    (b / "manifest.json").write_text(json.dumps(m, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    rehash(b)
    rc = run_analysis(b, tmp / "dmg_nounit", curve)
    assert rc == 2, f"单位未确认应退出 2，实际 {rc}"
    print("[PASS] analysis: 单位未确认时拒绝计算（exit 2）")


def _shell_bundle(tmp: Path) -> Path:
    d = tmp / "shell"
    w = BundleWriter(d, manifest_meta={
        "schema": "bridge-bundle-v1", "source": "mock", "step": "Load",
        "component": "S11", "frame_range": [0, 8], "n_frames": 9,
        "units": units.normalize_units({"units": {"stress_source": "MPa"}}),
        "basis": {"coordinate_system": "local-unresolved",
                  "declared": "unknown", "resolved": False},
    })
    for sp in (1, 2):
        pid = w.add_point("SHELL-1", 2, 1, sp, f"SP{sp}", "S4R",
                          "INTEGRATION_POINT")
        for frame, val in enumerate([0.0, 5.0, 0.0, -5.0, 0.0,
                                     5.0, 0.0, -5.0, 0.0]):
            w.add_field(pid, frame, float(frame), "INTEGRATION_POINT",
                        "local-unresolved", {"S11": val}, True, "not_provided")
    w.finish()
    return d


def test_shell_basis_gate(tmp: Path, curve: Path):
    b = _shell_bundle(tmp)
    rc = run_analysis(b, tmp / "dmg_shell", curve)
    assert rc == 2, f"壳截面点基底未解析应拒绝，实际 {rc}"
    rc2 = run_analysis(b, tmp / "dmg_shell_ok", curve,
                       extra=("--allow-unresolved-basis",))
    assert rc2 == 0, rc2
    print("[PASS] analysis: 壳截面点基底未解析拒绝计算，显式允许后可算")


def test_fit_columns_and_strict_bool(tmp: Path):
    ok = tmp / "sn_ok.csv"
    ok.write_text(
        "load_amplitude_MPa,cycles,fracture\n"
        "13.39,455,True\n10.0,2100,True\n6.3,13927,True\n"
        "3.15,256682,False\n", encoding="utf-8")
    df = fit_sn_curve.load_data(str(ok))
    assert len(df) == 4
    assert df["fracture"].dtype == bool
    assert int((~df["fracture"]).sum()) == 1, "字符串 False 必须解析为 run-out"

    legacy = tmp / "sn_legacy.csv"
    legacy.write_text(
        "load,cycles,fracture\n13.39,455,1\n10.0,2100,1\n6.3,13927,1\n"
        "3.15,256682,0\n", encoding="utf-8")
    assert len(fit_sn_curve.load_data(str(legacy))) == 4

    bad = tmp / "sn_bad.csv"
    bad.write_text(
        "load_amplitude_MPa,cycles,fracture\n"
        "13.39,455,True\n10.0,2100,unknown\n6.3,13927,True\n"
        "3.15,256682,False\n", encoding="utf-8")
    try:
        fit_sn_curve.load_data(str(bad))
    except ValueError as exc:
        assert "fracture" in str(exc)
    else:
        raise AssertionError("未知 fracture 标记应报错")
    print("[PASS] fit: 模板列名兼容 / fracture 严格解析")


def main():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        curve = tmp / "curve.json"
        curve.write_text(json.dumps(CURVE, ensure_ascii=False, indent=2),
                         encoding="utf-8")
        test_unit_invariance(tmp, curve)
        test_missing_frame_excluded(tmp, curve)
        test_invalid_flag_excluded(tmp, curve)
        test_unconfirmed_units_refused(tmp, curve)
        test_shell_basis_gate(tmp, curve)
    with tempfile.TemporaryDirectory() as td:
        test_fit_columns_and_strict_bool(Path(td))
    print("ALL REAL-BUNDLE ANALYSIS TESTS PASSED")


if __name__ == "__main__":
    main()
