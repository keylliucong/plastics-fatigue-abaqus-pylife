# pyLife 虚拟数据接口核验

返回 [[塑胶疲劳仿真技术SOP — 工作稿]]。本例只演示 pyLife 2.3.1 接口与手算一致性；不读取 ODB、不建立 PC/ABS 材料卡、不输出完整寿命。数据、参数和单位均为教学假设。

文件：[pylife_synthetic_check.py](pylife_synthetic_check.py)。在 Python 虚拟环境安装 `pylife==2.3.1` 后运行：

```text
python pylife_synthetic_check.py
```

虚拟历程是 `[0, 10, -10, 10, -10, 10, -10, 0]` MPa。三点算法和 `FullRecorder` 输出两个已闭合循环，均为 -10 → 10 MPa、幅值 10 MPa；记录器同时给出原始数组索引。虚拟 Wöhler 曲线设置 $k_1=k_2=5$、$S_D=10$ MPa、$N_D=10^6$，每个闭合循环按 $1/N_f$ 得到损伤 $10^{-6}$，合计 $2\times10^{-6}$。软件会额外列出尚未闭合的残余转折点。

**边界**：这里的合计只覆盖已闭合循环，残余被明确排除，不能作为有限记录的总损伤或重复谱块寿命。真实项目需预先规定残余半循环、分块拼接和谱块重复的处理，针对预期结果独立验证；不得简单以本例乘重复数。曲线和均值应力也必须用目标材料试验支持。

2026-11-16 已在本机 macOS、Python 3.12、pyLife 2.3.1 上运行并通过脚本断言；这不是 Windows 或 Abaqus 2024 的兼容性验证。参考 [ThreePointDetector 官方文档](https://pylife.readthedocs.io/en/2.3.1/stress/rainflow/threepointdetector.html)、[FullRecorder 官方文档](https://pylife.readthedocs.io/en/2.3.1/stress/rainflow/fullrecorder.html)、[WoehlerCurve 官方文档](https://pylife.readthedocs.io/en/2.3.1/materiallaws/woehlercurve.html)。
