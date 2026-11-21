"""ODB 只读扫描：列出步骤/帧/实例/单元类型/集合/场变量/分量/位置/截面点。

运行（目标 Abaqus 2024 环境）：
    abaqus python bridge/odb_probe.py Job.odb [--out inventory.json]

仅写清单 JSON，不加载全部场历程，不修改 ODB。名称在 ODB 中为大写，查找时大小写不敏感。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path


def _connect():
    # 在 Abaqus Python 中运行；本机 mock 测试会注入同名模块。
    from odbAccess import openOdb  # type: ignore
    return openOdb


def file_fingerprint(path: str) -> dict:
    try:
        st = os.stat(path)
        return {"bytes": st.st_size, "mtime": st.st_mtime}  # 不强制每次全量哈希大型 ODB
    except OSError:
        return {"bytes": None, "mtime": None, "note": "文件不可 stat（如 mock 测试）"}


def probe(odb_path: str) -> dict:
    openOdb = _connect()
    odb = openOdb(path=odb_path, readOnly=True)
    try:
        steps = []
        for sname in odb.steps.keys():
            step = odb.steps[sname]
            frames = [{"frame_id": i, "frame_value": fr.frameValue}
                      for i, fr in enumerate(step.frames)]
            fields = {}
            if step.frames:
                for vname, fo in step.frames[0].fieldOutputs.items():
                    positions = sorted({str(v.position) for v in fo.values})
                    section_points = sorted({
                        str(v.sectionPoint.number)
                        for v in fo.values if getattr(v, "sectionPoint", None)
                    })
                    fields[vname] = {
                        "componentLabels": list(fo.componentLabels),
                        "positions": positions,
                        "sectionPoints": section_points,
                        "n_values_frame0": len(fo.values),
                    }
            steps.append({
                "name": sname, "domain": str(getattr(step, "domain", "")),
                "n_frames": len(step.frames), "frames": frames,
                "fieldOutputs": fields,
            })

        instances = []
        for iname in odb.rootAssembly.instances.keys():
            inst = odb.rootAssembly.instances[iname]
            etypes = sorted({str(e.type) for e in inst.elements})
            instances.append({
                "name": iname, "n_elements": len(inst.elements),
                "element_types": etypes,
                "element_sets": list(inst.elementSets.keys()),
                "node_sets": list(inst.nodeSets.keys()),
            })

        return {
            "schema": "odb-inventory-v1",
            "source_path": odb_path,
            "fingerprint": file_fingerprint(odb_path),
            "odb_creation": str(getattr(odb, "creationTime", "")),
            "steps": steps,
            "instances": instances,
            "assembly_element_sets": list(odb.rootAssembly.elementSets.keys()),
        }
    finally:
        odb.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("odb")
    ap.add_argument("--out", default="odb_inventory.json")
    args = ap.parse_args(argv)
    inv = probe(args.odb)
    Path(args.out).write_text(json.dumps(inv, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
    print(f"扫描完成: {args.out}; 步骤数={len(inv['steps'])}, 实例数={len(inv['instances'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
