---
类型: 文献精读
状态: 正文已读，图表待复核
zotero_key: UHMR938Y
doi: 10.1016/j.finel.2024.104114
---
# 有限黏弹性与 Abaqus UMAT：Lefèvre 等，2024

原文：*Abaqus implementation of a large family of finite viscoelasticity models*，[DOI](https://doi.org/10.1016/j.finel.2024.104114)，[作者预印本](https://arxiv.org/abs/2311.13751)，[Zotero](zotero://select/library/items/UHMR938Y)。本次按预印本 PDF 页码阅读第 1–13 页正文；原公式及图像尚需逐图核对。研究对象是**各向同性弹性体的大变形等温黏弹性**，不是 PC/ABS 疲劳寿命模型。

## 问题 → 方法 → 证据

作者希望在 Abaqus 中实现一族可压缩与不可压缩弹性体的大变形黏弹性模型。文章采用自由能和耗散势构造材料行为，用内部变量记录黏性变形；第 6–7 页介绍全局平衡方程的 Newton 迭代和积分点内部变量的五阶显式 Runge–Kutta 更新。第 8–10 页分别进行均匀变形 patch test 与非均匀边值问题的解析解比较；第 11–13 页以两相橡胶周期单胞的均匀化响应展示数值能力。

验证材料包括近似 3M VHB 4910 的丙烯酸弹性体，第 8 页表 1 数值不能用于 PC/ABS。解析解一致与网格收敛证明的是给定边值问题上的数值实现表现，并不等于材料模型在实际塑胶产品和疲劳寿命上的实验验证。第 10 页作者指出低阶 C3D4H 需要比其他所示单元更细的网格。

## 数学与物理逻辑

以参考构形为基准，变形梯度 $F=\partial x/\partial X$、$C=F^TF$，黏性内部变量 $C^v=F^{vT}F^v$，$J=\det F$。论文第 2–3 页式 (1)、(5)、(6) 的结构可概括为：

$$\psi(F,C^v)=\psi^{Eq}(F)+\psi^{NEq}(F,C^v),\qquad S=\frac{\partial\psi}{\partial F},\qquad \frac{\partial\psi}{\partial C^v}+\frac{\partial\phi}{\partial\dot C^v}=0.$$

这里 $\psi$ 是单位参考体积的自由能，$\phi$ 是耗散势，$S$ 是第一 Piola–Kirchhoff 应力；平衡项保留长期弹性，非平衡项与内部变量共同描述应力松弛。该模型假设 $\det C^v=1$，对应文中所研究弹性体的黏性部分等体积，不能未经实验验证推广到其他聚合物。

本工作使用归一化更新 $C^v=A/(\det A)^{1/3}$ 以保持行列式约束（第 7 页式 31）。它解决的是材料点内部变量的积分；**局部采用显式 Runge–Kutta 并不意味着整套模型使用 Abaqus/Explicit**。文章主体是无惯性的准静态平衡和 UMAT 实现，不能把该代码当成 Explicit 的 VUMAT。

第 7 页建议所示积分方法的时间增量不大于特征时间 $\tau$ 的约 $10^{-2}$；这是作者针对该方法的经验建议，依然必须做时间步收敛。举例：若材料拟合出的 $\tau=2\,s$，起始上限建议约 $\Delta t=0.02\,s$；不是所有 Abaqus 黏弹模型的通用步长规则。

## 对本项目的决策

1. 先测试小应变线性黏弹的拟合残差和预测能力；若显著大应变、非线性及历史效应不能被现有本构表征，才研究更复杂的用户材料。
2. 先用单单元加载、卸载、松弛验证，再做网格、时间增量和能量检查；用独立材料测试校准模型，不能套用橡胶参数。
3. 单独区分材料响应模型与疲劳损伤模型：本文不输出 S–N 寿命，也未证明 Miner 规则适合目标 PC/ABS。
4. [作者公开代码](https://github.com/victorlefevre/UMAT_Lefevre_Sozio_Lopez-Pamies) 是研究参考，尚未验证本机编译、许可条款、Abaqus 2024、壳单元或本文以外的产品分析。
