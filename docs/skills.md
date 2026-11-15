# 项目技能安装与使用

已使用Codex skill-installer helper将下列四套技能安装到本项目`.agents/skills/`，共54个目录，包含`nature-shared`支持包。不修改全局skill目录；下一轮在此项目打开的新会话可发现这些项目技能。

| 来源 | 目录数 | 主要用途 |
|---|---:|---|
| [Ohmframe/abaqus-ai-skills](https://github.com/Ohmframe/abaqus-ai-skills) | 7 | 建模、ODB提取、网格诊断、传热和作业检查 |
| [jasonanewcoder/abaqus_skills](https://github.com/jasonanewcoder/abaqus_skills) | 7 | 通用/静力/疲劳/热/复材/XFEM脚本及子程序 |
| [Yuan1z0825/nature-skills](https://github.com/Yuan1z0825/nature-skills) | 24 | 阅读、证据整理、绘图、论文写作等；含共享支持包 |
| [K-Dense-AI/science-superpowers](https://github.com/K-Dense-AI/science-superpowers) | 16 | 研究问题、分析设计、复现和结果核验 |

本次只安装技能及配套资源，没有执行上游安装钩子、自动更新脚本或外部API程序，也没有安装Abaqus MCP。它们需要的Abaqus、Fortran、Python/R库、文档转换器或外部服务按具体任务再配置。

## 推荐入口

- 精读下载的论文：`nature-paper-card`、`nature-paper-xray`或`nature-reader`。
- Abaqus局部历程：`abaqus-odb-extract`；保留积分点、截面点和坐标系标识。
- 建模与求解：`abaqus-model-builder`，或Jason通用脚本模块；避免两套流程重复执行。
- 材料子程序：Jason子程序模块，必须通过单元级和基准验证。
- 实验/仿真方案：按需使用Science Superpowers，用户当前任务和既有授权优先。

## 安装映射与适配

上游目录名与frontmatter名称不一定相同，例如Jason的`general`目录声明`abaqus-script-control-general`，`abaqus_subroutine_skills`声明`abaqus-subroutine-development`。保留目录名是为了使相邻技能间的相对链接继续有效。全部映射在[skill-index.json](../third_party/skill-index.json)。

Jason通用skill引用仓库根目录的`abaqus_agent_playbook.md`。已从同一commit补充到本地`general`目录，来源与路径记录在lock文件。Nature共享依赖按原来的同级目录保留。

保存上游README和许可证于`third_party/licenses/`。当前状态是文件安装与静态完整性检查通过，不代表54个技能均已在本机执行验证。上游错误、示例金属参数与版本假设应在应用时审查。
