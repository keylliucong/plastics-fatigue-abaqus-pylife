"""ODB 只读全历程提取：按材料点（含积分点与壳截面点）导出应力历程桥接包。

运行（目标 Abaqus 2024 环境）：
    abaqus python bridge/odb_extract.py Job.odb Step-1 --region INSTANCE_OR_SET \
        --component S11 --frames 0:-1 --out bundle_dir

遵守 PRD FR-03/FR-04/FR-05：
  - 单时间域分析步；保留原始帧序与 step_time；
  - 实体保留全部积分点；壳截面点按 ODB 实际编号逐点保留，不默认合并/取最大；
  - 不做节点/积分点/跨截面点平均；缺失分量留空，NaN/失效保留标记；
  - STATUS 存在时保留该标志；原ODB只读，不改原文件。

应力/时间单位由用户在 manifest 的 meta 中显式确认；本脚本不臆断单位。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from contract import BundleWriter, COMPONENTS


def _connect():
    from odbAccess import openOdb  # type: ignore
    return openOdb


def _resolve_region(odb, name):
    """大小写不敏感地解析实例名或实例/装配的单元集。"""
    if not name:
        return None, odb.rootAssembly.instances.keys()
    for iname in odb.rootAssembly.instances.keys():
        if iname.upper() == name.upper():
            return odb.rootAssembly.instances[iname], None
    for sname in odb.rootAssembly.elementSets.keys():
        if sname.upper() == name.upper():
            return odb.rootAssembly.elementSets[sname], None
    raise ValueError(f"未找到实例或单元集: {name}")


def extract(odb_path: str, step_name: str, region_name: str, component: str,
            frame_start: int, frame_end: int, out_dir: str, meta: dict) -> dict:
    openOdb = _connect()
    odb = openOdb(path=odb_path, readOnly=True)
    try:
        step = None
        for sname in odb.steps.keys():
            if sname.upper() == step_name.upper():
                step = odb.steps[sname]
                break
        if step is None:
            raise ValueError(f"未找到分析步: {step_name}")
        n = len(step.frames)
        if n < 2:
            raise ValueError("少于两帧，不能作为历程导出（PRD FR-08 准备包条件）")
        start = frame_start if frame_start >= 0 else 0
        end = frame_end if frame_end >= 0 else n - 1
        frames = list(range(start, min(end, n - 1) + 1))

        selected, all_instances = _resolve_region(odb, region_name)

        writer = BundleWriter(
            Path(out_dir),
            manifest_meta={
                "schema": "bridge-bundle-v1",
                "source": odb_path,
                "step": step.name,
                "step_domain": str(getattr(step, "domain", "")),
                "component": component,
                "frame_range": [frames[0], frames[-1]],
                "n_frames": len(frames),
                "units": meta.get("units", {"stress_standard": "UNCONFIRMED",
                                            "time_meaning": "UNCONFIRMED"}),
                "selection": {"region": region_name or "<all instances>"},
                # 元数据用 ASCII，避免 Windows/Mac 跨平台编码差异破坏 JSON 读取。
                "note": "Read-only extraction via abaqus python; units confirmed by user, not assumed.",
            },
        )
        pid_by_key = {}

        for fr in frames:
            frame = step.frames[fr]
            fo_map = frame.fieldOutputs
            if "S" not in fo_map:
                raise ValueError("该帧没有应力场输出 S；不能伪造（PRD FR-02/FR-08）")
            S = fo_map["S"]
            component_labels = list(S.componentLabels)
            if component not in component_labels:
                raise ValueError(f"应力场无分量 {component}; 实际分量: {component_labels}")
            if "STATUS" in fo_map:
                status_fo = fo_map["STATUS"]

            subset = S.getSubset(region=selected) if selected is not None else S
            for v in subset.values:
                inst_name = getattr(v.instance, "name", "ASSEMBLY")
                ip = getattr(v, "integrationPoint", None)
                sp_obj = getattr(v, "sectionPoint", None)
                sp = sp_obj.number if sp_obj is not None else None
                sp_desc = sp_obj.description if sp_obj is not None else None
                key = pid_key(inst_name, v.elementLabel, ip, sp)
                if key not in pid_by_key:
                    pid_by_key[key] = writer.add_point(
                        inst_name, v.elementLabel, ip, sp, sp_desc,
                        str(getattr(v, "elementType", "")),
                        str(getattr(v, "position", "")),
                    )
                pid = pid_by_key[key]

                components = {}
                for label in COMPONENTS:
                    if label in component_labels:
                        val = getattr(v, "data", None)
                        idx = component_labels.index(label)
                        components[label] = _component_value(val, idx)
                valid = _finite(components.get(component))
                status_val = _status_value(status_fo, v, selected, fo_map) \
                    if "STATUS" in fo_map else "not_provided"
                if status_val != "not_provided" and _is_number(status_val) \
                        and float(status_val) <= 0.5:
                    valid = False  # 失效/删除单元：保留行但标记不可用于下游

                writer.add_field(
                    pid, fr, frame.frameValue, str(getattr(v, "position", "")),
                    "local-unresolved",  # 基底/坐标信息未解析，禁止标为可直接用标量
                    components, valid, status_val,
                )

        return writer.finish()
    finally:
        odb.close()


def pid_key(instance, element, ip, sp):
    return (instance, element, ip, sp)


def _component_value(data, idx):
    """提取单个应力分量。

    真实 Abaqus 的 v.data 是 numpy.ndarray（float32/float64），元素为 numpy
    标量，不能只靠 isinstance(val,(int,float)) 判断——那会把真实值误判为空。
    统一用 float() 转换，失败才视为缺失。
    """
    try:
        val = data[idx]
        return float(val)
    except (Exception,):
        return ""


def _finite(v):
    if v is None or v == "":
        return False
    try:
        f = float(v)
        return f == f and f not in (float("inf"), float("-inf"))
    except (TypeError, ValueError):
        return False


def _is_number(v):
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


def _status_value(status_fo, v, selected, fo_map):
    """尽力按同一材料点匹配 STATUS；取不到返回 not_provided，绝不臆断。"""
    try:
        ssub = status_fo.getSubset(region=selected) if selected is not None else status_fo
        for sv in ssub.values:
            if (getattr(sv, "elementLabel", None) == v.elementLabel and
                    getattr(sv, "instance", None) and v.instance and
                    sv.instance.name == v.instance.name):
                return sv.data
    except Exception:
        pass
    return "not_provided"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("odb")
    ap.add_argument("step")
    ap.add_argument("--region", default="")
    ap.add_argument("--component", default="S11")
    ap.add_argument("--frames", default="0:-1", help="start:end，-1 表示末帧")
    ap.add_argument("--out", default="bridge_bundle")
    ap.add_argument("--meta", default="", help="JSON 文件：单位/时间含义等用户确认信息")
    args = ap.parse_args(argv)
    fs, fe = (int(x) for x in args.frames.split(":"))
    meta = json.loads(Path(args.meta).read_text(encoding="utf-8")) if args.meta else {}
    manifest = extract(args.odb, args.step, args.region, args.component, fs, fe,
                       args.out, meta)
    print(f"提取完成: {args.out}; 点数={manifest['n_points']}, 行数={manifest['n_field_rows']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
