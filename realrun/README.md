# 真实 ODB 桥接产物（来自远程 Windows / Abaqus 2024）

远程项目位于 `E:\plastic-fatigue-bridge`（已从 C 盘迁出）。以下均由**真实 Abaqus 2024 ODB** 提取回传。

## 真实材料数据全链路（消除虚构参数）

- `data/raw/sn_rodrigues2026_pcabs.csv`（远程）：Rodrigues 等 2026, Polymers 18(18):302 表 8，
  真实 PC-ABS FFF 疲劳试验 10 点（9 断裂 + 1 run-out），从出版商 PDF 逐点提取。
  应力幅 2.52–13.39 MPa，R≈0.05，10 Hz。
- 拟合：pyLife MaxLikeFull（run-out 作删失）→ k1=4.66, ND=8.9e5, SD=2.43, TN=1.55, TS=1.11。
- 真实 ODB：循环实体梁，应力幅约 9.7 MPa（落在曲线有效区间，无外推），13 帧。
- 结果：32/32 点雨流闭合，用真实曲线算损伤，最高点损伤小计 4.05e-4（数千循环量级）。

## 本目录留存

- `real_bundle/`：静力悬臂梁桥接包（256 点 × 2 帧），验证桥接保真；`run_bridge_flow.py --verify-only realrun/real_bundle` 全项通过。
- `bridge_cyclic/`：循环实体梁桥接包（32 点 × 13 帧 = 416 行）。
- `cyclic_damage/`：教学虚构曲线链路验算（明确标注非真实材料）。
- 真实曲线拟合与损伤的权威产物在远程 `E:\plastic-fatigue-bridge\data\derived\curve_real.json` 与 `results\damage_realcurve\`。

## 边界
材料数据来自 FFF 打印 PC-ABS，用于方法学闭环验证，非目标牌号注塑件寿命承诺。
真实零件寿命仍需目标件几何/载荷谱/工况定义。

修复记录：numpy 数组分量 float() 转换；manifest ASCII；CSV 的 frame_id 转数值排序（'10'<'2'）；路径反斜杠归一化。
