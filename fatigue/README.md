# pyLife工作区

实现并验证材料曲线、循环计数、载荷集、损伤和寿命映射。

## 已可运行：端到端合成流程演练

`pipeline.py` 在没有 Abaqus/真实 ODB/真实材料的本机环境，把 SOP 的整条计算链跑通一次：

**合成桥接包（PRD v1 契约）→ 数据契约校验 → 逐点雨流 → 虚构 Wöhler → Miner 损伤 → 寿命/场映射 → 手算核对 → 结果落盘。**

运行（使用本机已装 pyLife 2.3.1 的解释器）：

```text
<pyLife-2.3.1>/bin/python fatigue/pipeline.py
<pyLife-2.3.1>/bin/python fatigue/bridge_adapter.py results/synthetic_pipeline/bridge_bundle
```

第一步生成合成桥接包（PRD v1：`points.csv` + `fields/*.csv` + `fatigue_parameters.json` + 带 SHA-256 的 `manifest.json`）与逐点损伤；`bridge_adapter.py` 在**独立进程**重读该包，核对文件哈希、材料点键唯一性、行数、时间顺序与参数，证明“导出 → 独立重读核对”闭环。脚本内置数据契约校验与手算断言，任一失败即以非零码退出，不产生标为完成的包。

**边界**：全部输入为合成应力历程与虚构 Wöhler 参数，未读 ODB、未拟合真实材料、未做均值/温度/频率修正，残余循环未闭合且未计入损伤。这是接口、单位与算术的演练，**不是**真实零件寿命预测或验证结果。真实计算须在 Windows/Abaqus 2024、真实实体/壳 ODB 与匹配牌号的疲劳试验数据上另行执行。

## 对真实桥接包计算损伤

```text
<pylife-python> fatigue/analyze_real_bundle.py <bundle_dir> --curve <curve.json> \
    --component S11 --out <bundle_dir>/damage_results
<python-with-matplotlib> fatigue/plot_results.py --history <bundle_dir> \
    --damage <bundle_dir>/damage_results --out <bundle_dir>/figures
```

分析入口在计算前强制校验桥接包（清单/哈希/组合键/缺帧/失效标记/应力基底），
按 `manifest.units` 把源应力显式换算为 MPa；单位未确认、壳/梁截面点基底未解析时
拒绝计算。缺帧、`valid=false`、非有限应力的材料点逐点排除并在 `per_point.csv`
标注 `status`；`summary.json` 记录单位、基底、校验结果、幅值范围、低于/高于
曲线试验区间的点数与 R 不匹配点数。外推或应力比错配的结果只能作方法学参考。

输入需包含匹配工况的材料疲劳数据与可追溯局部历程。先复现恒幅试样，再以独立变幅数据验证。不要默认存在塑胶无限寿命平台，也不要把软件示例材料参数用作真实材料输入。
