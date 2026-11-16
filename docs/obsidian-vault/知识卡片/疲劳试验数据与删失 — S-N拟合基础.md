---
类型: 理论知识卡
状态: 工作稿
主题: 疲劳试验 S-N 删失 概率
---
# 疲劳试验数据与删失：S–N 拟合基础

返回 [[塑胶疲劳知识地图]] · [[塑胶疲劳仿真技术SOP — 工作稿]]。

## 1. 每条记录是什么

每个试样是一条独立记录：材料牌号、批次、成型工艺及取向，几何尺寸，加载控制与波形，频率，$\sigma_{max}$、$\sigma_{min}$，试样温度和环境，停机循环数及是否按失效判据破坏。针对不同失效模式记录断口、温升、永久变形与刚度变化；不要把热失稳、蠕变断裂和裂纹疲劳未经判断混为同一条曲线。

应力范围 $\Delta\sigma=\sigma_{max}-\sigma_{min}$，应力幅值 $\sigma_a=\Delta\sigma/2$，平均应力 $\sigma_m=(\sigma_{max}+\sigma_{min})/2$，常用应力比 $R=\sigma_{min}/\sigma_{max}$。保存原始上下限，引用来源时核对各作者的 $R$ 定义及 $N$ 是否表示完整循环数；$\sigma_{max}=0$ 时应力比不可直接计算。

**手算**：若 $\sigma_{max}=30$ MPa、$\sigma_{min}=10$ MPa，则范围20 MPa、幅值10 MPa、平均20 MPa、$R=1/3$。例如图轴是范围而疲劳模型输入要求幅值时，直接填20会使 $k=5$ 幂律下的单次损伤放大 $2^5=32$ 倍。

## 2. 拟合曲线与试验范围

在明确工艺、温度、频率、应力比及失效定义的一段有效区间，可用 Basquin 经验式 $S_a=A N_f^b$，通常 $b<0$。改写为 $N_f=N_D(S_D/S_a)^k$ 时 $k=-1/b$。这里 $S_D,N_D$ 是该表示法的参考点，不必声称它们已经证明真实耐久极限。多个应力水平和重复试样是估计趋势与离散的基础；只用均值和“±”不能重建每条原始记录。

疲劳寿命的对数正态假设可用于举例：设 $Y_i=\log N_{f,i}$，均值 $\mu_i=\log N_D+k(\log S_D-\log S_{a,i})$，标准差为 $s>0$。这是候选统计模型，需要检查残差与拟合区间；材料可能存在分段曲线、异方差或不同失效机理，不能把此分布当作物理定律。

## 3. 为什么 run-out 是右删失

未断试样在 $C_i$ 次停机只说明其寿命 $N_{f,i}>C_i$，不是 $N_{f,i}=C_i$，更不是“无限寿命”。对独立试样、给定载荷条件和非信息性右删失，采用寿命概率密度 $f_N$ 与累积分布函数 $F_N$ 时，示意似然可写为：

$$L(\theta)=\prod_{i:\,\text{破坏}} f_N(N_i\mid S_i,\theta)\;\prod_{j:\,\text{run-out}}\left[1-F_N(C_j\mid S_j,\theta)\right].$$

破坏记录贡献密度，run-out 贡献“寿命超过截止点”的概率。[NIST 对删失寿命似然的说明](https://www.itl.nist.gov/div898/handbook/apr/section4/apr412.htm)给出相应原理。若用 $\log N$ 的正态密度表示，须使用一致的变量尺度；在比较不同参数的最大似然时，变换的 Jacobian 应正确处理。

示例：某幅值下两件试样分别在 $80,000$ 次破坏和 $100,000$ 次未破坏，数据不能写成两个破坏寿命 80,000、100,000 次。第二件寿命可能为110,000，也可能更长；仅有两条数据不足以可靠估计分布尾部。

## 4. 对接 pyLife 2.3.1

[FatigueData 源码](https://pylife.readthedocs.io/en/2.3.1/_modules/pylife/materialdata/woehler/fatigue_data.html)定义 `load`、`cycles`、`fracture` 三列，`fracture=True` 表示破坏，`False` 表示 run-out；应由原始试验记录给出。演示代码中的 `determine_fractures` 可按截断循环数推测，但不能用它替代真实记录；最大循环数的试样也可能恰好发生破坏。

pyLife 具体分析器对有限寿命区、转折区和 run-out 的筛选与统计假设各不相同；上面的通用右删失似然**不是声称任意 pyLife 函数都使用完全相同的似然**。使用前阅读所选版本和分析器的官方文档、确认其实际分区规则，检查样本量与离散；缺少 run-out、破坏标记、重复试样或混合应力比时，不自动生成可信失效概率。

### 4.1 自动分区可能改变拟合样本：已运行的例子

下面是 pyLife **2.3.1** 中 `FatigueData` 的教学演示，数据完全虚构、载荷统一为应力幅 MPa：

| 载荷幅值 | 循环数 | 结果 |
|---:|---:|---|
| 8 | 1,000,000 | run-out |
| 10 | 1,000,000 | run-out |
| 10 | 400,000 | 破坏 |
| 12 | 120,000 | 破坏 |
| 14 | 45,000 | 破坏 |

复现数据和默认分区：

```python
import pandas as pd
import pylife.materialdata.woehler  # 注册 fatigue_data 访问器

df = pd.DataFrame({
    "load": [8., 10., 10., 12., 14.],
    "cycles": [1e6, 1e6, 4e5, 1.2e5, 4.5e4],
    "fracture": [False, False, True, True, True],
})
fd = df.fatigue_data
print(fd.finite_infinite_transition)
print(fd.finite_zone)
print(fd.infinite_zone)
```

在本地 pyLife 2.3.1 中运行该数据后：默认推测的 `finite_infinite_transition` 为 11 MPa；然而默认的 `finite_zone` 含 12、14 MPa 两条破坏记录，而 8 MPa run-out、10 MPa run-out **及 10 MPa 破坏记录**均被放入 `infinite_zone`。该版本源码先用**最高 run-out 载荷**划分，再将它与其上最近的有限区载荷取中点作为报告的初始转折值；因而此例 10 MPa 的破坏点没有进入有限区回归。不能把“自动转折点 11 MPa”理解为试验已证明的塑胶耐久极限。

若调用 `set_finite_infinite_transition(9.0)`，本例有限区会包含 10、12、14 MPa 三条破坏记录。这只是揭示算法对输入分区的敏感性，**不是建议把转折点设为 9 MPa**：人为设置也必须有试验依据、报告敏感性，并检查这个划分是否适合所选择的分析器及其统计假设。

因此运行 `Elementary`、`Probit` 或最大似然分析器前，必须输出并审查原始记录、破坏/run-out 标签、默认转折值、有限区及另一分区的每条记录；将该工作流称作有限/无限区只是 pyLife 的算法术语，不能自动宣称塑胶具有无限寿命。若研究需要直接估计含删失数据的单段 S–N 模型，应选择**确实实现该似然的拟合方法**并验证，而不能把通用删失似然套称为该分析器的实现。

依据：[pyLife 2.3.1 分析器示例](https://pylife.readthedocs.io/en/2.3.1/demos/woehler_analyzer.html)、[FatigueData 2.3.1 源码](https://pylife.readthedocs.io/en/2.3.1/_modules/pylife/materialdata/woehler/fatigue_data.html)；示例已在本地 pyLife 2.3.1 执行，未使用真实试验数据。

对于 FFF PC-ABS，[[08 FFF工艺与PC-ABS疲劳 — Rodrigues等 2026]] 将一件达到 $10^6$ 次的试样记为 run-out。对于注塑 PC/ABS/PMMA，[[04 PC-ABS-PMMA疲劳试验 — Kuleyin与Gümrük 2025]] 的5 MPa跨配方比较由拟合外推，不应写成该幅值的实测。
