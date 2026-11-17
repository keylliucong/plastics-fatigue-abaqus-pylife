# pyLife 虚拟数据接口核验

返回 [[塑胶疲劳仿真技术SOP — 工作稿]]。本例只演示 pyLife 2.3.1 接口与手算一致性；不读取 ODB、不建立 PC/ABS 材料卡、不输出完整寿命。数据、参数和单位均为教学假设。

文件：[pylife_synthetic_check.py](pylife_synthetic_check.py)。在 Python 虚拟环境安装 `pylife==2.3.1` 后运行：

```text
python pylife_synthetic_check.py
```

虚拟历程是 `[0, 10, -10, 10, -10, 10, -10, 0]` MPa。三点算法和 `FullRecorder` 输出两个已闭合循环，均为 -10 → 10 MPa、幅值 10 MPa；记录器同时给出原始数组索引。虚拟 Wöhler 曲线设置 $k_1=k_2=5$、$S_D=10$ MPa、$N_D=10^6$，每个闭合循环按 $1/N_f$ 得到损伤 $10^{-6}$，合计 $2\times10^{-6}$。软件会额外列出尚未闭合的残余转折点。

**边界**：这里的合计只覆盖已闭合循环，残余被明确排除，不能作为有限记录的总损伤或重复谱块寿命。真实项目需预先规定残余半循环、分块拼接和谱块重复的处理，针对预期结果独立验证；不得简单以本例乘重复数。曲线和均值应力也必须用目标材料试验支持。

2026-11-16 已在本机 macOS、Python 3.12、pyLife 2.3.1 上运行并通过脚本断言；这不是 Windows 或 Abaqus 2024 的兼容性验证。参考 [ThreePointDetector 官方文档](https://pylife.readthedocs.io/en/2.3.1/stress/rainflow/threepointdetector.html)、[FullRecorder 官方文档](https://pylife.readthedocs.io/en/2.3.1/stress/rainflow/fullrecorder.html)、[WoehlerCurve 官方文档](https://pylife.readthedocs.io/en/2.3.1/materiallaws/woehlercurve.html)。

## 分块处理：跨块状态不能丢失

对同一虚构数组 `[0, 10, -10, 10, -10, 10, -10, 0]`，在第4个样本后分成两块：

| 方法 | 已闭合循环 | 解释 |
|---|---:|---|
| 整段输入一个检测器 | 2 | 参考结果 |
| 两块依次输入同一个检测器，前块 `flush=False`、末块 `flush=True` | 2 | 本例与整段相同 |
| 每块都新建检测器，分别 `flush=True` | 0 + 0 | 跨块闭合循环未被识别；两块各自仍有残余 |

三个结果仅统计 `FullRecorder` 已闭合循环，**不含残余半循环**，也不是完整载荷块寿命。块边界不应人为重复或漏掉样本；流式算法应跨块保留同一个检测器对象及其状态。`flush=True` 是处理缓存的接口选项，不等同于直接把所有残余自动转换成半循环；每块重复调用它是否改变结果取决于具体输入和实现，不能单凭本例一概判断。末尾残余、循环块重复和有限记录的半循环权重需要明确约定并单独验证。

示例脚本现已分别运行三种情况并核对本例结果；这不替代对实际记录分块边界的回归检查。
