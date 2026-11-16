# Obsidian 知识库项目调研

检索日期：2026-11-16。以下为候选，不代表已安装插件或完成兼容性测试。

| 项目 | 适用点 | 注意事项 |
|---|---|---|
| [obsidian-research-vault-template](https://github.com/hoonsubin/obsidian-research-vault-template) | 学术研究和Zotero整合，适合借鉴文献笔记结构 | 依赖与具体版本须逐项核对 |
| [obsidian-scientific-research-vault](https://github.com/LalieA/obsidian-scientific-research-vault) | 科研知识库和文献工作流 | 自带配置及依赖较多，先核查后选用 |
| [Obsidian-Research-Vault-Template](https://github.com/danielrosehill/Obsidian-Research-Vault-Template) | 研究用笔记模板、元数据与双向链接，声明不需社区插件 | 借鉴结构前核对许可证和项目成熟度 |
| [seed-vault](https://github.com/crsaila/seed-vault) | PARA分类及工作项目的笔记组织 | 适合作为通用目录参考 |
| [obsizoto-vault](https://github.com/tuonglnc/obsizoto-vault) | Zotero条目、阅读队列和研究笔记 | 自动导入机制与本机Zotero版本须核验 |

建议先采用轻量的项目主页、理论、文献和决策笔记；待明确Zotero同步需求后再选择插件。不要直接执行模板内的自动化脚本。

## 核查后的具体借鉴与现状

此前的调研只是候选项目清单，未充分落实为好用的研究工作流；早期使用 Zotero 条目键作为文件名，也不利于直接浏览。下表将已核对的项目做法与本库现状分开说明。

| 参考项目的做法 | 本项目如何采用 | 当前状态 |
|---|---|---|
| [hoonsubin 研究库](https://github.com/hoonsubin/obsidian-research-vault-template)：Zotero 保存原始文献，文献笔记与概念笔记分别组织 | Zotero 保存条目和附件；Obsidian 分开组织文献索引、精读和主题地图 | 文件和主题入口已建立；精读仍在进行，未安装该项目的自动导入插件 |
| [Daniel Rosehill 研究库](https://github.com/danielrosehill/Obsidian-Research-Vault-Template)：主页、问题、来源、结论和手动维护的主题入口，无须依赖社区插件 | 使用 [[项目主页]]、[[塑胶疲劳知识地图]]、[[精读进度与证据台账]] 组织入口、证据和待核查事项 | 入口已建立；尚未完整建设逐问题和逐结论的原子笔记 |
| [sachasiani 研究库](https://github.com/sachasiani/obsidian-vault)：用 Zotero 元数据支持检索与文献笔记 | 用可读标题浏览，并保留 Zotero 条目键用于定位 | 文献文件已改名；条目与 PDF 以 Zotero 为准，不声称双向自动同步 |

建设顺序：从项目主页进入 → 按问题选择主题 → 查看标明页码和证据边界的精读 → 关联模型与 SOP。索引条目不等同于已精读；空模板不等同于知识内容。不要把其他模板的插件配置直接覆盖本库。
