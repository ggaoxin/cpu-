// 在线测试的文本模式只模拟用户直接粘贴的纯文本。
// PDF 页眉页脚、图片说明、公式版面和页码只允许出现在文件模式中。
const zhGroundMotion = '合理选取地震动记录是结构抗震分析的重要基础。传统方法通常依赖震级、距离和场地类别进行人工分组，难以客观描述记录之间的频谱差异。本文从 PEER 数据库选取地震动记录，先利用模糊聚类分析记录的震级与距离特征，再通过主成分分析对不同场地类别中的记录进行排序，形成自适应地震动记录推荐方法。实验结果表明，该方法能够提高记录选取的一致性，并为工程结构时程分析提供更可靠的输入。'

const zhMedical = '糖尿病肾病是糖尿病常见的微血管并发症。研究从 GEO 数据库获取相关转录组数据，利用加权基因共表达网络分析识别关键模块，并整合多种机器学习方法筛选特征基因。随后通过通路富集、免疫微环境关联和分子对接分析验证候选基因的诊断及治疗价值。结果表明，VWF 等基因具有较高的识别能力和潜在靶向价值，可为糖尿病肾病的精准诊疗提供参考。'

const zhManufacturing = '复杂工业表面中的裂纹、划痕和孔洞通常具有尺度差异大、边缘模糊及背景纹理干扰强等特点。本文提出融合多尺度特征增强和局部注意力的微小缺陷检测方法，通过跨层特征融合改善缺陷区域表征。多个公开数据集上的实验结果表明，该方法能够提高检测准确率与召回率，同时保持较低的推理延迟，适用于智能制造在线质量检测。'

const enVlm = 'Reinforcement learning can improve the reasoning performance of vision-language models, but it may also reduce the diversity of their reasoning paths. This study compares reinforcement-learning models with their base counterparts and finds that the former reason more deeply along a narrow set of strategies, while the latter explore broader alternatives. The proposed Multi-Group Policy Optimization method encourages diverse solutions during training. Experiments on established benchmarks show improved reasoning diversity and a better balance between accuracy and scalability.'

const enDiffusion = 'Diffusion models produce high-quality samples but require repeated denoising and therefore incur substantial inference cost. This study proposes timestep-aware block masking, which learns which network blocks should be executed or reused at each denoising step. Independent optimization and knowledge-guided mask refinement reduce memory consumption while preserving generation quality. Experiments across several diffusion architectures demonstrate consistent acceleration with limited quality loss.'

const enTimeSeries = 'Multivariate time-series anomaly detection is difficult because sensor noise, missing observations and operating-condition shifts can hide weak fault patterns. This study proposes a temporal graph framework that combines adaptive dependency learning, multi-scale temporal encoding and consistency regularization. Experiments on public industrial datasets show lower false-alarm rates and improved detection performance under heterogeneous operating conditions.'

const definitionText = '高校体育场馆的智慧化建设需要明确核心治理概念。智慧治理是以数据要素汇聚、智能分析和协同决策为基础，对高校体育场馆资源、服务与运营实施精细化管理的治理方式。数据驱动决策是利用场馆运行、用户行为和资源配置数据支持管理判断与方案优化的决策过程。上述概念共同构成场馆数字化运营的理论基础。'

const generalNerText = '刘亭亭、吕大刚和李鸿晶使用美国太平洋地震工程研究中心的 PEER 数据库开展地震动记录研究，并在南京完成了实验分析。'
const researchNerText = '研究使用PEER数据库中的水平双向地震动记录，采用模糊聚类和主成分分析开展特征处理，实现地震动记录自适应选取，并评估不同场地类别的频谱差异。'
const domainNerText = '研究从GEO数据库获取糖尿病肾病转录组数据，利用加权基因共表达网络分析和机器学习方法筛选关键基因，其中VWF具有潜在靶向治疗价值。'

type TextItem = { projectName: string; title: string; text: string }

const zhBatch: TextItem[] = [
  { projectName: '', title: '地震动记录选取的新视角：大数据与机器学习', text: zhGroundMotion },
  { projectName: '', title: '糖尿病肾病关键基因识别与潜在靶点分析', text: zhMedical },
  { projectName: '', title: '融合多尺度特征的工业表面微小缺陷检测', text: zhManufacturing },
]
const domainClassificationBatch: TextItem[] = [
  {
    projectName: '',
    title: '基于WGCNA和113种机器学习算法鉴定糖尿病肾病关键基因',
    text: zhMedical,
  },
  {
    projectName: '',
    title: '基于单细胞转录组的肿瘤免疫微环境细胞亚群识别',
    text: '利用单细胞转录组测序数据识别肿瘤免疫微环境中的关键细胞亚群，并分析其差异表达特征与免疫调控作用。',
  },
  {
    projectName: '',
    title: '蛋白质互作网络驱动的疾病药物靶点预测研究',
    text: '融合蛋白质互作网络、疾病相关基因与机器学习方法，预测候选药物靶点并评估其潜在治疗价值。',
  },
]
const definitionBatch: TextItem[] = [
  {
    projectName: '',
    title: '',
    text: '地震动记录选取需要兼顾记录间的相似性和频谱信息。模糊C-均值聚类是通过数据点对不同聚类中心的隶属度迭代更新，实现地震动记录软划分的方法。主成分分析是将多个相关频谱指标转换为少数综合指标，并据此对地震动记录进行排序的方法。两种方法结合后可提高地震动记录选取的一致性。',
  },
  {
    projectName: '',
    title: '',
    text: '糖尿病肾病研究需要从高维转录组数据中识别具有诊疗价值的分子特征。加权基因共表达网络分析是基于基因表达相关性构建共表达网络并识别关键模块的分析方法。特征基因是通过机器学习筛选得到、能够表征糖尿病肾病分子差异并具有诊断或治疗潜力的关键基因。研究据此筛选并验证VWF等候选基因。',
  },
  {
    projectName: '',
    title: '',
    text: '复杂工业表面的微小缺陷容易受到尺度变化和背景纹理干扰。多尺度特征增强是融合不同分辨率层级的视觉特征，以提高模型对尺度差异明显和微小缺陷表征能力的方法。跨层特征融合是联合建模浅层细节特征与深层语义特征，以改善复杂背景下缺陷区域表达的方法。两种机制共同提升了微小缺陷检测的准确率与召回率。',
  },
]
const generalNerBatch: TextItem[] = [
  { projectName: '', title: '', text: '余洪涛、佟志刚和崔芸熙来自石河子大学体育学院，研究团队在新疆石河子开展高校体育场馆智慧治理研究。' },
  { projectName: '', title: '', text: generalNerText },
  { projectName: '', title: '', text: '桂林医学院研究团队从GEO数据库获取糖尿病肾病转录组数据，并开展糖尿病肾病关键基因研究。' },
]
const researchNerBatch: TextItem[] = [
  {
    projectName: '',
    title: '大数据赋能高校体育场馆智慧化建设的现实困境与路径研究',
    text: '研究采用文献资料法和逻辑分析法，基于场馆运行数据分析大数据技术支持高校体育场馆智慧治理的作用机制，并讨论高校体育场馆可持续发展问题。',
  },
  {
    projectName: '',
    title: '地震动记录选取的新视角：大数据与机器学习',
    text: researchNerText,
  },
  {
    projectName: '',
    title: '基于WGCNA和113种机器学习算法鉴定糖尿病肾病关键基因',
    text: '研究从GEO数据库获取转录组数据，采用WGCNA和113种机器学习算法开展糖尿病肾病关键基因识别，并分析VWF的潜在诊疗价值。',
  },
]
const domainNerBatch: TextItem[] = [
  {
    projectName: '',
    title: '高校体育场馆智慧治理机制研究',
    text: '高校体育场馆智慧治理研究以高校体育场馆为研究对象，围绕数据治理体系和运营管理机制分析场馆智慧治理模式。',
  },
  {
    projectName: '',
    title: '地震动记录特征与工程指标分析',
    text: '研究以地震动记录为工程数据，分析震级、震中距与加速度反应谱之间的关系，用于地震工程场景下的记录筛选。',
  },
  {
    projectName: '',
    title: '糖尿病肾病关键基因识别与潜在靶点分析',
    text: domainNerText,
  },
]
const enBatch: TextItem[] = [
  { projectName: '', title: 'Divergent Thinking Through Reinforcement Learning in Vision-Language Models', text: enVlm },
  { projectName: '', title: 'Timestep-Aware Block Masking for Efficient Diffusion Inference', text: enDiffusion },
  { projectName: '', title: 'Adaptive Temporal Graph Learning for Multivariate Anomaly Detection', text: enTimeSeries },
]

export const pureSingleTextByTool: Record<string, string> = {
  'zh-classify': zhGroundMotion,
  'en-classify': enVlm,
  'domain-classify': zhMedical,
  'zh-keyword': zhGroundMotion,
  'en-keyword': enVlm,
  'rq-detect': zhGroundMotion,
  'definition-detect': definitionText,
  'general-ner': generalNerText,
  'research-ner': researchNerText,
  'domain-ner': domainNerText,
}

export const pureBatchTextByTool: Record<string, TextItem[]> = {
  'zh-classify': zhBatch,
  'en-classify': enBatch,
  'domain-classify': domainClassificationBatch,
  'zh-keyword': zhBatch,
  'en-keyword': enBatch,
  'rq-detect': zhBatch,
  'definition-detect': definitionBatch,
  'general-ner': generalNerBatch,
  'research-ner': researchNerBatch,
  'domain-ner': domainNerBatch,
}

export const pureCitationItems = [
  {
    documentText: '近年来，强化学习被广泛用于提升视觉语言模型的推理能力。已有研究指出，强化学习模型的性能上限仍受到基础模型能力约束[52]。这一结论促使研究者进一步关注推理路径多样性。',
    previousContext: '近年来，强化学习被广泛用于提升视觉语言模型的推理能力。',
    citationSentence: '已有研究指出，强化学习模型的性能上限仍受到基础模型能力约束[52]。',
    nextContext: '这一结论促使研究者进一步关注推理路径多样性。',
  },
  {
    documentText: '扩散模型需要反复执行去噪过程，因此推理成本较高。相关研究发现，相邻时间步的特征变化通常较小[20,29,30]。基于这一观察，可以复用部分网络模块的输出以提升采样效率。',
    previousContext: '扩散模型需要反复执行去噪过程，因此推理成本较高。',
    citationSentence: '相关研究发现，相邻时间步的特征变化通常较小[20,29,30]。',
    nextContext: '基于这一观察，可以复用部分网络模块的输出以提升采样效率。',
  },
]

