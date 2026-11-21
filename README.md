# 塑胶件疲劳仿真：Abaqus + pyLife

面向塑胶件疲劳分析的方法研究与工程实施项目，不限定PC/ABS。当前已完成文献归档、方法导读与项目专用AI技能安装；尚未建立并验证具体零件的疲劳模型。

## 当前内容

- Zotero项目分类截至2026-11-16有38条文献、标准与官方技术文档，包含原始PC/ABS案例和通用聚合物方法；原BibTeX和元数据是36条历史快照。
- 13份已获取的PDF，按Zotero条目去重；54个项目技能目录（含Nature共享支持包）。
- Zotero中文评注、DOI清单、BibTeX和PDF校验清单。
- 四套技能来源：Ohmframe Abaqus AI Skills、jasonanewcoder Abaqus Skills、Nature Skills、Science Superpowers。

本仓库默认用于私人研究归档。论文全文保留原有权利；第三方技能保留各自许可证，不能以本项目名义重新授权。

## 从这里开始

0. 查看[完整技术路线与实现接口](docs/technical-route.md)：本构/工况、Standard或Explicit、材料点历程、pyLife、验证与程序模块。
   - [图形路线 PNG](docs/assets/technical-route.png) / [可编辑 SVG](docs/assets/technical-route.svg)。
   - [ODB—pyLife 桌面桥接工具 PRD](docs/superpowers/specs/2026-11-15-odb-pylife-bridge-design.md)：Windows、Abaqus 2024、实体与壳单元；已按此实现 GUI 与命令行入口（见 `bridge/`、`docs/research/GUI桥接工具使用说明.md`）。
1. 阅读[通用分析方法论](docs/research/塑胶件_Abaqus_pyLife疲劳分析方法论.md)。
   - 系统学习：[项目理论知识与阅读指南](docs/research/项目理论知识与阅读指南.md)，14章，含公式、手算案例、文献DOI与学习计划；[HTML阅读与打印版](docs/research/项目理论知识与阅读指南.html)需下载后用浏览器打开。
   - 新增[Obsidian知识库工作快照](docs/obsidian-vault/仓库快照说明.md)：文献精读、证据台账、数学物理模型、技术SOP与图形路线，均保留未完成状态。
2. 浏览[文献索引](literature/README.md)，用[references.bib](literature/references.bib)导入文献管理软件；PDF映射见[pdf-manifest.json](literature/pdf-manifest.json)。
3. 查看[技能使用说明](docs/skills.md)。在本项目目录打开Codex，新会话可发现`.agents/skills/`；没有修改全局skill或安装启动钩子。
4. 后续用真实载荷、材料试验和零件几何建立恒幅基线，再评估变幅与热/黏弹影响。

## 目录

```text
.agents/skills/          四套上游技能及配套文件
skills.lock.json         上游仓库、固定commit与安装路径
third_party/            技能索引、上游README与许可证
docs/research/          文献检索记录、DOI与疲劳方法论
docs/obsidian-vault/    本机Obsidian研究库的工作快照
literature/             36条历史元数据、中文笔记、BibTeX、13份PDF
abaqus/                 后续建模与ODB提取工作的说明
fatigue/                后续pyLife计算工作的说明
data/                   后续试验/载荷数据说明
results/                后续验证与结果说明
```

## 计算状态

已归档与核验文件；合成链路与桥接包校验已跑通，真实 ODB 桥接包可回读。真实材料 S-N 由文献逐点数据拟合（Rodrigues 2026 PC-ABS，R≈0.05），目前仅用于方法学核对：E 盘循环算例存在低幅外推（8/32 点低于试验下限 2.52 MPa）和应力比错配（最高损伤点 R≈−0.60），不构成零件寿命结论。安装 skill 不包含 Abaqus、许可证、编译器或额外 API 服务。Windows 桌面上的完整点击流程仍待实机验收。

**已可运行的合成端到端演练**：`./run_synthetic_flow.sh` 一条命令跑通「合成桥接包（PRD v1 数据契约）→ 数据契约校验 → 逐点雨流 → 虚构 Wöhler/Miner → 寿命/场映射 → 独立进程重读核对」，输出在 `results/synthetic_pipeline/`。pyLife 2.3.1 雨流与 Wöhler 接口在 macOS 独立环境已验证；全部输入为合成应力与虚构参数，**不是**真实 ODB、材料或零件寿命。真实验证仍须在 Windows / Abaqus 2024 / 真实实体与壳 ODB / 匹配牌号疲劳试验上执行。

**桥接与计算入口**：`bridge/gui.py`（Windows 可双击 `bridge/start_gui.bat`）完成探测 → 提取 → 结构校验 → 导出，⑥ 页可继续计算损伤并出图；命令行入口为 `fatigue/analyze_real_bundle.py`。发布前强制校验清单/哈希/组合键/缺帧/失效标记/基底；单位未确认或壳截面点基底未解析时拒绝计算，缺帧与失效点逐点排除，不再静默进入损伤。

工程分工为：Abaqus计算局部响应，pyLife进行循环统计、材料曲线与损伤评估。若存在明显滞回、自发热、保载或顺序效应，应验证S-N/Miner基线的适用性，必要时采用自定义损伤方法。

## 来源与版本

技能版本固定在[skills.lock.json](skills.lock.json)，阅读和安装日期为2026-11-15。论文原始Zotero分类和检索时的判断保留在`literature/metadata/`、`literature/notes/`；“已获取PDF”不等同于“已精读”。
