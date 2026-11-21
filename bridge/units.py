"""应力/时间单位登记与换算（纯标准库；Abaqus Python 与本机共用）。

原则：
  - 提取端只登记源单位，保留 ODB 原始数值，不做任何隐式换算；
  - 源单位与换算系数写入 manifest.units，下游统一换算到 MPa；
  - 单位缺失或无法识别时返回 None/UNCONFIRMED，分析入口必须拒绝计算，
    不得把 Pa 数值当成 MPa 使用。
"""

from __future__ import annotations


def _norm_key(value: str) -> str:
    return (str(value).strip().replace(" ", "").replace("^", "")
            .replace("²", "2").lower())


# 规范名 -> 换算到 MPa 的系数
STRESS_SCALE_TO_MPA = {
    "MPa": 1.0,
    "Pa": 1e-6,
    "kPa": 1e-3,
    "GPa": 1e3,
    "N/mm2": 1.0,
    "N/m2": 1e-6,
    "psi": 6894.757293168e-6,
    "ksi": 6.894757293168,
}

TIME_SCALE_TO_S = {"s": 1.0, "ms": 1e-3, "min": 60.0, "h": 3600.0}

_STRESS_LOOKUP = {_norm_key(k): k for k in STRESS_SCALE_TO_MPA}
_TIME_LOOKUP = {_norm_key(k): k for k in TIME_SCALE_TO_S}

_UNCONFIRMED = {"", "unconfirmed", "unknown", "?", "n/a", "na", "none"}


def canonical_stress_unit(unit) -> str | None:
    """返回规范应力单位名；空/UNCONFIRMED 返回 None；无法识别抛 ValueError。"""
    if unit is None:
        return None
    key = _norm_key(unit)
    if key in _UNCONFIRMED:
        return None
    canonical = _STRESS_LOOKUP.get(key)
    if canonical is None:
        raise ValueError(
            f"无法识别的源应力单位: {unit!r}；支持 "
            + "、".join(sorted(STRESS_SCALE_TO_MPA)))
    return canonical


def stress_scale_to_mpa(unit) -> float | None:
    canonical = canonical_stress_unit(unit)
    if canonical is None:
        return None
    return STRESS_SCALE_TO_MPA[canonical]


def canonical_time_unit(unit) -> str | None:
    if unit is None:
        return None
    key = _norm_key(unit)
    if key in _UNCONFIRMED:
        return None
    canonical = _TIME_LOOKUP.get(key)
    if canonical is None:
        # 时间单位不影响损伤数值，但必须原样保留，不能臆断。
        return str(unit).strip()
    return canonical


def _units_mapping(obj) -> dict:
    """兼容 {"units": {...}} 与扁平 {...} 两种元数据形态。"""
    if obj is None:
        return {}
    if not isinstance(obj, dict):
        raise ValueError(f"单位元数据必须是 dict，实际: {type(obj).__name__}")
    inner = obj.get("units")
    if isinstance(inner, dict):
        return inner
    return obj


def normalize_units(meta) -> dict:
    """规范化提取端传入的单位元数据；无法识别的单位立即报错。"""
    u = _units_mapping(meta)
    # 只认显式的 stress_source；stress_standard 是目标单位，不能反推源单位。
    src = canonical_stress_unit(u.get("stress_source"))
    scale = STRESS_SCALE_TO_MPA[src] if src else None
    time_src = canonical_time_unit(u.get("time_source"))
    meaning = str(u.get("time_meaning") or "unknown").strip() or "unknown"
    return {
        "stress_source": src or "UNCONFIRMED",
        "stress_standard": "MPa",
        "stress_scale_to_MPa": scale,
        "time_source": time_src or "UNCONFIRMED",
        "time_meaning": meaning,
    }


def units_from_manifest(manifest) -> dict:
    """从 manifest 读取单位与换算系数；不抛错，把问题放进 problem。

    兼容旧包：只记录 stress_standard 而没有 stress_source 时，不能假定
    源数值就是 MPa——按未确认处理，由分析入口拒绝计算。
    """
    u = _units_mapping((manifest or {}).get("units"))
    raw_src = u.get("stress_source")
    problem = None
    scale = None
    src = None
    if raw_src is None or str(raw_src).strip() == "":
        problem = "manifest 未记录源应力单位（stress_source）"
    else:
        try:
            src = canonical_stress_unit(raw_src)
            scale = STRESS_SCALE_TO_MPA[src] if src else None
            if src is None:
                problem = f"源应力单位未确认: {raw_src!r}"
        except ValueError as exc:
            problem = str(exc)
    time_src = canonical_time_unit(u.get("time_source"))
    return {
        "stress_source": src or (str(raw_src).strip() if raw_src else "UNCONFIRMED"),
        "stress_standard": "MPa",
        "stress_scale_to_MPa": scale,
        "time_source": time_src or "UNCONFIRMED",
        "time_meaning": str(u.get("time_meaning") or "unknown"),
        "problem": problem,
    }


def to_mpa(values, unit):
    """把应力序列换算到 MPa（纯 Python 列表）。"""
    scale = stress_scale_to_mpa(unit)
    if scale is None:
        raise ValueError(f"源应力单位未确认，拒绝换算: {unit!r}")
    return [float(v) * scale for v in values]
