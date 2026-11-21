# 真实 ODB 桥接产物（来自远程 Windows / Abaqus 2024）

远程项目位于 `E:\plastic-fatigue-bridge`（已从 C 盘迁出）。以下均由**真实 Abaqus 2024 ODB** 提取回传。

## 真实材料数据

- `data/raw/sn_rodrigues2026_pcabs.csv`（远程）：Rodrigues 等 2026, Polymers 18(18):302 表 8，
  真实 PC-ABS FFF 疲劳试验 10 点（9 断裂 + 1 run-out），从出版商 PDF 逐点提取。
  应力幅 2.52–13.39 MPa，R≈0.05，10 Hz。
- 拟合：pyLife MaxLikeFull（run-out 作删失）→ k1=4.66, ND=8.9e5, SD=2.43, TN=1.55, TS=1.11。
- 本地未留存 `curve_real.json` 与原始 S-N CSV；权威产物在远程
  `E:\plastic-fatigue-bridge\data\derived\curve_real.json` 与 `results\damage_realcurve\`。

## E 盘真实曲线算例（本仓库图与数字的来源）

- 真实 ODB：循环实体梁，13 帧，32 个实体积分点，源单位 MPa。
- 实际闭合环应力幅 **0.574–8.612 MPa**；其中 **8/32** 个点低于曲线试验下限
  **2.52 MPa**，属于低幅外推，不是“全部落在有效区间”。
- 损伤用真实曲线计算，最高 Miner 小计 **4.047×10⁻⁴**；该点应力比 **R≈−0.60**，
  而试验曲线参考 **R≈0.05**，未做均值应力修正，属于应力比不匹配。
- 因此：这组数字只用于方法学闭环核对，**不能**表述为“无外推”，也**不能**
  当作零件寿命结论（更不存在“数千循环寿命”这种工程承诺）。
- 图与数据：`realrun/figures/` 下的 PNG 与 `*_data.csv`（S-N、应力历程、雨流环、
  损伤分布）由 E 盘算例产物回传；图题已改为中性方法学说明。

## 本目录留存与用途

- `real_bundle/`：静力悬臂梁桥接包（256 点 × 2 帧），只验证桥接保真；
  `run_bridge_flow.py --verify-only realrun/real_bundle` 应全项通过，**不用于损伤结论**。
- `bridge_cyclic/`：循环实体梁桥接包（32 点 × 13 帧 = 416 行），保存的是教学量级
  载荷（数百 MPa 量级），仅用于单位换算、缺帧/失效过滤、雨流链路测试，
  **不能与 E 盘算例的 0.574–8.612 MPa 数值混用**。
- `cyclic_damage/`：教学虚构曲线链路验算（明确标注非真实材料）。
- `figures/`：E 盘真实曲线算例回传的图与数据（见上节）。

## 重新核对

```bash
# 桥接包结构校验（清单/哈希/组合键/缺帧/失效/基底）
python bridge/run_bridge_flow.py --verify-only realrun/real_bundle
python bridge/run_bridge_flow.py --verify-only realrun/bridge_cyclic

# 对桥接包计算损伤（需 pyLife；这里用测试曲线，仅验证链路）
<pylife-python> fatigue/analyze_real_bundle.py realrun/bridge_cyclic \
    --curve /path/to/curve.json --component S11 --out /tmp/cyclic_damage
```

分析入口会强制校验：源应力单位未确认则拒绝；壳/梁截面点基底未解析则拒绝；
缺帧、`valid=false`、非有限应力的材料点逐点排除，并写入 `per_point.csv` 的
`status`；`summary.json` 记录单位、基底、校验结果、幅值范围，以及低于/高于
曲线试验区间和 R 不匹配的点数。

## 边界

材料数据来自 FFF 打印 PC-ABS，用于方法学闭环验证，非目标牌号注塑件寿命承诺。
真实零件寿命仍需目标件几何/载荷谱/工况定义；E 盘算例的幅值外推与 R 错配
必须在报告中逐点标注。

## 修复记录

- 早期：numpy 数组分量 `float()` 转换；manifest ASCII；CSV 的 `frame_id` 转数值排序
  （`'10'<'2'`）；路径反斜杠归一化。
- 2026-11-21 审查后：
  - 单位改为“提取保留源值 + manifest 记录换算系数”，分析端显式换算并拒绝未确认单位；
  - 桥接包写入改为暂存→校验→发布，重复导出默认拒绝；校验器不再把不同积分点的
    壳截面记录误判为重复；
  - 分析入口强制校验组合键、缺帧、失效标记与基底，缺帧/失效点逐点排除；
  - 修正本节“无外推”“数千循环量级”的错误表述；
  - S-N 拟合兼容 `load_amplitude_MPa` 模板列名，`fracture` 严格解析；
  - GUI 增加单位/基底选择、校验汇总预览、⑥ 计算与出图、双击启动入口。
