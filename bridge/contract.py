"""桥接包数据契约（PRD v1）写入：points.csv + fields/*.csv + manifest + 校验。

纯标准库实现，被 odb_extract.py（Abaqus Python）与本机 mock 测试共用。
关键约束（PRD FR-03/FR-04）：
  - point_id = instance + element_label + integration_point + section_point，包内唯一；
  - 不做节点平均、积分点平均、跨截面点合并；
  - 缺失分量/NaN/失效单元保留标记，不补零、不静默删行；
  - 原始基底与坐标系信息可追溯。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import csv

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
    """增量写入桥接包，最后生成带文件哈希的 manifest。"""

    FIELD_HEADER = [
        "point_id", "frame_id", "step_time", "output_position",
        "coordinate_system", *COMPONENTS, "valid", "status",
    ]

    def __init__(self, out_dir: Path, manifest_meta: dict, chunk_rows: int = 1_000_000):
        self.out = Path(out_dir)
        self.chunk_rows = chunk_rows
        self.meta = dict(manifest_meta)
        self.points: list[dict] = []
        self._seen_ids: set[str] = set()
        self._field_files: list[Path] = []
        self._chunk: list[list] = []
        self._row_count = 0

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
        path = self.out / "fields" / f"part-{n:06d}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not path.exists()
        with open(path, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if write_header:
                w.writerow(self.FIELD_HEADER)
            w.writerows(self._chunk)
        self._field_files.append(path)
        self._chunk = []

    def finish(self) -> dict:
        self._flush_chunk()
        (self.out / "points.csv").parent.mkdir(parents=True, exist_ok=True)
        with open(self.out / "points.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(self.points[0].keys()))
            w.writeheader()
            w.writerows(self.points)

        files = {}
        for rel in ("points.csv", *[str(p.relative_to(self.out)) for p in self._field_files]):
            p = self.out / rel
            files[rel] = {"bytes": p.stat().st_size, "sha256": _sha256(p)}
        manifest = dict(self.meta)
        manifest["n_points"] = len(self.points)
        manifest["n_frames"] = self.meta.get("n_frames")
        manifest["n_field_rows"] = self._row_count
        manifest["files"] = files
        (self.out / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return manifest
