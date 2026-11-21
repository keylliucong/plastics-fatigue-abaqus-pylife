"""独立读取适配器：在分离进程中重读桥接包并核对（PRD FR-08）。

不读 ODB、不计算损伤；只验证数据包可被独立加载、文件哈希一致、
材料点键唯一、历程/参数可还原为 pandas 对象。对应 PRD 的
“导出 → 在独立 Python 中重读并核对”闭环。

运行：
  <pyLife-2.3.1>/bin/python fatigue/bridge_adapter.py <bridge_bundle_dir>
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


class BundleError(RuntimeError):
    pass


def load_bundle(bundle_dir: Path) -> dict:
    """从目录独立加载桥接包；任何缺失/哈希不符/重复键都抛错。"""
    manifest_p = bundle_dir / "manifest.json"
    if not manifest_p.exists():
        raise BundleError(f"缺少 manifest.json: {bundle_dir}")
    manifest = json.loads(manifest_p.read_text(encoding="utf-8"))

    # 核对文件哈希。
    for rel, spec in manifest.get("files", {}).items():
        p = bundle_dir / rel
        if not p.exists():
            raise BundleError(f"清单列出但文件缺失: {rel}")
        data = p.read_bytes()
        if len(data) != spec["bytes"]:
            raise BundleError(f"文件大小不符: {rel}")
        if hashlib.sha256(data).hexdigest() != spec["sha256"]:
            raise BundleError(f"SHA-256 不符: {rel}")

    points = pd.read_csv(bundle_dir / "points.csv", dtype={"point_id": str})
    field_files = sorted((bundle_dir / "fields").glob("*.csv"))
    if not field_files:
        raise BundleError("fields/ 下无历程 CSV")
    fields = pd.concat([pd.read_csv(f, dtype={"point_id": str}) for f in field_files],
                       ignore_index=True)

    params_p = bundle_dir / "fatigue_parameters.json"
    params = json.loads(params_p.read_text(encoding="utf-8")) if params_p.exists() else None

    return {"manifest": manifest, "points": points, "fields": fields,
            "fatigue": params, "field_files": [f.name for f in field_files]}


def verify(bundle: dict) -> dict:
    m, pts, fld = bundle["manifest"], bundle["points"], bundle["fields"]
    checks: dict[str, object] = {}
    checks["file_hashes_match"] = True  # load_bundle 已逐文件校验，未抛错即通过
    checks["point_id_unique"] = bool(pts["point_id"].is_unique)
    checks["row_count_matches_manifest"] = len(fld) == m["n_field_rows"]
    checks["all_points_present"] = set(pts["point_id"]) == set(fld["point_id"])
    checks["all_stress_finite"] = bool(np.isfinite(fld["S11_MPa"].to_numpy()).all())
    ordered = all(
        g.sort_values("frame_id")["step_time_s"].is_monotonic_increasing
        for _, g in fld.groupby("point_id")
    )
    checks["time_ordered_per_point"] = bool(ordered)
    checks["shell_points_present"] = bool(pts["section_point_number"].notna().any())
    checks["curve_params_present"] = bundle["fatigue"] is not None and bool(
        bundle["fatigue"].get("curve", {}).get("k_1")
    )
    checks["passed"] = all(v is True for k, v in checks.items() if k != "passed")
    checks["failed"] = [k for k, v in checks.items() if v is not True]
    return checks


def point_history(bundle: dict, point_id: str) -> pd.DataFrame:
    """返回指定材料点的有符号应力历程（pandas 对象），供下游 pyLife 使用。"""
    return (bundle["fields"].query("point_id == @point_id")
            .sort_values("frame_id")[["frame_id", "step_time_s", "S11_MPa"]]
            .reset_index(drop=True))


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("用法: bridge_adapter.py <bridge_bundle_dir>", file=sys.stderr)
        return 2
    b = load_bundle(Path(argv[1]))
    v = verify(b)
    print("=== 独立读取核对（合成桥接包）===")
    print("包来源:", b["manifest"]["source"])
    print("历程文件:", b["field_files"])
    print("材料点数:", len(b["points"]), "历程行数:", len(b["fields"]))
    print("校验:", v)
    if not v["passed"]:
        print("独立核对失败:", v["failed"], file=sys.stderr)
        return 1
    # 示例：还原一个点的历程，证明可作为 pandas 对象交给后续 pyLife。
    pid = b["points"]["point_id"].iloc[0]
    print("示例历程点:", pid)
    print(point_history(b, pid).to_string(index=False))
    print("结论: 导出包可在独立进程重读并核对一致（合成数据，非真实 ODB）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
