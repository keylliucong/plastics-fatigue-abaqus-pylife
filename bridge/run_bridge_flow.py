"""驱动完整桥接闭环：探测 → 提取 → 契约校验 → 独立重读核对。

在目标环境按真实 ODB 运行：
    # 1) 探测
    abaqus python bridge/odb_probe.py Job.odb --out inv.json
    # 2) 提取
    abaqus python bridge/odb_extract.py Job.odb Step-1 --region PART-1 \
        --component S11 --frames 0:-1 --out bundle --meta units.json
    # 3) 本机独立重读核对
    python bridge/bridge_verify.py bundle

本脚本把上述顺序固化为一条命令（探测与提取需由 abaqus python 执行，
因此这里用 --probe-cmd/--extract-cmd 指定实际 Aabaqus 调用；mock 测试用同一
入口注入 fake odbAccess）。它本身不臆断单位、不改 ODB、不算寿命。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def verify_bundle(bundle_dir: Path) -> dict:
    """独立重读核对（纯 Python，可在与 Abaqus 隔离的环境运行）。"""
    import hashlib
    import csv

    mpath = bundle_dir / "manifest.json"
    if not mpath.exists():
        raise FileNotFoundError(f"缺少 manifest.json: {bundle_dir}")
    m = json.loads(mpath.read_text(encoding="utf-8"))

    checks: dict[str, object] = {}
    # 文件哈希（兼容 Windows 反斜杠清单在本机以 / 分隔的情况）。
    def _norm(rel: str) -> Path:
        return bundle_dir / rel.replace("\\", "/")
    ok = True
    for rel, spec in m.get("files", {}).items():
        p = _norm(rel)
        if not p.exists():
            ok = False
            break
        data = p.read_bytes()
        if len(data) != spec["bytes"] or hashlib.sha256(data).hexdigest() != spec["sha256"]:
            ok = False
            break
    checks["file_hashes_match"] = ok

    pts = list(csv.DictReader(open(bundle_dir / "points.csv")))
    ids = [p["point_id"] for p in pts]
    checks["point_id_unique"] = len(ids) == len(set(ids))
    checks["n_points_match"] = len(ids) == m.get("n_points")

    field_files = sorted((bundle_dir / "fields").glob("*.csv"))
    rows = [r for f in field_files for r in csv.DictReader(open(f))]
    checks["row_count_match"] = len(rows) == m.get("n_field_rows")
    checks["all_points_present"] = set(ids) == set(r["point_id"] for r in rows)
    # 截面点检查仅在存在壳/梁截面点时适用；纯实体模型无截面点，视为不适用(通过)。
    shell_pts = [p for p in pts if p["section_point_number"] not in ("", "None", "nan")]
    checks["shell_present"] = bool(shell_pts)
    if shell_pts:
        keys = {(p["instance"], p["element_label"], p["section_point_number"])
                for p in shell_pts}
        max_sp = max(int(p["section_point_number"]) for p in shell_pts
                     if str(p["section_point_number"]).isdigit())
        checks["shell_sections_separate"] = len(keys) == len(shell_pts) and max_sp >= 2
    else:
        checks["shell_sections_separate"] = True  # 无壳截面点，无合并风险
    checks["passed"] = all(v is True for k, v in checks.items()
                           if k not in ("passed", "shell_present"))
    checks["failed"] = [k for k, v in checks.items()
                        if v is not True and k not in ("passed", "shell_present")]
    return checks


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verify-only", metavar="BUNDLE_DIR")
    ap.add_argument("--mock", action="store_true", help="用注入的 mock ODB 跑通全流程")
    args = ap.parse_args(argv)

    if args.verify_only:
        v = verify_bundle(Path(args.verify_only))
        print(json.dumps(v, ensure_ascii=False, indent=2))
        return 0 if v["passed"] else 1

    if args.mock:
        # 注入 mock，直接调用真实提取代码跑完整链条。
        import tempfile
        sys.path.insert(0, str(HERE / "tests"))
        import fake_odbaccess
        fake_odbaccess.install()
        import odb_probe, odb_extract

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            inv = odb_probe.probe("mock.odb")
            assert inv["steps"][0]["n_frames"] == 4
            print("[1/4 探测] OK: 步骤/帧/分量/截面点已扫描")

            (td / "units.json").write_text(json.dumps({
                "units": {"stress_standard": "MPa", "stress_source": "MPa",
                          "time_source": "s", "time_meaning": "物理时间(模拟)"}
            }), encoding="utf-8")
            manifest = odb_extract.extract(
                "mock.odb", "Load", "", "S11", 0, -1, str(td / "bundle"),
                json.loads((td / "units.json").read_text()))
            print(f"[2/4 提取] OK: 点数={manifest['n_points']}, 行数={manifest['n_field_rows']}")

            v = verify_bundle(td / "bundle")
            print("[3/4 契约校验] OK" if v["passed"] else f"[3/4 契约校验] 失败: {v['failed']}")
            if not v["passed"]:
                return 1

            # 独立重读（新解释器语义：重新加载文件、不共享内存对象）。
            v2 = verify_bundle(td / "bundle")
            print("[4/4 独立重读核对] OK" if v2["passed"] else f"[4/4 失败]: {v2['failed']}")
            return 0 if v2["passed"] else 1

    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
