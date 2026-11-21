"""桥接包结构校验（纯标准库；提取端发布前、分析入口、GUI 共用）。

校验内容（PRD FR-03/FR-04/FR-05）：
  - manifest 存在、schema 正确；清单内文件存在且大小/SHA-256 一致；
  - fields/ 下不存在清单未列出的 CSV（防止重复导出追加出的脏数据）；
  - points.csv 键唯一、数量与清单一致；历程行数一致；
  - (point_id, frame_id) 组合键唯一，无未知材料点；
  - 每个材料点的帧覆盖完整（与 manifest.frame_range 对齐）；
  - valid 标志可解析（true/false），并记录各点失效/非有限值帧；
  - 应力基底（coordinate_system）逐行记录且一致；
  - 壳/梁截面点按 (instance, element, integration_point, section_point) 保留，
    不同积分点的记录不会被误判为重复。

返回的 report 中：
  errors   —— 结构性问题，必须拒绝发布/计算；
  points   —— 每个材料点的 missing_frames / invalid_frames / nonfinite_frames；
  stats    —— 行数、点数、分量范围（源单位）等预览用信息。
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

try:  # 脚本方式（sys.path 指向 bridge/）
    from units import units_from_manifest
except ImportError:  # 包方式
    from .units import units_from_manifest  # type: ignore

SCHEMA = "bridge-bundle-v1"
FIELD_REQUIRED = ("point_id", "frame_id", "step_time", "coordinate_system",
                  "valid", "status")
POINT_REQUIRED = ("point_id", "instance", "element_label",
                  "integration_point", "section_point_number")

_EMPTY_SP = {"", "none", "nan", "null"}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _norm_rel(rel: str) -> str:
    return str(rel).replace("\\", "/").lstrip("./")


def _is_num(text) -> bool:
    try:
        float(text)
        return True
    except (TypeError, ValueError):
        return False


def _parse_valid(text) -> bool:
    s = str(text).strip().lower()
    if s in ("true", "1", "yes", "y", "t"):
        return True
    if s in ("false", "0", "no", "n", "f"):
        return False
    raise ValueError(f"valid 值无法解析: {text!r}")


def _parse_int(text, field: str) -> int:
    try:
        return int(str(text).strip())
    except (TypeError, ValueError):
        raise ValueError(f"{field} 不是整数: {text!r}")


def validate_bundle(bundle_dir, component: str = "S11") -> dict:
    """校验桥接包，返回报告。bundle_dir 不存在/缺 manifest 时抛异常。"""
    bundle = Path(bundle_dir)
    mpath = bundle / "manifest.json"
    if not mpath.exists():
        raise FileNotFoundError(f"缺少 manifest.json: {bundle}")
    manifest = json.loads(mpath.read_text(encoding="utf-8"))

    errors: list[str] = []
    warnings: list[str] = []
    checks: dict[str, object] = {}
    points_report: dict[str, dict] = {}

    if manifest.get("schema") != SCHEMA:
        errors.append(f"schema 不是 {SCHEMA}: {manifest.get('schema')!r}")

    units = units_from_manifest(manifest)
    if units.get("problem"):
        warnings.append(f"units: {units['problem']}")

    # ---- 文件清单与哈希 ----
    files = manifest.get("files") or {}
    checks["file_hashes_match"] = True
    if not files:
        errors.append("manifest.files 为空，无法证明导出包完整")
        checks["file_hashes_match"] = False
    listed: set[str] = set()
    for rel, spec in files.items():
        rel_n = _norm_rel(rel)
        listed.add(rel_n)
        p = bundle / rel_n
        if not p.exists():
            errors.append(f"清单列出但文件缺失: {rel_n}")
            checks["file_hashes_match"] = False
            continue
        data = p.read_bytes()
        if len(data) != int(spec.get("bytes", -1)):
            errors.append(f"文件大小不符: {rel_n} "
                          f"({len(data)} != {spec.get('bytes')})")
            checks["file_hashes_match"] = False
        elif _sha256(p) != spec.get("sha256"):
            errors.append(f"SHA-256 不符: {rel_n}")
            checks["file_hashes_match"] = False

    fields_dir = bundle / "fields"
    actual_fields = sorted(p.name for p in fields_dir.glob("*.csv")) \
        if fields_dir.is_dir() else []
    listed_fields = {Path(r).name for r in listed if Path(r).parent.name == "fields"}
    unlisted = [n for n in actual_fields if n not in listed_fields]
    if unlisted:
        errors.append(f"fields/ 下存在清单未列出的文件（可能是重复导出追加）: "
                      + ", ".join(unlisted))
    checks["no_unlisted_field_files"] = not unlisted
    if not actual_fields:
        errors.append("fields/ 下没有历程 CSV")

    # ---- points.csv ----
    pfile = bundle / "points.csv"
    points: list[dict] = []
    ids: list[str] = []
    if not pfile.exists():
        errors.append("缺少 points.csv")
    else:
        with open(pfile, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames or []
            missing = [c for c in POINT_REQUIRED if c not in header]
            if missing:
                errors.append(f"points.csv 缺少列: {missing}")
            points = list(reader)
            ids = [p.get("point_id", "") for p in points]
    checks["point_id_unique"] = len(ids) == len(set(ids)) and "" not in ids
    if not checks["point_id_unique"]:
        dup = sorted({i for i in ids if ids.count(i) > 1})
        errors.append(f"points.csv point_id 重复/为空: {dup[:5]}")
    checks["n_points_match"] = len(ids) == int(manifest.get("n_points", -1))
    if not checks["n_points_match"]:
        errors.append(f"points.csv 点数 {len(ids)} 与清单 "
                      f"{manifest.get('n_points')} 不符")

    # ---- 帧范围 ----
    fr_range = manifest.get("frame_range")
    expected_frames: list[int] = []
    if (not isinstance(fr_range, (list, tuple)) or len(fr_range) != 2
            or not all(_is_num(x) for x in fr_range)):
        errors.append(f"manifest.frame_range 非法: {fr_range!r}")
    else:
        start, end = int(fr_range[0]), int(fr_range[1])
        expected_frames = list(range(start, end + 1))
        if manifest.get("n_frames") not in (None, len(expected_frames)):
            warnings.append(
                f"manifest.n_frames={manifest.get('n_frames')} 与帧范围长度 "
                f"{len(expected_frames)} 不一致")

    # ---- 历程行 ----
    rows_total = 0
    seen: set[tuple[str, int]] = set()
    systems: set[str] = set()
    comp_vals: list[float] = []
    invalid_rows = 0
    nonfinite_rows = 0
    per_point_frames: dict[str, list[int]] = {pid: [] for pid in ids}
    unknown_points: set[str] = set()
    valid_parseable = True
    known_ids = set(ids)

    for name in actual_fields:
        with open(fields_dir / name, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames or []
            missing = [c for c in FIELD_REQUIRED if c not in header]
            if missing:
                errors.append(f"{name} 缺少列: {missing}")
                continue
            if component not in header:
                errors.append(f"{name} 缺少应力分量列 {component}")
            for row in reader:
                rows_total += 1
                pid = row.get("point_id", "")
                if pid not in known_ids:
                    unknown_points.add(pid)
                    continue
                try:
                    frame_id = _parse_int(row.get("frame_id"), "frame_id")
                except ValueError as exc:
                    errors.append(f"{name}: {exc}")
                    continue
                key = (pid, frame_id)
                if key in seen:
                    errors.append(f"组合键重复: point_id={pid}, frame_id={frame_id}")
                seen.add(key)
                per_point_frames[pid].append(frame_id)
                if expected_frames and frame_id not in expected_frames:
                    errors.append(f"帧 {frame_id} 超出 manifest.frame_range")

                cs = str(row.get("coordinate_system", "")).strip()
                if cs:
                    systems.add(cs)
                else:
                    errors.append(f"point_id={pid} frame={frame_id} 缺 coordinate_system")
                try:
                    ok = _parse_valid(row.get("valid"))
                except ValueError as exc:
                    valid_parseable = False
                    errors.append(f"point_id={pid} frame={frame_id}: {exc}")
                    ok = False
                info = points_report.setdefault(
                    pid, {"missing_frames": [], "invalid_frames": [],
                          "nonfinite_frames": []})
                if not ok:
                    invalid_rows += 1
                    info["invalid_frames"].append(frame_id)
                val = row.get(component, "")
                if not _is_num(val):
                    nonfinite_rows += 1
                    info["nonfinite_frames"].append(frame_id)
                else:
                    fv = float(val)
                    if fv != fv or fv in (float("inf"), float("-inf")):
                        nonfinite_rows += 1
                        info["nonfinite_frames"].append(frame_id)
                    else:
                        comp_vals.append(fv)

    if unknown_points:
        errors.append(f"历程中出现未注册材料点: {sorted(unknown_points)[:5]}")
    checks["all_points_present"] = not unknown_points and known_ids.issubset(
        {pid for pid, _ in seen})
    if not checks["all_points_present"]:
        missing = sorted(known_ids - {pid for pid, _ in seen})
        errors.append(f"以下材料点在历程中没有数据: {missing[:5]}")
    checks["valid_flags_parseable"] = valid_parseable

    # 每点帧覆盖
    coverage_ok = True
    for pid, frames in per_point_frames.items():
        got = set(frames)
        missing = [f for f in expected_frames if f not in got]
        info = points_report.setdefault(
            pid, {"missing_frames": [], "invalid_frames": [],
                  "nonfinite_frames": []})
        info["missing_frames"] = missing
        if missing:
            coverage_ok = False
    checks["frame_coverage_complete"] = coverage_ok
    if not coverage_ok:
        bad = [pid for pid, info in points_report.items() if info["missing_frames"]]
        warnings.append(f"{len(bad)} 个材料点帧不完整（分析将逐点排除）: {bad[:5]}")
    checks["row_count_match"] = rows_total == int(manifest.get("n_field_rows", -1))
    if not checks["row_count_match"]:
        errors.append(f"历程行数 {rows_total} 与清单 "
                      f"{manifest.get('n_field_rows')} 不符")
    if len(per_point_frames) != len(ids):
        errors.append("points.csv 与历程中的材料点集合不一致")

    # ---- 应力基底与壳截面点 ----
    shell_points = [p for p in points
                    if str(p.get("section_point_number", "")).strip().lower()
                    not in _EMPTY_SP]
    checks["basis_consistent"] = len(systems) <= 1
    if len(systems) > 1:
        errors.append(f"coordinate_system 不唯一: {sorted(systems)}")
    basis_resolved = bool(systems) and "local-unresolved" not in systems
    if systems and not basis_resolved:
        if shell_points:
            warnings.append("应力基底未解析（local-unresolved）且含壳/梁截面点；"
                            "分析入口将拒绝直接计算，须先声明 --basis global/local")
        else:
            warnings.append("应力基底记为 local-unresolved；实体积分点按全局分量"
                            "使用，若模型使用局部坐标系须重新提取并声明 --basis")

    checks["shell_present"] = bool(shell_points)
    shell_ok = True
    groups: dict[tuple, set] = {}
    for p in shell_points:
        key = (p.get("instance"), str(p.get("element_label")),
               str(p.get("integration_point")))
        groups.setdefault(key, set()).add(str(p.get("section_point_number")).strip())
    # 每个 (实例, 单元, 积分点) 下的截面点必须各自独立；不同积分点不算重复。
    for key, sps in groups.items():
        n_pts = sum(1 for p in shell_points
                    if (p.get("instance"), str(p.get("element_label")),
                        str(p.get("integration_point"))) == key)
        if len(sps) != n_pts:
            shell_ok = False
    checks["shell_sections_separate"] = shell_ok
    if not shell_ok:
        errors.append("壳/梁截面点在同体积分点下发生合并或重复")

    report = {
        "bundle": str(bundle),
        "schema": manifest.get("schema"),
        "component": component,
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
        "passed": not errors,
        "units": units,
        "basis": {
            "coordinate_system": sorted(systems)[0] if len(systems) == 1 else
            (sorted(systems) if systems else None),
            "resolved": basis_resolved,
            "shell_section_points": bool(shell_points),
        },
        "n_points": len(ids),
        "n_frames_expected": len(expected_frames),
        "rows": rows_total,
        "points": points_report,
        "stats": {
            "component": component,
            "component_min": min(comp_vals) if comp_vals else None,
            "component_max": max(comp_vals) if comp_vals else None,
            "invalid_rows": invalid_rows,
            "nonfinite_rows": nonfinite_rows,
            "n_points_missing_frames": sum(
                1 for i in points_report.values() if i["missing_frames"]),
            "n_points_invalid_frames": sum(
                1 for i in points_report.values() if i["invalid_frames"]),
        },
    }
    return report
