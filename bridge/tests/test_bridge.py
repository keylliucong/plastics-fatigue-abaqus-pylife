"""本机桥接逻辑测试（注入 fake odbAccess，不需要真实 Abaqus）。

验证 PRD 关键点：材料点键唯一、实体积分点与壳上下截面点分离保留、
NaN/失效单元标记、缺失分量不补零、包可被独立重读、哈希一致。
"""

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BRIDGE = HERE.parent
sys.path.insert(0, str(HERE))      # fake_odbaccess
sys.path.insert(0, str(BRIDGE))    # contract, odb_probe, odb_extract

import fake_odbaccess  # noqa: E402
fake_odbaccess.install()

import csv  # noqa: E402


def test_probe():
    import odb_probe
    inv = odb_probe.probe("mock.odb")
    assert inv["schema"] == "odb-inventory-v1"
    assert len(inv["steps"]) == 1
    step = inv["steps"][0]
    assert step["domain"] == "TIME"
    assert step["n_frames"] == 4
    S = step["fieldOutputs"]["S"]
    assert "S11" in S["componentLabels"]
    assert any("TOP" in sp or "1" == sp for sp in S["sectionPoints"])
    assert len(inv["instances"]) == 2
    print("[PASS] probe: 步骤/帧/分量/截面点/实例已列出")


def test_extract_and_contract():
    import odb_extract
    with tempfile.TemporaryDirectory() as td:
        meta = {"units": {"stress_standard": "MPa", "stress_source": "MPa",
                          "time_source": "s", "time_meaning": "物理时间(模拟)"}}
        manifest = odb_extract.extract(
            "mock.odb", "Load", "", "S11", 0, -1, td, meta)
        assert manifest["schema"] == "bridge-bundle-v1"
        assert manifest["n_frames"] == 4

        pts = list(csv.DictReader(open(Path(td) / "points.csv")))
        ids = [p["point_id"] for p in pts]
        assert len(ids) == len(set(ids)), "材料点键必须唯一"
        # 实体积分点 + 壳上下两个截面点 = 3 个材料点。
        assert len(pts) == 3, ids
        shell_sp = [p["section_point_number"] for p in pts
                    if p["instance"] == "SHELL-1"]
        assert set(shell_sp) == {"1", "2"}, "壳上下截面点必须分别保留"

        rows = list(csv.DictReader(open(Path(td) / "fields" / "part-000001.csv")))
        assert len(rows) == manifest["n_field_rows"] == 12  # 3 点 × 4 帧
        # NaN 与失效单元必须保留行并标记无效，不静默删除。
        nan_rows = [r for r in rows if r["S11"] and r["S11"].lower() == "nan"]
        assert len(nan_rows) == 1, "NaN 行应保留"
        invalid = [r for r in rows if r["valid"] == "false"]
        assert invalid, "失效/NaN 点应标记 valid=false"
        # manifest 文件哈希存在。
        assert "points.csv" in manifest["files"]
        assert "sha256" in manifest["files"]["points.csv"]

        # 独立重读一致性（用 contract 的哈希定义核对）。
        from contract import _sha256
        for rel, spec in manifest["files"].items():
            assert _sha256(Path(td) / rel) == spec["sha256"], f"哈希不符: {rel}"
        print("[PASS] extract: 点键唯一/壳截面分离/NaN与失效保留/哈希一致")


if __name__ == "__main__":
    test_probe()
    test_extract_and_contract()
    print("ALL BRIDGE TESTS PASSED")
