"""最小 odbAccess/abaqusConstants 模拟：用于在本机验证桥梁提取逻辑。

它构造一个含实体积分点、壳上下截面点、STATUS、删除单元、NaN 与多帧的假 ODB，
接口与真实 odbAccess 对齐（只覆盖 bridge 脚本用到的调用）。
这不是真实 Abaqus 结果，只是逻辑自测夹具。
"""

import sys
import types

import numpy as np  # 真实 ODB 的 v.data 是 numpy 数组，mock 也用 numpy 以覆盖该路径

POS_INTEGRATION = "INTEGRATION_POINT"


class _Point:
    def __init__(self, number, description):
        self.number = number
        self.description = description


class _Value:
    def __init__(self, instance, element, ip, sp, data, position=POS_INTEGRATION,
                 etype="C3D8R"):
        self.instance = instance
        self.elementLabel = element
        self.integrationPoint = ip
        self.sectionPoint = sp
        self.data = data
        self.position = position
        self.elementType = etype
        self.nodeLabel = None


class _FieldOutput:
    def __init__(self, values, componentLabels=()):
        self.values = values
        self.componentLabels = list(componentLabels)

    def getSubset(self, region=None):
        if region is None:
            return self
        # region 可为实例对象或单元集(list of values)
        if isinstance(region, list):
            return _FieldOutput(list(region), self.componentLabels)
        return _FieldOutput([v for v in self.values if v.instance is region],
                            self.componentLabels)


class _Frame:
    def __init__(self, frame_value, field_outputs):
        self.frameValue = frame_value
        self.fieldOutputs = field_outputs


class _Step:
    def __init__(self, name, domain, frames):
        self.name = name
        self.domain = domain
        self.frames = frames


class _Instance:
    def __init__(self, name, elements):
        self.name = name
        self.elements = elements
        self.elementSets = {}
        self.nodeSets = {}


class _Assembly:
    def __init__(self, instances, element_sets):
        self.instances = {i.name: i for i in instances}
        self.elementSets = element_sets


class _Odb:
    def __init__(self, path, readOnly=True):
        self.path = path
        self.closed = False
        self.creationTime = "mock"
        inst_solid = _Instance("PART-1", [_Elem(1, "C3D8R")])
        inst_shell = _Instance("SHELL-1", [_Elem(2, "S4R")])
        self.rootAssembly = _Assembly([inst_solid, inst_shell], {})
        pts = [_Point(1, "TOP"), _Point(2, "BOTTOM")]
        frames = []
        # 三个材料点：实体1点、壳上、壳下；四点应力张量按 S11..S23 顺序。
        for i in range(4):
            t = float(i)
            svals = {
                ("PART-1", 1, 1, None): [10.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                ("SHELL-1", 2, 1, 1): [8.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                ("SHELL-1", 2, 1, 2): [6.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            }
            S_values = []
            for (iname, elem, ip, sp), data in svals.items():
                inst = self.rootAssembly.instances[iname]
                sp_obj = None
                if sp is not None:
                    sp_obj = pts[sp - 1]
                if i == 3 and iname == "SHELL-1" and sp == 2:
                    data = [float("nan"), 0.0, 0.0, 0.0, 0.0, 0.0]  # NaN 保留
                data = np.array(data, dtype=np.float32)  # 与真实 Abaqus 一致
                S_values.append(_Value(inst, elem, ip, sp_obj, data,
                                       etype="C3D8R" if iname == "PART-1" else "S4R"))
            status_values = [
                _Value(self.rootAssembly.instances["PART-1"], 1, 1, None, 1.0),
                _Value(self.rootAssembly.instances["SHELL-1"], 2, 1, pts[0], 1.0),
                _Value(self.rootAssembly.instances["SHELL-1"], 2, 1, pts[1], 0.0),  # 失效
            ]
            fo = {
                "S": _FieldOutput(S_values, ["S11", "S22", "S33", "S12", "S13", "S23"]),
                "STATUS": _FieldOutput(status_values),
            }
            frames.append(_Frame(t, fo))
        self.steps = {"Load": _Step("Load", "TIME", frames)}

    def close(self):
        self.closed = True


class _Elem:
    def __init__(self, label, type):
        self.label = label
        self.type = type


def install():
    mod = types.ModuleType("odbAccess")
    mod.openOdb = lambda path, readOnly=True: _Odb(path, readOnly)
    sys.modules["odbAccess"] = mod
    const = types.ModuleType("abaqusConstants")
    const.MISES = "MISES"
    const.INTEGRATION_POINT = POS_INTEGRATION
    sys.modules["abaqusConstants"] = const
