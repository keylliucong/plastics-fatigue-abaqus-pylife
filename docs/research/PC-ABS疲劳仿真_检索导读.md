# PC/ABS 疲劳仿真：文献与技术文档首轮检索

检索日期：2026-11-15。归档位置：Zotero → PC-ABS疲劳仿真｜Abaqus + pyLife。

共26条独立资料：13篇PC/ABS相关论文（含1篇会议论文）、1篇聚合物自发热综述、1篇工程技术论文、9条软件官方文档、2项试验标准。6条附PDF；所有26条均有中文检索评注。其余为元数据或在线文档，不代表取得全文。

## 初步判断与阅读顺序

Abaqus求取局部响应，再由pyLife处理循环与损伤，是可进一步验证的技术路线；这属于基于现有工具能力的工程判断，当前检索尚不能证明存在可直接用于目标PC/ABS牌号的现成验证流程。

建议依次阅读2018温度研究、2026频率/热软化研究、2025含PC/ABS基线的PMMA论文，再阅读OdbClient及寿命计算示例。2018论文的Wöhler曲线是简化构造；2026论文目前只完成摘要级筛选。

建立初版模型前，需要明确材料牌号/PC-ABS比例、填料与阻燃体系、注塑或打印工艺、工作温度、频率、应力比及载荷谱。S-N参数必须匹配这些条件；仅E、泊松比和拉伸强度不足以完成可信疲劳预测。

若近似弹性且温升可忽略，可试行经本材料试验标定的S-N与循环损伤流程；若有显著黏弹、塑性、保载或自发热，需要先确定更合适的本构和损伤方法。pyLife示例中的均值应力修正、FKM材料分组或金属经验参数不应直接套用。已有裂纹时应另设裂纹扩展分析，区分起裂寿命和扩展寿命。

## 检索与筛选记录

来源：Crossref、OpenAlex、出版商/期刊官网、Dassault Systèmes官方技术资料、pyLife官方文档和ASTM官方目录。检索词包括PC/ABS fatigue、PC-ABS temperature、low cycle fatigue、fatigue crack propagation、viscoelastic constitutive、Abaqus ODB、pyLife rainflow/Woehler/lifetime。

本轮为面向仿真实施的精选检索，不是系统综述。优先正式出版版本；未重复收入2022相容改性论文的SSRN预印本。试验标准仅收官方元数据和公开范围，未获取付费全文。软件文档优先固定2.3.1版本，odbserver使用stable浮动链接。中文论文Crossref年份与期刊不符，已按期刊官网校正为2007。

## 01 PC-ABS疲劳试验与S-N数据

### Investigation of Fatigue Behavior of ABS and PC-ABS Polymers at Different Temperatures

Andrea Mura; Alessando Ricci; Giancarlo Canavese | 2018-9-25 | journalArticle

来源：[10.3390/ma11101818](https://doi.org/10.3390/ma11101818) · Zotero条目：`5PUAPLS2` · 已附PDF

核心必读。注塑Cycoloy1200HF PC-ABS；试验温度22、85、-27°C，30 Hz。论文图7为50%存活概率的简化Wöhler曲线，由拉伸参数和疲劳极限构造，不是完整逐级S-N试验数据库。用于温度敏感性与验证思路；不可当作任意牌号PC/ABS设计许用曲线。已查看出版商全文网页。

### Interaction between strain-rate strengthening and thermal softening in fatigue behavior of PC/ABS blends

Jeong-Moo Lee; Hyungkwon Park; Boyoung Yoon; Ji-Ung Moon; Junghwan Lee; Jung-Wook Wee | 2026-9 | journalArticle

来源：[10.1016/j.ijfatigue.2026.109678](https://doi.org/10.1016/j.ijfatigue.2026.109678) · Zotero条目：`3V3WWBZN` · 无本地PDF；元数据/网页归档

核心必读。2026年PC/ABS频率、应变率强化与热软化研究，涉及50%与75%PC配比、双线性S-N及自发热。用于判断温度/频率条件是否必须纳入模型。当前依据出版商摘要与元数据，未获取全文；具体应力比、参数及双线性转折点待全文核对。

### Research on the Low Cycle Fatigue Properties of PC/ABS Blend

Ming Hsiung Ho; Pin Ning Wang; Shun Chi Kuo | 2015-3-20 | journalArticle

来源：[10.4028/www.scientific.net/amr.1095.938](https://doi.org/10.4028/www.scientific.net/amr.1095.938) · Zotero条目：`SUCTX3GJ` · 无本地PDF；元数据/网页归档

注塑PC/ABS低周疲劳与成型条件。适合研究应变幅和工艺影响，提示高应变区需评估局部应变/耗散能方法。仅元数据及摘要筛选，不能把摘要中的成型条件推广为所有牌号的最佳工艺。

### Fatigue resistance and failure behavior of reaction compatibilized PC/ABS blends under tensile cyclic loading

Meng Ma; Chencheng Yu; Lei Bai; Si Chen; Yanqin Shi; Huiwen He; Wang Xu | 2022-6-20 | journalArticle

来源：[10.1007/s10965-022-03137-9](https://doi.org/10.1007/s10965-022-03137-9) · Zotero条目：`6BLSHSXK` · 无本地PDF；元数据/网页归档

PC/ABS及SMA相容改性；循环拉伸与界面分离机制。用于解释配方/相容性对疲劳寿命影响。已查看出版商摘要，未取得全文。采用2022正式期刊版本，不另收2021同题SSRN预印本。

### Highly enhanced the toughness and fatigue resistance of PC/ABS blends by constructing a double-comb compatibilizer

Bangdong Ge; Zongsheng Liu; Yi Zheng; Shiyang Zhu; Meng Ma; Si Chen; Yanqin Shi; Huiwen He; Yulu Zhu; Xu Wang | 2025-4 | journalArticle

来源：[10.1016/j.polymer.2025.128170](https://doi.org/10.1016/j.polymer.2025.128170) · Zotero条目：`FT3BC9TK` · 无本地PDF；元数据/网页归档

PC/ABS双梳相容剂改性研究；2025年正式论文。用途是配方敏感性与界面机制背景。依据Crossref元数据筛选，全文待获取；不能直接把改性配方疲劳曲线用作未改性商用PC/ABS输入。

### The Effect of Poly (Methyl Methacrylate) Content on Chemical, Thermomechanical, Mechanical, and Fatigue Life Characteristics of Ternary PC/ABS/PMMA Blends

Hamdi Kuleyin; Recep Gümrük | 2025-7-10 | journalArticle

来源：[10.3390/polym17141905](https://doi.org/10.3390/polym17141905) · Zotero条目：`4HT2HPWX` · 已附PDF

含PC/ABS基线及PC/ABS/PMMA三元体系；全文表6给出基线疲劳数据，适合后续数字化与Basquin拟合练习。论文报告5 Hz和拉-拉加载；R的正文比值写法有疑点，采用前必须结合原始应力上下限核对，按惯例R=σmin/σmax。PMMA含量改变的配方不能代替目标材料。已查看开放全文网页；附PDF供进一步精读。

### Mechanical, Fatigue, and Thermal Characterization of ASA, Nylon 12, PC, and PC-ABS Manufactured by Fused Filament Fabrication (FFF)

Ângela Rodrigues; Ricardo Branco; Margarida Franco; Rui Silva; Cândida Malça; Rui F. Martins | 2026-1-22 | journalArticle

来源：[10.3390/polym18020302](https://doi.org/10.3390/polym18020302) · Zotero条目：`RF9QV2NH` · 已附PDF

FFF增材制造专用参考。含PC-ABS疲劳数据，报道室温R=0.05。打印孔隙、铺丝/层间方向和工艺影响大；不可直接代用注塑件参数。已查看开放全文网页及数据表，附PDF。

## 02 裂纹扩展与黏弹本构

### Overload effect on the fatigue crack propagation of PC/ABS alloy

Qin-Zhi Fang; T.J. Wang; H.M. Li | 2007-10 | journalArticle

来源：[10.1016/j.polymer.2007.08.048](https://doi.org/10.1016/j.polymer.2007.08.048) · Zotero条目：`GYNENK27` · 无本地PDF；元数据/网页归档

PC/ABS疲劳裂纹扩展的过载效应。用于已有缺陷/变幅载荷下裂纹扩展分支，不属于整件总寿命S-N曲线。当前元数据/摘要级筛选；Paris参数及载荷序列须全文核查。

### ‘Tail’ phenomenon and fatigue crack propagation of PC/ABS alloy

Qin-Zhi Fang; T.J. Wang; H.M. Li | 2008-1 | journalArticle

来源：[10.1016/j.polymdegradstab.2007.09.002](https://doi.org/10.1016/j.polymdegradstab.2007.09.002) · Zotero条目：`ZW78X7PW` · 无本地PDF；元数据/网页归档

PC/ABS裂纹扩展与tail现象。用途为裂纹增长机制及Paris模型适用边界。期刊卷期年份可能与在线发表年不同，应按正式卷期核对。当前元数据/摘要级筛选，未获全文。

### Effect of cyclic loading on tensile properties of PC and PC/ABS

Qin-Zhi Fang; T.J. Wang; H.G. Beom; H.M. Li | 2008-8 | journalArticle

来源：[10.1016/j.polymdegradstab.2008.05.022](https://doi.org/10.1016/j.polymdegradstab.2008.05.022) · Zotero条目：`LU7DYX7X` · 无本地PDF；元数据/网页归档

循环加载后PC与PC/ABS拉伸性能变化；用于判断刚度/强度演化以及固定弹性模量假设是否合理。当前元数据级筛选，未逐页审读；不能直接当作循环本构参数集。

### FATIGUE CRACK GROWTH BEHAVIOR OF PC AND PC/ABS

Qinzhi Fang; Huimin Li; Tiejun Wang | 2007-08-20 | journalArticle

来源：[10.3724/sp.j.1105.2007.00713](https://doi.org/10.3724/sp.j.1105.2007.00713) · Zotero条目：`VT5WRGR4` · 无本地PDF；元数据/网页归档

中文核心参考：方钦志、李慧敏、王铁军，PC及PC/ABS共混物的疲劳裂纹扩展研究，高分子学报2007(8):713–718。Crossref返回2009日期，已根据期刊官网校正为2007-08-20。期刊摘要给出Paris型关系，使用前须核对ΔK单位、配比、R和试验条件；裂纹扩展寿命与S-N总寿命不可混用。已核对期刊摘要。

### Investigation of Viscoelastic Deformation and Constitutive Modeling of PC, ABS and PC/ABS Alloys

Z.N. Yin; T.J. Wang | 2012-2-27 | journalArticle

来源：[10.4028/www.scientific.net/amm.157-158.1186](https://doi.org/10.4028/www.scientific.net/amm.157-158.1186) · Zotero条目：`HSCSTRHV` · 无本地PDF；元数据/网页归档

PC、ABS及60/40、50/50、40/60配比的DMA/黏弹表征研究。可供Abaqus Prony/松弛拟合路线参考；不能直接移植不同牌号或温度数据。当前依据Crossref摘要，全文待核查。

### Research on Fatigue Fracture Characterization of PC/ABS Blend

Ming-Hsiung Ho; Pin-Ning Wang; Jung-Peng Ye; Sheng-Jie Li | 2015 | conferencePaper

来源：[10.2991/icadme-15.2015.351](https://doi.org/10.2991/icadme-15.2015.351) · Zotero条目：`VMNL7VRT` · 已附PDF

会议论文；研究注塑工艺与PC/ABS疲劳断裂，涉及da/dN–ΔK与Paris拟合。优先级低于直接对应工况的期刊试验。PDF已下载归档，尚未逐页审读。

## 03 聚合物疲劳方法与自发热

### Criticality of the Self-Heating Effect in Polymers and Polymer Matrix Composites during Fatigue, and Their Application in Non-Destructive Testing

Andrzej Katunin | 2018-12-23 | journalArticle

来源：[10.3390/polym11010019](https://doi.org/10.3390/polym11010019) · Zotero条目：`UC3HMX8S` · 已附PDF

聚合物及聚合物基复合材料自发热综述。用于组织温升、滞回耗散与疲劳机制的后续阅读；其复合材料结论不是PC/ABS定量模型。已查看出版商网页，附开放PDF供精读。

### Fatigue Behavior of Engineering Polymers and Its Numerical Implementation

Pieter Volgers; Amir K. Shojaei | 未确认年份 | report

来源：[官方文档](https://www.3ds.com/assets/invest/2024-01/2218-saoe-fatigue_behavior_of_engineering_polymers_and_its_numerical_implementation.pdf) · Zotero条目：`RYGCBQQJ` · 已附PDF

DuPont技术论文，作者Pieter Volgers与Amir K. Shojaei；由Dassault Systèmes官网提供PDF。案例为Delrin POM等工程聚合物，涉及Abaqus、自发热、温度/黏弹与用户子程序。仅借鉴方法，不可移植其材料常数到非晶PC/ABS。PDF元信息误含模板标题，已按首页真实题名建档；出版年份未确认，留空。已查看首页及摘要。

## 04 Abaqus与pyLife官方技术文档

### pyLife 2.3.1 — User guide

pyLife developers | 未确认年份 | webpage

来源：[官方文档](https://pylife.readthedocs.io/en/2.3.1/user_guide.html) · Zotero条目：`PNXRWNKE` · 无本地PDF；元数据/网页归档

总览材料拟合、载荷处理与寿命计算；pyLife是计算工具，PC/ABS模型仍须标定。

### pyLife 2.3.1 — The WoehlerCurve data structure

pyLife developers | 未确认年份 | webpage

来源：[官方文档](https://pylife.readthedocs.io/en/2.3.1/tutorials/woehler_curve.html) · Zotero条目：`LER4G59Z` · 无本地PDF；元数据/网页归档

S-N参数与曲线使用；勿未经试验假设塑胶存在无限寿命平台。

### pyLife 2.3.1 — The rainflow module

pyLife developers | 未确认年份 | webpage

来源：[官方文档](https://pylife.readthedocs.io/en/2.3.1/stress/rainflow.html) · Zotero条目：`V2RP94U7` · 无本地PDF；元数据/网页归档

雨流计数与FullRecorder，可保留循环位置以关联温度；检查残余循环处理。

### pyLife 2.3.1 — Life time Calculation

pyLife developers | 未确认年份 | webpage

来源：[官方文档](https://pylife.readthedocs.io/en/2.3.1/demos/lifetime_calc.html) · Zotero条目：`JKJYC99W` · 无本地PDF；元数据/网页归档

Miner类损伤、均值修正与有限元网格流程；示例均值修正和金属参数不等于PC/ABS验证。

### pyLife 2.3.1 — The OdbClient class

pyLife developers | 未确认年份 | webpage

来源：[官方文档](https://pylife.readthedocs.io/en/2.3.1/tools/odbclient/odbclient.html) · Zotero条目：`DKYZVGS7` · 无本地PDF；元数据/网页归档

Abaqus ODB桥接：步骤、帧、场与历史输出；注意默认积分点数据可能转为单元节点值，显式核对position。

### pyLife — The pylife-odbserver package

pyLife developers | 未确认年份 | webpage

来源：[官方文档](https://pylife.readthedocs.io/en/stable/tools/odbserver/index.html) · Zotero条目：`T7TDNBQ4` · 无本地PDF；元数据/网页归档

Abaqus端ODB服务安装；stable为浮动链接，部署需核对Abaqus Python与client/server版本。

### Abaqus 2026 — Reading field output data

Dassault Systèmes | 未确认年份 | webpage

来源：[官方文档](https://docs.software.vt.edu/abaqusv2026/English/SIMACAECMDRefMap/simacmd-c-odbintroreadfieldpyc.htm) · Zotero条目：`ETK2GDHZ` · 无本地PDF；元数据/网页归档

官方场输出读取：应力张量、积分点、截面点及位置标识，用于建立可追溯应力历程。

### Abaqus 2026 — Time Domain Viscoelasticity

Dassault Systèmes | 未确认年份 | webpage

来源：[官方文档](https://docs.software.vt.edu/abaqusv2026/English/SIMACAEMATRefMap/simamat-c-timevisco.htm) · Zotero条目：`43BLRYYC` · 无本地PDF；元数据/网页归档

黏弹与Prony表征的官方依据；应以本牌号DMA/松弛数据验证适用应变和温度范围。

### Abaqus 2026 — Combining Material Behaviors

Dassault Systèmes | 未确认年份 | webpage

来源：[官方文档](https://docs.software.vt.edu/abaqusv2026/English/SIMACAEMATRefMap/simamat-c-matmodels.htm) · Zotero条目：`UN6AN88K` · 无本地PDF；元数据/网页归档

核对材料模型兼容性；不能默认线性黏弹和任意塑性模型可直接叠加。

## 05 疲劳试验标准

### ASTM D7791-22 — Standard Test Method for Uniaxial Fatigue Properties of Plastics

ASTM International | 2022 | standard

来源：[10.1520/D7791-22](https://doi.org/10.1520/D7791-22) · Zotero条目：`92LYUGXY` · 无本地PDF；元数据/网页归档

塑料单轴疲劳试验标准ASTM D7791-22。已核对官方目录与公开范围；未获取付费标准全文。后续试样、加载、调湿、频率和终止规则应以持有授权的标准全文为准。

### ASTM D7774-22 — Standard Test Method for Flexural Fatigue Properties of Plastics

ASTM International | 2022 | standard

来源：[10.1520/D7774-22](https://doi.org/10.1520/D7774-22) · Zotero条目：`33B87BBZ` · 无本地PDF；元数据/网页归档

塑料弯曲疲劳试验标准ASTM D7774-22。已核对官方目录与公开范围；未获取付费标准全文。若零件为弯曲主导，可用于制定材料验证试验；与轴向疲劳数据不可无条件互换。
