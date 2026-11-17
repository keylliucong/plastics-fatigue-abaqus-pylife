"""pyLife 2.3.1 最小接口核验：虚拟数据，不读取 ODB，不预测实际寿命。"""
import importlib.metadata
import numpy as np
import pandas as pd
import pylife.stress.rainflow as rainflow
from pylife.materiallaws import WoehlerCurve


def main():
    # MPa: 仅作为单轴、有符号应力的教学历程。
    stress = np.array([0., 10., -10., 10., -10., 10., -10., 0.])
    if not np.all(np.isfinite(stress)):
        raise ValueError("历程含 NaN 或无穷值；请排查来源，禁止静默删除。")

    detector = rainflow.ThreePointDetector(rainflow.FullRecorder())
    detector.process(stress, flush=True)
    loops = detector.recorder.collective.copy()
    loops["amplitude_MPa"] = (loops["to"] - loops["from"]).abs() / 2.0
    loops["mean_MPa"] = (loops["to"] + loops["from"]) / 2.0

    # 分块只改变数据传输，不应丢失检测器状态。此例不核算残余。
    chunks = [stress[:4], stress[4:]]
    streamed = rainflow.ThreePointDetector(rainflow.FullRecorder())
    streamed.process(chunks[0], flush=False)
    streamed.process(chunks[1], flush=True)
    assert np.allclose(streamed.recorder.collective[["from", "to"]],
                       detector.recorder.collective[["from", "to"]])
    assert np.allclose(streamed.residuals, detector.residuals)
    separate_counts = []
    for chunk in chunks:
        separate = rainflow.ThreePointDetector(rainflow.FullRecorder())
        separate.process(chunk, flush=True)
        separate_counts.append(len(separate.recorder.collective))
    assert separate_counts == [0, 0]
    print("Whole vs stateful chunks closed loops:", len(loops),
          len(streamed.recorder.collective), "; independent chunks:", separate_counts)

    # 完全虚构的单段幂律，不代表 PC/ABS；显式指定拐点后斜率。
    curve = WoehlerCurve(pd.Series({"k_1": 5., "ND": 1e6, "SD": 10., "k_2": 5.}))
    loops["Nf_synthetic"] = curve.basquin_cycles(loops["amplitude_MPa"])
    loops["closed_loop_damage"] = 1.0 / loops["Nf_synthetic"]

    # 验证接口和人工手算，不代表此有限记录的完整损伤。
    assert len(loops) == 2
    assert np.allclose(loops["amplitude_MPa"], [10., 10.])
    assert np.allclose(loops["Nf_synthetic"], [1e6, 1e6])
    assert np.isclose(loops["closed_loop_damage"].sum(), 2e-6)
    print("pyLife version:", importlib.metadata.version("pylife"))
    print("Closed loops only, virtual input (MPa):")
    print(loops.to_string(index=False))
    print("Unclosed residual turning points:", detector.residuals.tolist())
    print("Closed-loop damage subtotal:", loops["closed_loop_damage"].sum())
    print("Residuals excluded; no total life or real-material result is claimed.")


if __name__ == "__main__":
    main()
