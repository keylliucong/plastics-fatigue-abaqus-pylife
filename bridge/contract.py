"""桥接包数据契约（PRD v1）写入：points.csv + fields/*.csv + manifest + 校验。

纯标准库实现，被 odb_extract.py（Abaqus Python）与本机 mock 测试共用。
关键约束（PRD FR-03/FR-04/FR-05）：
  - point_id = instance + element_label + integration_point + section_point，包内唯一；
  - 不做节点平均、积分点平均、跨截面点合并；
  - 缺失分量/NaN/失效单元保留标记，不补零、不静默删行；
  - 原始基底与坐标系信息可追溯；
  - 先写入暂存目录并通过结构校验，再发布为目标目录，避免半成品/旧数据混入。
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
from pathlib import Path

COMPONENTS = ("S11", "S22", "S33", "S12", "S13", "S23")


def point_id(instance: str, element_label: int, integration_point, section_point) -> str:
    """构造稳定、唯一的材料点键。无截面点用显式空串语义。"""
    sp = "" if section_point is None else str(section_point)
    ip = "" if integration_point is None else str(integration_point)
    return f"{instance}::{element_label}::{ip}::{sp}"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class BundleWriter:
    """增量写入桥接包，校验通过后再发布为带文件哈希的完整包。"""

    FIELD_HEADER = [
        "point_id", "frame_id", "step_time", "output_position",
        "coordinate_system", *COMPONENTS, "valid", "status",
    ]

    STAGE_NAME = ".publish-staging"

    def __init__(self, out_dir: Path, manifest_meta: dict, chunk_rows: int = 1_000_000,
                 overwrite: bool = False):
        self.out = Path(out_dir)
        self.chunk_rows = chunk_rows
        self.meta = dict(manifest_meta)
        self.overwrite = overwrite
        self._guard_existing()
        self.stage = self.out / self.STAGE_NAME
        if self.stage.exists():
            shutil.rmtree(self.stage)
        (self.stage / "fields").mkdir(parents=True)
        self.points: list[dict] = []
        self._seen_ids: set[str] = set()
        self._field_files: list[Path] = []
        self._chunk: list[list] = []
        self._row_count = 0

    def _guard_existing(self):
        """默认拒绝覆盖已有导出包；显式 overwrite 时才允许替换。"""
        existing = []
        if (self.out / "points.csv").exists():
            existing.append("points.csv")
        if (self.out / "manifest.json").exists():
            existing.append("manifest.json")
        fields = self.out / "fields"
        if fields.is_dir() and any(fields.glob("part-*.csv")):
            existing.append("fields/part-*.csv")
        if existing and not self.overwrite:
            raise ValueError(
                f"输出目录已存在桥接包（{', '.join(existing)}）: {self.out}；"
                "请换新目录，或显式使用 --overwrite 覆盖（避免追加出脏数据）")

    def add_point(self, instance, element_label, integration_point, section_point,
                  section_description, element_type, output_position) -> str:
        pid = point_id(instance, element_label, integration_point, section_point)
        if pid in self._seen_ids:
            raise ValueError(f"point_id 重复，违反包内唯一性: {pid}")
        self._seen_ids.add(pid)
        self.points.append({
            "point_id": pid,
            "instance": instance,
            "element_label": int(element_label),
            "integration_point": integration_point,
            "section_point_number": section_point,
            "section_point_description": section_description,
            "element_type": element_type,
            "output_position": output_position,
        })
        return pid

    def add_field(self, pid: str, frame_id: int, step_time, output_position,
                  coordinate_system, components: dict, valid: bool, status):
        if pid not in self._seen_ids:
            raise ValueError(f"未注册的材料点: {pid}")
        row = [pid, int(frame_id), step_time, output_position, coordinate_system]
        row += [components.get(c, "") for c in COMPONENTS]  # 缺失分量留空，不补零
        row += ["true" if valid else "false", status]
        self._chunk.append(row)
        self._row_count += 1
        if len(self._chunk) >= self.chunk_rows:
            self._flush_chunk()

    def _flush_chunk(self):
        if not self._chunk:
            return
        n = len(self._field_files) + 1
        path = self.stage / "fields" / f"part-{n:06d}.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(self.FIELD_HEADER)
            w.writerows(self._chunk)
        self._field_files.append(path)
        self._chunk = []

    def finish(self) -> dict:
        self._flush_chunk()
        if not self.points:
            raise ValueError("未提取到任何材料点；拒绝发布空导出包")
        points_path = self.stage / "points.csv"
        with open(points_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(self.points[0].keys()))
            w.writeheader()
            w.writerows(self.points)

        files = {"points.csv": self._file_spec(points_path)}
        for p in self._field_files:
            rel = p.relative_to(self.stage).as_posix()
            files[rel] = self._file_spec(p)
        manifest = dict(self.meta)
        manifest["n_points"] = len(self.points)
        manifest["n_frames"] = self.meta.get("n_frames")
        manifest["n_field_rows"] = self._row_count
        manifest["files"] = files
        manifest_path = self.stage / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")

        # 校验通过后才发布；失败时保留暂存目录供排查，且不破坏已有包。
        from bundle_validation import validate_bundle
        report = validate_bundle(self.stage, component=str(
            self.meta.get("component", "S11")))
        problems = list(report["errors"])
        if not report["checks"].get("frame_coverage_complete", False):
            bad = [pid for pid, info in report["points"].items()
                   if info.get("missing_frames")]
            problems.append(f"材料点帧覆盖不完整（提取过程丢帧）: {bad[:5]}")
        if problems:
            raise RuntimeError(
                "导出包校验失败，未发布: " + "；".join(problems[:6])
                + f"（暂存目录: {self.stage}）")
        self._publish()
        return manifest

    @staticmethod
    def _file_spec(path: Path) -> dict:
        return {"bytes": path.stat().st_size, "sha256": _sha256(path)}

    def _publish(self):
        out_fields = self.out / "fields"
        out_fields.mkdir(parents=True, exist_ok=True)
        new_names = [p.name for p in sorted((self.stage / "fields").glob("*.csv"))]
        # 覆盖模式下清掉上一版多出来的分块，防止新旧行数混在一起。
        for old in out_fields.glob("part-*.csv"):
            if old.name not in new_names:
                old.unlink()
        for name in new_names:
            os.replace(self.stage / "fields" / name, out_fields / name)
        os.replace(self.stage / "points.csv", self.out / "points.csv")
        # manifest 最后替换：中途失败时旧清单仍在，校验会明确报错而不是静默通过。
        os.replace(self.stage / "manifest.json", self.out / "manifest.json")
        shutil.rmtree(self.stage, ignore_errors=True)
        self._field_files = [out_fields / n for n in new_names]
