"""桥接契约与结构校验测试（注入 fake odbAccess，不需要真实 Abaqus）。

覆盖审查后修复的回归点：
  - 单位登记/换算：Pa→MPa、N/mm2、未确认/未知单位；
  - 重复导出：默认拒绝；--overwrite 后行数与清单一致、旧分块被清理；
  - 缺帧、valid=false 可被检出并按点记录；
  - 不同积分点的壳截面记录不被误判为重复；
  - fields/ 下清单未列出的文件会报错（防追加脏数据）。

运行：
  <含 numpy 的 python> bridge/tests/test_contract_validation.py
"""

import csv
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
BRIDGE = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(BRIDGE))

import fake_odbaccess  # noqa: E402

fake_odbaccess.install()

import units  # noqa: E402
from bundle_validation import _sha256, validate_bundle  # noqa: E402
from contract import BundleWriter  # noqa: E402
import odb_extract  # noqa: E402

META = {"units": {"stress_source": "MPa", "stress_standard": "MPa",
                  "time_source": "s", "time_meaning": "physical"}}


def _rows(bundle: Path):
    files = sorted((bundle / "fields").glob("*.csv"))
    return files, [r for f in files for r in csv.DictReader(open(f, newline=""))]


def rehash(bundle: Path):
    m = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    files, rows = _rows(bundle)
    m["n_field_rows"] = len(rows)
    m["files"] = {p.relative_to(bundle).as_posix():
                  {"bytes": p.stat().st_size, "sha256": _sha256(p)} for p in files}
    (bundle / "manifest.json").write_text(
        json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_units():
    assert units.stress_scale_to_mpa("Pa") == 1e-6
    assert units.stress_scale_to_mpa("N/mm^2") == 1.0
    assert units.stress_scale_to_mpa("kPa") == 1e-3
    assert units.stress_scale_to_mpa("UNCONFIRMED") is None
    norm = units.normalize_units({"units": {"stress_source": "Pa"}})
    assert norm["stress_scale_to_MPa"] == 1e-6
    assert norm["stress_standard"] == "MPa"
    assert units.normalize_units({})["stress_scale_to_MPa"] is None
    try:
        units.normalize_units({"units": {"stress_source": "furlong"}})
    except ValueError:
        pass
    else:
        raise AssertionError("未知单位应报错，而不是静默当成 MPa")
    print("[PASS] units: Pa/N-mm2/未确认/未知单位")


def test_duplicate_export():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / "bundle"
        m1 = odb_extract.extract("mock.odb", "Load", "", "S11", 0, -1, str(d), META)
        assert m1["n_field_rows"] == 12
        try:
            odb_extract.extract("mock.odb", "Load", "", "S11", 0, -1, str(d), META)
        except ValueError as exc:
            assert "已存在桥接包" in str(exc)
        else:
            raise AssertionError("同一目录二次导出应被拒绝")

        # 模拟旧版本留下的多余分块与陈旧行。
        stray = d / "fields" / "part-000099.csv"
        stray.write_text((d / "fields" / "part-000001.csv").read_text(encoding="utf-8"),
                         encoding="utf-8")
        m2 = odb_extract.extract("mock.odb", "Load", "", "S11", 0, -1, str(d), META,
                                 overwrite=True)
        assert m2["n_field_rows"] == 12
        files, rows = _rows(d)
        assert len(rows) == 12, f"覆盖后行数应为 12，实际 {len(rows)}"
        assert len(files) == 1, f"旧分块应被清理，实际 {[p.name for p in files]}"
        report = validate_bundle(d)
        assert report["passed"], report["errors"]
        print("[PASS] duplicate export: 默认拒绝 / overwrite 后 12 行且旧分块清理")


def test_missing_frame_and_invalid_flag():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / "bundle"
        odb_extract.extract("mock.odb", "Load", "", "S11", 0, -1, str(d), META)
        files, rows = _rows(d)
        pid = rows[0]["point_id"]
        kept = [r for r in rows if not (r["point_id"] == pid and r["frame_id"] == "0")]
        assert len(kept) == len(rows) - 1
        header = list(rows[0].keys())
        with open(files[0], "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=header)
            w.writeheader()
            w.writerows(kept)
        # 再把另一个点的一帧标为失效。
        victim = next(r for r in kept if r["point_id"] != pid)
        for r in kept:
            if r is victim:
                r["valid"] = "false"
        with open(files[0], "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=header)
            w.writeheader()
            w.writerows(kept)
        rehash(d)

        report = validate_bundle(d)
        assert report["checks"]["frame_coverage_complete"] is False
        assert report["points"][pid]["missing_frames"] == [0]
        assert report["points"][victim["point_id"]]["invalid_frames"] == [int(victim["frame_id"])]
        assert report["stats"]["n_points_missing_frames"] == 1
        # fake ODB 里壳下截面点本来就是 STATUS=0（4 帧全失效），再加刚标失效的点。
        assert report["stats"]["n_points_invalid_frames"] == 2
        assert report["points"][pid]["invalid_frames"] == []
        print("[PASS] validator: 缺帧与 valid=false 可按点检出")


def test_shell_points_across_integration_points():
    """同一单元不同积分点、相同截面点编号，不能算重复。"""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / "shell"
        w = BundleWriter(d, manifest_meta={
            "schema": "bridge-bundle-v1", "source": "mock", "step": "Load",
            "component": "S11", "frame_range": [0, 1], "n_frames": 2,
            "units": units.normalize_units(META),
            "basis": {"coordinate_system": "global", "declared": "global",
                      "resolved": True},
        })
        for ip in (1, 2):
            for sp in (1, 2):
                pid = w.add_point("SHELL-1", 2, ip, sp, f"SP{sp}", "S4R",
                                  "INTEGRATION_POINT")
                for frame in (0, 1):
                    w.add_field(pid, frame, float(frame), "INTEGRATION_POINT",
                                "global", {"S11": 10.0 * frame}, True, "not_provided")
        w.finish()
        report = validate_bundle(d)
        assert report["passed"], report["errors"]
        assert report["checks"]["shell_sections_separate"] is True
        assert report["n_points"] == 4
        print("[PASS] shell: 不同积分点的截面点记录未被误判重复")


def test_publish_refuses_incomplete_frames():
    """提取端丢帧时必须在发布前失败，目标目录不能出现半成品包。"""
    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / "partial"
        w = BundleWriter(d, manifest_meta={
            "schema": "bridge-bundle-v1", "source": "mock", "step": "Load",
            "component": "S11", "frame_range": [0, 1], "n_frames": 2,
            "units": units.normalize_units(META),
        })
        ok_pid = w.add_point("PART-1", 1, 1, None, None, "C3D8R",
                             "INTEGRATION_POINT")
        for frame in (0, 1):
            w.add_field(ok_pid, frame, float(frame), "INTEGRATION_POINT",
                        "local-unresolved", {"S11": 1.0}, True, "not_provided")
        bad_pid = w.add_point("PART-1", 2, 1, None, None, "C3D8R",
                              "INTEGRATION_POINT")
        w.add_field(bad_pid, 0, 0.0, "INTEGRATION_POINT",
                    "local-unresolved", {"S11": 1.0}, True, "not_provided")
        try:
            w.finish()
        except RuntimeError as exc:
            assert "帧覆盖不完整" in str(exc)
        else:
            raise AssertionError("缺帧包不应发布成功")
        assert not (d / "manifest.json").exists()
        assert not (d / "points.csv").exists()
        assert (d / BundleWriter.STAGE_NAME).exists(), "暂存目录应保留供排查"
        print("[PASS] publish: 缺帧时拒绝发布，目标目录无半成品包")


def test_unlisted_field_file():
    with tempfile.TemporaryDirectory() as td:
        d = Path(td) / "bundle"
        odb_extract.extract("mock.odb", "Load", "", "S11", 0, -1, str(d), META)
        src = d / "fields" / "part-000001.csv"
        extra = d / "fields" / "part-000002.csv"
        extra.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        report = validate_bundle(d)
        assert not report["passed"]
        assert any("未列出" in e for e in report["errors"]), report["errors"]
        print("[PASS] validator: 清单外 fields 文件报错")


if __name__ == "__main__":
    test_units()
    test_duplicate_export()
    test_missing_frame_and_invalid_flag()
    test_shell_points_across_integration_points()
    test_publish_refuses_incomplete_frames()
    test_unlisted_field_file()
    print("ALL CONTRACT/VALIDATION TESTS PASSED")
