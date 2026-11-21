# 真实 ODB 桥接产物（来自远程 Windows / Abaqus 2024）

本目录的 `real_bundle/` 由远程项目 `C:\Users\Public\plastic-fatigue-bridge` 在
**真实 Abaqus 2024 ODB** 上提取并回传，用于留证与跨平台核对。

- 来源 ODB：`bridge_cantilever.odb`（教学悬臂梁，本机远程实机求解生成，原生 2024）。
- 提取方式：`abaqus python bridge/odb_extract.py`（只读，不改原 ODB）。
- 内容：256 材料点 × 2 帧 = 512 行，分量 S11；单位为手动确认（MPa / s）。
- 核对：`python bridge/run_bridge_flow.py --verify-only realrun/real_bundle` 全项通过
  （文件哈希一致、点键唯一、行数一致、时间有序、无 NaN 丢失）。
- 元数据为 ASCII，避免 Windows/Mac 编码差异。

**范围限制**：这是静力加载步，只有 2 帧，不足以形成雨流闭合环；此处只验证桥接数据保真，
不计算疲劳寿命。真实 S–N 拟合需匹配牌号的恒幅疲劳试验数据（尚未取得）。

修复记录：真实 ODB 的 `v.data` 是 numpy 数组，分量需 `float()` 转换；清单路径用 `/` 归一化。
