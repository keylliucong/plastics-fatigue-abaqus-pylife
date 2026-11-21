# ODB → pyLife 桥接工具（GUI）使用说明

## 使用场景

用户在 Abaqus 提交作业、生成 ODB 后，打开本工具，用鼠标点选 ODB、交互式设置参数、
导出桥接包，并可直接接续计算损伤、出图。GUI 运行在与 Abaqus 隔离的 Python
（项目 venv），ODB 读取通过 `abaqus python` 子进程完成（PRD 方案 A：独立 GUI +
原生读取进程）。GUI 不直接加载 odbAccess，不修改原 ODB。

## 启动

Windows（可双击，推荐）：

```text
<项目目录>\bridge\start_gui.bat
```

脚本会优先使用项目 venv 的 `pythonw.exe`，找不到时回退到 PATH 中的 `pythonw`。
也可以显式启动：

```text
E:\plastic-fatigue-bridge\.venv\Scripts\pythonw.exe E:\plastic-fatigue-bridge\bridge\gui.py
```

macOS 本机（无 Abaqus 时只能看界面/做本地校验）：

```text
./bridge/start_gui.command
```

分析 Python 需要安装 pyLife（损伤计算）；出图另需 matplotlib。Windows 上
`abaqus python` 只负责读写 ODB，不承担 pyLife 计算。

## 六步向导

1. **① 文件与环境**：填写 abaqus.bat 路径（默认 `E:\SIMULIA\Commands\abaqus.bat`）、
   点“浏览”选择 ODB，点“测试连接并扫描 ODB” → 列出步骤/帧/分量/截面点。
2. **② 数据选择**：选分析步（可点按钮自动填入）、区域（实例/单元集，留空=全部）、
   应力分量、帧范围（如 `0:-1`）。实体保留全部积分点，壳截面点按实际编号保留、不平均。
3. **③ 预览与单位**：选择源应力单位（MPa/Pa/kPa/GPa）、源时间单位、时间含义
   （physical/pseudo/unknown）和应力基底（unknown/global/local）。
   点“预览材料点历程与校验汇总”查看：点数/帧数/行数、分量范围、失效行、非有限行、
   缺帧点、源单位与换算系数、基底状态，以及最多 3 个材料点 × 8 帧的样例历程。
4. **④ 疲劳参数**：选择已拟合曲线 JSON，点“查看曲线参数”核对 k1/ND/SD、参考 R、
   试验应力区间（finite_load_levels）与来源 CSV。缺参数时会明确提示不可用于计算。
5. **⑤ 校验与导出**：选择输出目录，点“执行：探测 → 提取 → 独立重读核对 → 导出”。
   提取端先写暂存目录，通过清单/哈希/组合键/缺帧/基底校验后才发布到目标目录；
   同一目录重复导出默认拒绝，确认覆盖后会清掉旧分块再发布，避免行数与清单不符。
6. **⑥ 计算与出图**：选择分析 Python（含 pyLife）与损伤输出目录（留空则写到
   `桥接包/damage_results`，图写到 `桥接包/figures`），点：
   - “① 校验桥接包”：只读重读核对；
   - “② 计算损伤并出图”：先强制校验（单位未确认、壳/梁截面点基底未解析时拒绝），
     再按 manifest 的换算系数把源应力换成 MPa，逐点雨流+Miner 损伤，输出
     `per_point.csv`、`summary.json`；随后调用 `plot_results.py` 输出
     `sn_curve.png`、`stress_history.png`、`rainflow_loops.png`、`damage_map.png`
     及对应 `*_data.csv`。

底部可“保存工程配置/打开工程配置”，便于复用设置（含单位、基底、分析 Python）。

## 从桥接包到结果文件

```text
⑤ 导出：<输出目录>/manifest.json + points.csv + fields/*.csv
⑥ 计算：<输出目录>/damage_results/per_point.csv + summary.json
⑥ 出图：<输出目录>/figures/*.png + *_data.csv
```

也可以不用 GUI，直接命令行：

```text
<python-with-pylife> fatigue/analyze_real_bundle.py <bundle> --curve <curve.json> \
    --component S11 --out <bundle>/damage_results
<python-with-matplotlib> fatigue/plot_results.py --history <bundle> \
    --damage <bundle>/damage_results --out <bundle>/figures
```

## 单位与基底的语义

- 提取端**不改写** ODB 数值，只记录 `units.stress_source` 与
  `units.stress_scale_to_MPa`；分析端统一乘系数换算到 MPa。选 Pa 时数值不会被
  当成 MPa 使用；单位缺失或无法识别时分析入口直接拒绝。
- 基底默认 `unknown`（记为 `local-unresolved`）。实体积分点按全局分量处理并在
  summary 中保留警告；壳/梁截面点在基底未解析时拒绝计算，需在提取端声明
  `--basis global`（已确认截面应力为全局分量）或人工确认后加
  `--allow-unresolved-basis`。
- 缺帧、`valid=false`、非有限应力的材料点不会进入损伤计算，会在
  `per_point.csv` 里以 `missing_frames` / `invalid_frames` / `skipped_nonfinite`
  标出；若所有点都被排除，命令以非零码退出。

## 已验证（本机自动化）

- 桥接逻辑测试：点键唯一、壳上下截面点分离保留、NaN/失效标记、哈希一致（`bridge/tests/test_bridge.py`）。
- 契约与校验：重复导出拒绝/覆盖后行数一致、缺帧与失效标记可检出、
  不同积分点的壳截面记录不误判为重复（`bridge/tests/test_contract_validation.py`）。
- 分析入口：MPa 与 Pa 同一物理载荷结果一致；缺帧/失效点被排除
  （`fatigue/tests/test_real_bundle.py`）。
- GUI：6 个向导页可构造，窗口标题/页签无错误。
- E 盘教学算例的数值复算（见 `realrun/README.md`）。

**尚未完成的验收**：Windows 桌面上的实际点击流程（求解完成 → 打开工具 → 选 ODB →
设置分析步/区域/分量/单位 → 预览 → 导出 → 计算 → 出图），以及含中文和空格的路径
实机走查。需在 E 盘那台 Windows 机器上按上面六步操作一次。

## 边界

- 需 Windows 图形桌面；SSH 无桌面会话时窗口无法交互，但调用链逻辑可测。
- 无桌面会话下弹窗（messagebox）会阻塞，自动化测试需将其禁用。
- 单位由用户显式确认；未确认不得贴 MPa/秒标签；残余循环不闭合不计入损伤。
- 外推与应力比不匹配的点（幅值超出 `finite_load_levels`、或 R 与曲线参考 R 不一致）
  只作方法学参考，不能作为零件寿命承诺。
