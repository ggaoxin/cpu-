"""rq_identify 研究问题句识别 gold 标准（Claude 自主标注）。

读 rq_sample_72.json（50中文+22英文摘要），我逐篇标注：
  - rq_sentences: 表达研究问题/探究对象的句子（摘要的 verbatim 子串）
  - 每句内 rq_phrase: 承载核心问题的短语（句子的 verbatim 子串）
脚本断言字面一致性，输出 gold JSON。
标注者(Claude)与预测器(GLM-5.2)不同模型。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from config.settings import settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

SAMPLE = str(settings.DATA_DIR / "rq_sample_72.json")
OUT = str(settings.DATA_DIR / "rq_sample_72_gold.json")

# id(1..72) -> [(sentence, phrase), ...]
MY = {
    1: [("文章基于2010—2021年中国30个省份面板数据，采用SBM模型和空间计量模型实证探究了规模经营视角下土地流转和农业社会化服务对农业全要素生产率的影响、空间溢出效应及其交互效应。", "土地流转和农业社会化服务对农业全要素生产率的影响、空间溢出效应及其交互效应")],
    2: [("针对仅考虑摇摆方程可能导致虚拟同步机暂态稳定性分析误判的问题，首先考虑公共耦合点处电压变化对系统暂态行为的影响，建立了计及电压动态特性的虚拟同步机暂态模型，实现对虚拟同步机动态特性的全面精准刻画。", "仅考虑摇摆方程可能导致虚拟同步机暂态稳定性分析误判的问题")],
    3: [("文章以洞庭湖区17个县域为研究对象，通过构建县域旅游生态效率指标体系，揭示了2011—2020年洞庭湖区旅游生态效率的时空特征；同时运用Tobit模型和动态QCA模型探究了洞庭湖区县域旅游生态效率的主要影响因素和影响路径。", "洞庭湖区县域旅游生态效率的主要影响因素和影响路径")],
    4: [("分布式电源高渗透并网，呈现出运行复杂性与非线性，故障电流谐波特征显著，使得传统继电保护难以准确区分励磁涌流与故障电流。", "传统继电保护难以准确区分励磁涌流与故障电流")],
    5: [("文章基于2011—2020年长江经济带108个地级市的面板数据，应用耦合协调度和PVAR模型分析并探讨了数字经济与城乡融合发展的耦合协调和相互作用关系。", "数字经济与城乡融合发展的耦合协调和相互作用关系")],
    6: [("为提高风资源数据集的准确性，文章提出了一种基于K-means++自适应的改进反距离加权插值方法(K-means++ adaptive inverse distance weighted interpolation method,K-means++AIDW)。", "提高风资源数据集的准确性")],
    7: [("为实现馈线负载均衡并稳定直流电压，提出基于事件触发的动态一致性馈线负载均衡控制策略。", "实现馈线负载均衡并稳定直流电压")],
    8: [("为了弥补交流变速抽蓄机组涉网环节的不足，依据我国对大型发电机组并网的技术要求，提出了一种适用于交流变速抽蓄机组的单通道电力系统稳定器(power system stabilizer, PSS)设计方法，同时还给出了变速机组与定速机组的协同响应策略。", "弥补交流变速抽蓄机组涉网环节的不足")],
    9: [("然而,目前鲜有关于采用DSOGI-PLL的模块化多电平换流器(modular multilevel converters,MMC)阻抗模型。", "目前鲜有关于采用DSOGI-PLL的模块化多电平换流器(modular multilevel converters,MMC)阻抗模型")],
    10: [("探究旅游市场、民生福祉与生态系统服务的关系是后脱贫地区推进乡村振兴和促进共同富裕进而实现中国式现代化建设的重要环节。", "旅游市场、民生福祉与生态系统服务的关系")],
    11: [("采用工业SO排放总量作为环境压力的衡量指标,基于自然正交函数(EOF)揭示了长江中游城市群工业SO排放量的时空演变特征,将工业SO排放的空间异质性纳入STIRPAT模型分析框架中,通过地理加权回归(GWR)模型进行空间变系数的驱动因素分析。", "长江中游城市群工业SO排放量的时空演变特征")],
    12: [("在含风功率等新能源出力不确定性的联合机会约束机组组合问题中，如何将多维联合机会约束转化为确定性约束是求解此问题的关键。", "如何将多维联合机会约束转化为确定性约束是求解此问题的关键")],
    13: [("论文分析了GDL应用于智能暂态稳定评估模型的设计框架，从图表示、图嵌入、全局聚合、训练方式4个方面探讨了暂态稳定评估应用中GDL的特征聚合性能提升方法。", "GDL应用于智能暂态稳定评估模型的设计框架")],
    14: [("然而，对于空间科学在载人航天、深空探测和科学卫星这三类任务中如何发挥其作用，仍然有不少疑问和困惑。", "空间科学在载人航天、深空探测和科学卫星这三类任务中如何发挥其作用")],
    15: [("文章着重讨论了分布式可再生能源和智能微网在能源结构调整和转变中的意义、作用和发展潜力", "分布式可再生能源和智能微网在能源结构调整和转变中的意义、作用和发展潜力")],
    16: [("以镇域为研究单元,以经济综合发展指数为测度指标,采用GIS空间分类、ESDA等空间分析技术,根据区域经济差异的相关理论,分析2006—2010年郑州都市区镇域经济空间格局变化特征。", "郑州都市区镇域经济空间格局变化特征")],
    17: [("中国铁路建设进入高速化和网络化发展阶段,从铁路网络视角透视中国城市体系的枢纽—网络结构研究成为热点和前沿。", "从铁路网络视角透视中国城市体系的枢纽—网络结构")],
    18: [("然而,一方面,目前联合基金合作方只限于具有“国有”性质的部门、机构和企业,尚未扩展到“私营”企业等主体;另一方面,联合基金的管理体制和运行模式未能充分体现联合基金“合作投资”的内在属性。", "联合基金的管理体制和运行模式未能充分体现联合基金")],
    19: [("然而,我国物流园区开发建设在取得较大成功的同时,也存在规划上贪大求全、土地资源浪费、园区闲置率高等问题。", "我国物流园区开发建设在取得较大成功的同时,也存在规划上贪大求全、土地资源浪费、园区闲置率高等问题")],
    20: [("如何引导灵活性资源参与电网优化运行是智能电网面临的重要问题，而交直流混合配电网的分区化和多元化也给优化运行带来新的挑战。", "如何引导灵活性资源参与电网优化运行是智能电网面临的重要问题")],
    21: [("文章以文献计量为基础,对拉美科技发展现状、世界各国对拉美科技合作情况以及中国科学院与该地区国家合作情况进行分析,基于固有合作基础,探讨未来对拉合作的建议思路及举措。", "拉美科技发展现状、世界各国对拉美科技合作情况以及中国科学院与该地区国家合作情况")],
    22: [("采用经济重心模型,借助Arc GIS技术手段,以天津市各区县GDP数据为基础,计算得出2005—2015年天津市经济重心空间演变轨迹。", "天津市经济重心空间演变轨迹")],
    23: [("目前的配网故障测距算法大多依靠短路迭代计算或模拟大量故障选取最匹配的故障点来实现测距功能,该类方法计算繁琐,且容易得到伪故障点,为此提出了一种基于稀疏电压幅值量测的配网故障测距方法", "目前的配网故障测距算法大多依靠短路迭代计算或模拟大量故障选取最匹配的故障点来实现测距功能,该类方法计算繁琐,且容易得到伪故障点")],
    24: [("针对光伏发电功率存在随机性和波动性较强、预测精度较低的问题，提出了一种基于变分模态分解(variationalmodedecomposition, VMD)和改进松鼠觅食算法优化核极限学习机(improvedsquirrelsearchalgorithm optimization kernel extreme learning machine, ISSA-KELM)的预测模型。", "光伏发电功率存在随机性和波动性较强、预测精度较低的问题")],
    25: [("以我国31个省(市、区)的高等学校、中职学校、普通中学、普通小学等四类学校为例,对四类学校2000—2012年各省(市、区)的生均教育经费支出进行了描述性统计分析和聚类分析,采用基尼系数法和核密度估计考察了四类学校生均教育经费支出省际差异的动态变化特征", "四类学校生均教育经费支出省际差异的动态变化特征")],
    26: [],  # 新年致辞，非研究问题
    27: [("文章简要评述了电微生物学学科的发展态势和前沿科学问题,并对其未来发展方向进行了展望。", "电微生物学学科的发展态势和前沿科学问题")],
    28: [("聚焦吴先生建立的“人地关系地域系统”研究的新命题,对四个方面进行了初步讨论", "吴先生建立的“人地关系地域系统”研究的新命题")],
    29: [("利用2016年上海市教育机构的相关数据,运用连锁网络模型、社会网络分析方法以及ArcGIS空间分析方法测度了上海城市网络的空间结构特征。", "上海城市网络的空间结构特征")],
    30: [("为此,提出一种面向需求侧的约定曲线形状及价格的曲线交易机制。", "面向需求侧的约定曲线形状及价格的曲线交易机制")],
    31: [("在实现经济转型和产业升级的过程中,新技术能否形成新动能,新动能能否带动新经济,已成为政府部门、产业界和学术界普遍关心的问题。", "新技术能否形成新动能,新动能能否带动新经济")],
    32: [("针对该问题,基于机电比拟原理构建了多VSG并网系统功–频环路的机械导纳模型,推导了多VSG并网系统输出角频率的传递函数矩阵。", "多VSG并网系统功–频环路的机械导纳模型")],
    33: [("而对于机侧换流器与交流系统间是否有强交互的可能,其如何产生、又有何影响,当前未见有充分的理论分析与研究。", "机侧换流器与交流系统间是否有强交互的可能,其如何产生、又有何影响")],
    34: [("海洋环境是最为恶劣的自然腐蚀环境;海洋腐蚀问题是海洋工程安全服役面临的主要威胁,也给国民经济带来巨大的损失。", "海洋腐蚀问题是海洋工程安全服役面临的主要威胁")],
    35: [("针对此问题，首先分析了采用不同控制模式的受端换流站间二倍频扰动交互影响机理，发现较直流电压控制MMC而言，采用下垂控制的MMC受到的扰动影响程度更大。", "采用不同控制模式的受端换流站间二倍频扰动交互影响机理")],
    36: [("虽然基于系统辨识的惯量在线评估方法可以在线评估电力系统惯量,但是目前无法确定最佳的模型阶次,导致误差较大。", "目前无法确定最佳的模型阶次,导致误差较大")],
    37: [("分布式电源高比例渗透和柔性负荷的灵活调度给配电网安全运行带来了极大挑战。", "分布式电源高比例渗透和柔性负荷的灵活调度给配电网安全运行带来了极大挑战")],
    38: [("基于产业结构演变理论,重点对湖南三次产业产值结构、就业结构与产值结构等层面分阶段进行横、纵向对比分析", "湖南三次产业产值结构、就业结构与产值结构")],
    39: [("传统分区修正法存在计算量大、PV节点归并缺乏理论依据等问题。", "传统分区修正法存在计算量大、PV节点归并缺乏理论依据等问题")],
    40: [("为了提高风电功率的预测精度,提出了一种基于最优变分模态分解(optimal variational model decomposition,OVMD)、麻雀算法(sparrow search algorithm,SSA)、深度极限学习机(deep extreme learning machine,DELM)和灰色模型(grey model,GM)的超短期风电功率预测方法。", "提高风电功率的预测精度")],
    41: [("为了使微电网群的频率调整达到调频任务的有序分担、调频费用的有序分摊以及调频经济性的有序达成等要求,分析了孤岛微电网群调频备用容量配备应遵循的规则,提出了微电网群频率调整的双层协调控制策略。", "微电网群的频率调整达到调频任务的有序分担、调频费用的有序分摊以及调频经济性的有序达成")],
    42: [("探讨充电站建设与电动汽车共享服务调度的协同优化问题具有重要现实意义。", "充电站建设与电动汽车共享服务调度的协同优化问题")],
    43: [("针对天然气管网压力能利用率低及各能源负荷波动导致能源系统不稳定等问题,提出考虑天然气管网压力能发电技术的电-热-气综合能源系统(integrated energy systems,IES)优化调度方法。", "天然气管网压力能利用率低及各能源负荷波动导致能源系统不稳定等问题")],
    44: [("文章从学科建设视角，围绕“为什么”“是什么”“如何评”等关键问题开展基础理论研究", "技术经济安全")],
    45: [("针对配电网高上送速率的PMU装置产生的海量数据对通信系统和存储系统造成巨大压力的问题，考虑到配电网边缘计算装置计算与存储资源有限，提出了基于过滤旋转门和指数哥伦布编码的配电网边缘侧PMU数据压缩方法。", "配电网高上送速率的PMU装置产生的海量数据对通信系统和存储系统造成巨大压力的问题")],
    46: [("为此剖析了数字孪生的内涵，并结合继电保护领域的实际应用需求，定义了继电保护数字孪生相关术语，归纳了继电保护数字孪生的期望特征。", "继电保护数字孪生相关术语")],
    47: [("针对直流近区域交流系统故障与特高压直流交互作用下的暂态电压机理尚不明确的问题，在深入分析交直流系统无功功率交互作用的基础上，明确了影响暂态电压的主导因素。", "直流近区域交流系统故障与特高压直流交互作用下的暂态电压机理尚不明确的问题")],
    48: [("输入串联输出并联(inputseriesoutputparallel, ISOP)双有源桥(dualactivebridge, DAB)变换器的输入均压(input voltage sharing, IVS)主动控制策略存在控制系统复杂和传感器数量较多的问题。", "输入均压(input voltage sharing, IVS)主动控制策略存在控制系统复杂和传感器数量较多的问题")],
    49: [("文章核算了中国30个省份水—能源—粮食耦合视角下的混合能源，运用投入产出分析和社会网络分析法，结合接近中心度和耦合协调度，选取了4个代表性省份，应用长期能源替代规划系统对其在不同情境下的碳排放量、碳达峰时间和减碳贡献进行了重点预测和分析。", "中国30个省份水—能源—粮食耦合视角下的混合能源")],
    50: [("宽增益和高性能是LLC谐振变换器应用于电动汽车、可再生能源系统等领域的关键，而传统变频控制下存在开关频率范围宽、电压调节性能差的问题。", "传统变频控制下存在开关频率范围宽、电压调节性能差的问题")],
    # 英文
    51: [("A theory with growing evidence is that people simulate using simplified representations of the environment that abstract away from irrelevant details, but it is unclear how people determine these simplifications efficiently.", "it is unclear how people determine these simplifications efficiently")],
    52: [("advances in AI-driven persuasion sharply reduce the cost and increase the precision of shaping public opinion, making the distribution of preferences itself an object of deliberate design.", "the distribution of preferences itself an object of deliberate design")],
    53: [("Previous studies on visual customization primarily rely on the objective alignment between various control signals (e.g., language, layout and canny) and the edited images, which largely ignore the subjective emotional contents, and more importantly lack general-purpose foundation models for affective visual customization.", "lack general-purpose foundation models for affective visual customization")],
    54: [("However, these designs often contain bidirectional dependencies, which left-to-right models struggle to capture.", "these designs often contain bidirectional dependencies, which left-to-right models struggle to capture")],
    55: [("However, empirical evidence suggests that such long-context LLMs can consume far more text than they can reliably use.", "such long-context LLMs can consume far more text than they can reliably use")],
    56: [("However, prior work reports a recurring trade-off: pass@k improves while pass@1 degrades under such methods.", "pass@k improves while pass@1 degrades under such methods")],
    57: [("In this work we revisit fundamental learning theory questions in this, now ubiquitous, setting.", "fundamental learning theory questions in this, now ubiquitous, setting")],
    58: [("This raises a fundamental question: can slow-thinking LLMs reason over temporal dynamics to support accurate TSF, even without task-specific training?", "can slow-thinking LLMs reason over temporal dynamics to support accurate TSF, even without task-specific training?")],
    59: [("Self-training systems often degenerate due to the lack of an external criterion for judging data quality, leading to reward hacking and semantic drift.", "Self-training systems often degenerate due to the lack of an external criterion for judging data quality, leading to reward hacking and semantic drift")],
    60: [("To enhance the inherent multilingual capabilities of Gemma 3 for the translation task, we employ a two-stage fine-tuning process.", "enhance the inherent multilingual capabilities of Gemma 3 for the translation task")],
    61: [("Discriminative approaches to classification often learn shortcuts that hold in-distribution but fail even under minor distribution shift.", "Discriminative approaches to classification often learn shortcuts that hold in-distribution but fail even under minor distribution shift")],
    62: [("While training data memorization has been extensively studied in standard pre-training and fine-tuning settings, its dynamics in a knowledge distillation setup remain poorly understood.", "its dynamics in a knowledge distillation setup remain poorly understood")],
    63: [("However, on-policy distillation typically requires a separate, often larger, teacher LLM and does not explicitly leverage ground-truth solutions available in reasoning datasets.", "on-policy distillation typically requires a separate, often larger, teacher LLM and does not explicitly leverage ground-truth solutions available in reasoning datasets")],
    64: [("Vision language models (VLMs) have achieved remarkable success in broad visual understanding, yet they remain challenged by object-centric reasoning on rare objects due to the scarcity of such instances in pretraining data.", "they remain challenged by object-centric reasoning on rare objects due to the scarcity of such instances in pretraining data")],
    65: [("Vision-Language Models (VLMs) face significant computational challenges in video processing due to massive data redundancy, which creates prohibitively long token sequences.", "Vision-Language Models (VLMs) face significant computational challenges in video processing due to massive data redundancy")],
    66: [("Memory is critical for AI agents, yet the widely-adopted static memory, aiming to create readily available memory in advance, is inevitably subject to severe information loss.", "the widely-adopted static memory, aiming to create readily available memory in advance, is inevitably subject to severe information loss")],
    67: [("We present the surprising finding that a language model's reasoning capabilities can be improved by training on synthetic datasets of chain-of-thought (CoT) traces from more capable models, even when all of those traces lead to an incorrect final answer.", "a language model's reasoning capabilities can be improved by training on synthetic datasets of chain-of-thought (CoT) traces from more capable models")],
    68: [("We formulate long-context language modeling as a problem in continual learning rather than architecture design.", "long-context language modeling as a problem in continual learning rather than architecture design")],
    69: [("Latent reasoning represents a new development in Transformer language models that has shown potential in compressing reasoning lengths compared to chain-of-thought reasoning.", "Latent reasoning represents a new development in Transformer language models that has shown potential in compressing reasoning lengths compared to chain-of-thought reasoning")],
    70: [("Test-time reinforcement learning (TTRL) offers a label-free paradigm for adapting models using only synthetic signals at inference, but its success hinges on constructing reliable learning signals.", "its success hinges on constructing reliable learning signals")],
    71: [("How can we use AI to discover a new state of the art for a scientific problem?", "How can we use AI to discover a new state of the art for a scientific problem?")],
    72: [("Typical reinforcement learning (RL) methods for LLM reasoning waste compute on hard problems, where correct on-policy traces are rare, policy gradients vanish, and learning stalls.", "Typical reinforcement learning (RL) methods for LLM reasoning waste compute on hard problems")],
}


def main():
    papers = json.load(open(SAMPLE, encoding="utf-8"))
    bad = []
    out = []
    for i, p in enumerate(papers, 1):
        abs_ = p["abstract"]
        rq = []
        for sent, phrase in MY.get(i, []):
            if sent not in abs_:
                bad.append((i, "sentence_not_in_abstract", sent[:40]))
                continue
            if phrase not in sent:
                bad.append((i, "phrase_not_in_sentence", phrase[:40]))
                continue
            rq.append({"sentence": sent, "phrase": phrase})
        out.append({"id": i, "lang": p["lang"], "abstract": abs_, "rq": rq})
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    n_rq = sum(len(o["rq"]) for o in out)
    print(f"已写出 gold：{OUT}  共 {len(out)} 篇  RQ标注 {n_rq} 条")
    n_empty = sum(1 for o in out if not o["rq"])
    print(f"无 RQ 标注（非研究问题文本）：{n_empty} 篇")
    if bad:
        print("标注字面校验失败：")
        for b in bad:
            print("  ", b)
    else:
        print("所有句子/短语字面校验通过。")


if __name__ == "__main__":
    main()
