import type { InputMode } from '../types'
import { pureBatchTextByTool, pureSingleTextByTool } from './pure-text-demo.ts'
// 真实接口采集的响应快照（由 scripts/collect-real-responses.mjs 生成）。
// 优先于下方 alignXxx 合成数据，保证响应示例与真实接口输出一致。
import realResponses from './real-responses.generated.json' with { type: 'json' }

type AnyRecord = Record<string, any>

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value ?? {})) as T
}

function payloads(response: AnyRecord) {
  const data = response?.data ?? response
  if (!Array.isArray(data?.results)) return data ? [data] : []
  return data.results
    .map((item: any) => item?.result?.data ?? item?.result ?? item?.data?.data ?? item?.data ?? item)
    .filter(Boolean)
}

function batchFromPayloads(source: AnyRecord, items: AnyRecord[], mode: InputMode) {
  return {
    code: Number(source?.code ?? 200),
    message: 'batch_completed',
    data: {
      // 原型演示必须使用稳定批次号，保证响应示例与弹窗两次
      // 读取时完全一致；真实工程中的批次号仍由后端运行时生成。
      batch_id: `batch_demo_${mode === 'batch' ? 'files' : 'texts'}_${items.length}`,
      input_type: mode === 'batch' ? 'files' : 'texts',
      total: items.length,
      success_count: items.length,
      failed_count: 0,
      results: items.map((result, index) => ({
        index: index + 1,
        file_name: mode === 'batch' ? result.document?.source_file || result.document?.file_name || `demo_${index + 1}.pdf` : undefined,
        status: 'success',
        code: 200,
        result,
      })),
    },
  }
}

const zhPapers = [
  {
    title: '大数据赋能高校体育场馆智慧化建设的现实困境与路径研究',
    sourceFile: 'ch1.pdf',
    abstract: '本研究运用文献资料法、逻辑分析法，探究大数据赋能高校体育场馆智慧化建设的作用机理、现实困境与实现路径。研究发现，数据要素汇聚能够重塑管理决策并优化资源配置，但仍存在数据治理体系不完善、技术应用流于表面和管理协同机制缺位等问题。',
    keywords: ['大数据', '高校体育场馆', '智慧化建设', '数据治理', '运营管理'],
  },
  {
    title: '地震动记录选取的新视角：大数据与机器学习',
    sourceFile: 'ch4.pdf',
    abstract: '本文针对传统地震动记录选取依赖经验边界、难以客观反映记录关联规律的问题，将震级和震中距聚类分析与主成分排序结合，使用PEER NGA-West2数据库中的2157组水平双向地震动记录，形成面向工程结构时程分析的自适应地震动选取方法。',
    keywords: ['地震动选取', '聚类分析', '模糊C-均值', '主成分分析', '频谱特性'],
  },
  {
    title: '基于WGCNA和113种机器学习算法鉴定糖尿病肾病关键基因',
    sourceFile: 'ch8.pdf',
    abstract: '研究从GEO数据库获取糖尿病肾病转录组数据，利用WGCNA构建共表达网络，并整合113种机器学习算法筛选特征基因。研究鉴定出CEL、COL1A2、FN1、IL7R、LCN2、LTF、MMP7和VWF等关键基因，其中VWF表现出较好的潜在靶向治疗价值。',
    keywords: ['糖尿病肾病', 'WGCNA', '机器学习', '关键基因', 'VWF'],
  },
]

const enPapers = [
  {
    title: 'All Roads Lead to Rome: Incentivizing Divergent Thinking in Vision-Language Models',
    sourceFile: '18.pdf',
    abstract: 'The study compares reinforcement-learning vision-language models with their base models, identifies diversity collapse in GRPO, and proposes Multi-Group Policy Optimization to encourage divergent reasoning across multiple solutions.',
    keywords: ['reinforcement learning', 'vision-language models', 'divergent thinking', 'GRPO', 'Multi-Group Policy Optimization'],
  },
  {
    title: 'Timestep-Aware Block Masking for Efficient Diffusion Model Inference',
    sourceFile: '24.pdf',
    abstract: 'The work learns timestep-specific block masks for diffusion models, reuses cached features, and applies timestep-aware loss scaling and mask rectification to reduce inference cost while retaining generation quality.',
    keywords: ['diffusion model', 'timestep-aware masking', 'feature reuse', 'efficient inference', 'mask rectification'],
  },
  {
    title: 'TRIAGE: Hierarchical Visual Budgeting for Efficient Video Reasoning',
    sourceFile: '28.pdf',
    abstract: 'TRIAGE treats video reasoning as hierarchical resource allocation. It first selects keyframes and then allocates core and context tokens with relevance and diversity constraints to reduce memory and computation.',
    keywords: ['vision-language models', 'video reasoning', 'visual budgeting', 'keyframe selection', 'token allocation'],
  },
]

// These are the documents actually shown in the online-test text inputs.
// Classification fixtures must follow this order so a batch result can never
// be attached to a different document merely because both arrays have the
// same length.
const zhClassificationPapers = pureBatchTextByTool['zh-classify'].map((item, index) => ({
  title: item.title,
  sourceFile: `zh_classification_${index + 1}.txt`,
  abstract: item.text,
  keywords: [
    ['地震动选取', '聚类分析', '主成分分析', '结构抗震'],
    ['糖尿病肾病', 'WGCNA', '机器学习', '关键基因'],
    ['工业缺陷检测', '多尺度特征', '局部注意力', '智能制造'],
  ][index],
}))

const enClassificationPapers = pureBatchTextByTool['en-classify'].map((item, index) => ({
  title: item.title,
  sourceFile: `en_classification_${index + 1}.txt`,
  abstract: item.text,
  keywords: [
    ['vision-language models', 'reinforcement learning', 'divergent reasoning', 'policy optimization'],
    ['diffusion models', 'timestep-aware masking', 'feature reuse', 'efficient inference'],
    ['multivariate time series', 'anomaly detection', 'temporal graph', 'industrial monitoring'],
  ][index],
}))

// abstract-move 专用演示摘要：每篇都是含 5 个语步的完整摘要，语步切分带
// 在摘要中的字符 start/end 偏移，供响应示例按 V7.74 schema 还原 moves。
// 不复用 zhPapers/enPapers（其摘要未必 5 句齐全，且被分类/关键词等工具共用）。
type AbstractMovePaper = {
  title: string
  abstract: string
  language: 'zh' | 'en'
  moves: Array<{ label: string; text: string; start: number; end: number; confidence: number }>
}

const zhAbstractMovePapers: AbstractMovePaper[] = [
  {
    title: '大数据赋能高校体育场馆智慧化建设的现实困境与路径研究',
    abstract: '高校体育场馆管理正由经验管理向数据驱动的智慧治理转变，但仍面临数据孤岛与决策滞后等现实困境。本研究探究大数据赋能高校体育场馆智慧化建设的作用机理、现实困境与实现路径。采用文献资料法和逻辑分析法，围绕数据治理与运营协同开展归纳分析。研究发现，数据要素汇聚能够重塑管理决策并优化资源配置，但数据治理体系与协同机制仍不完善。由此提出应构建数据治理体系并创新运营管理机制，以促进高校体育场馆可持续发展。',
    language: 'zh',
    moves: [
      { label: '研究背景', text: '高校体育场馆管理正由经验管理向数据驱动的智慧治理转变，但仍面临数据孤岛与决策滞后等现实困境。', start: 0, end: 46, confidence: 0.92 },
      { label: '研究目的', text: '本研究探究大数据赋能高校体育场馆智慧化建设的作用机理、现实困境与实现路径。', start: 46, end: 83, confidence: 0.9 },
      { label: '研究方法', text: '采用文献资料法和逻辑分析法，围绕数据治理与运营协同开展归纳分析。', start: 83, end: 115, confidence: 0.88 },
      { label: '研究结果', text: '研究发现，数据要素汇聚能够重塑管理决策并优化资源配置，但数据治理体系与协同机制仍不完善。', start: 115, end: 159, confidence: 0.91 },
      { label: '研究结论', text: '由此提出应构建数据治理体系并创新运营管理机制，以促进高校体育场馆可持续发展。', start: 159, end: 197, confidence: 0.89 },
    ],
  },
  {
    title: '地震动记录选取的新视角：大数据与机器学习',
    abstract: '传统地震动选取依赖固定震级、距离分组和专家经验，难以客观反映记录间关联规律。本研究建立聚类分析与主成分分析相结合的自适应地震动记录选取方法。对2157组PEER地震动记录按震级和震中距聚类，并结合场地类别和主成分排序。地震动记录被划分为四组，并得到不同场地类别下的排序与推荐结果。该方法可为考虑不同结构需求参数的工程结构时程分析提供输入地震动。',
    language: 'zh',
    moves: [
      { label: '研究背景', text: '传统地震动选取依赖固定震级、距离分组和专家经验，难以客观反映记录间关联规律。', start: 0, end: 39, confidence: 0.91 },
      { label: '研究目的', text: '本研究建立聚类分析与主成分分析相结合的自适应地震动记录选取方法。', start: 39, end: 66, confidence: 0.9 },
      { label: '研究方法', text: '对2157组PEER地震动记录按震级和震中距聚类，并结合场地类别和主成分排序。', start: 66, end: 97, confidence: 0.89 },
      { label: '研究结果', text: '地震动记录被划分为四组，并得到不同场地类别下的排序与推荐结果。', start: 97, end: 127, confidence: 0.9 },
      { label: '研究结论', text: '该方法可为考虑不同结构需求参数的工程结构时程分析提供输入地震动。', start: 127, end: 157, confidence: 0.88 },
    ],
  },
  {
    title: '基于WGCNA和113种机器学习算法鉴定糖尿病肾病关键基因',
    abstract: '糖尿病肾病的关键衰老相关分泌蛋白基因及其治疗价值仍需系统识别。本研究鉴定糖尿病肾病关键基因并探索其分子机制和潜在治疗价值。采用WGCNA、113种机器学习算法、GSEA、药物富集和分子对接进行综合分析。筛选得到八个关键基因，其中VWF具有较好的诊断与潜在靶向治疗价值。研究为糖尿病肾病的精准诊疗与靶点发现提供了新的候选依据。',
    language: 'zh',
    moves: [
      { label: '研究背景', text: '糖尿病肾病的关键衰老相关分泌蛋白基因及其治疗价值仍需系统识别。', start: 0, end: 30, confidence: 0.9 },
      { label: '研究目的', text: '本研究鉴定糖尿病肾病关键基因并探索其分子机制和潜在治疗价值。', start: 30, end: 56, confidence: 0.89 },
      { label: '研究方法', text: '采用WGCNA、113种机器学习算法、GSEA、药物富集和分子对接进行综合分析。', start: 56, end: 86, confidence: 0.88 },
      { label: '研究结果', text: '筛选得到八个关键基因，其中VWF具有较好的诊断与潜在靶向治疗价值。', start: 86, end: 112, confidence: 0.91 },
      { label: '研究结论', text: '研究为糖尿病肾病的精准诊疗与靶点发现提供了新的候选依据。', start: 112, end: 138, confidence: 0.87 },
    ],
  },
]

const enAbstractMovePapers: AbstractMovePaper[] = [
  {
    title: 'All Roads Lead to Rome: Incentivizing Divergent Thinking in Vision-Language Models',
    abstract: 'Reinforcement learning can enhance vision-language model reasoning, but the effective mechanisms and limitations of multi-step sampling remain underexplored. This study investigates the behavioral difference between reinforcement-learning models and their base counterparts. Training dynamics and multi-sampling behavior are compared, followed by Multi-Group Policy Optimization. GRPO shows diversity collapse, while MUPO improves reasoning diversity and benchmark performance. Encouraging divergent solution paths improves the balance between accuracy and scalability.',
    language: 'en',
    moves: [
      { label: 'Background', text: 'Reinforcement learning can enhance vision-language model reasoning, but the effective mechanisms and limitations of multi-step sampling remain underexplored.', start: 0, end: 156, confidence: 0.92 },
      { label: 'Objective', text: 'This study investigates the behavioral difference between reinforcement-learning models and their base counterparts.', start: 158, end: 273, confidence: 0.9 },
      { label: 'Method', text: 'Training dynamics and multi-sampling behavior are compared, followed by Multi-Group Policy Optimization.', start: 275, end: 378, confidence: 0.89 },
      { label: 'Result', text: 'GRPO shows diversity collapse, while MUPO improves reasoning diversity and benchmark performance.', start: 380, end: 476, confidence: 0.91 },
      { label: 'Conclusion', text: 'Encouraging divergent solution paths improves the balance between accuracy and scalability.', start: 478, end: 568, confidence: 0.88 },
    ],
  },
  {
    title: 'Timestep-Aware Block Masking for Efficient Diffusion Model Inference',
    abstract: 'Diffusion models suffer from high latency because iterative denoising repeatedly executes the same network. This work seeks to reduce diffusion inference cost without sacrificing generation quality. Timestep-specific block masks, loss scaling, feature reuse, and mask rectification are jointly applied. The method provides substantial speedups across DDPM, LDM, DiT, and PixArt architectures. Per-timestep computational paths offer an efficient and architecture-agnostic acceleration route.',
    language: 'en',
    moves: [
      { label: 'Background', text: 'Diffusion models suffer from high latency because iterative denoising repeatedly executes the same network.', start: 0, end: 105, confidence: 0.91 },
      { label: 'Objective', text: 'This work seeks to reduce diffusion inference cost without sacrificing generation quality.', start: 106, end: 186, confidence: 0.9 },
      { label: 'Method', text: 'Timestep-specific block masks, loss scaling, feature reuse, and mask rectification are jointly applied.', start: 187, end: 285, confidence: 0.89 },
      { label: 'Result', text: 'The method provides substantial speedups across DDPM, LDM, DiT, and PixArt architectures.', start: 286, end: 372, confidence: 0.9 },
      { label: 'Conclusion', text: 'Per-timestep computational paths offer an efficient and architecture-agnostic acceleration route.', start: 373, end: 462, confidence: 0.88 },
    ],
  },
  {
    title: 'TRIAGE: Hierarchical Visual Budgeting for Efficient Video Reasoning',
    abstract: 'Video reasoning with vision-language models is constrained by temporal and spatial redundancy. The work aims to allocate visual computation to the most informative frames and tokens. TRIAGE combines frame-level budgeting with relevance- and diversity-aware token allocation. The framework reduces token count, inference time, and memory while preserving benchmark performance. Hierarchical visual budgeting is an effective training-free strategy for efficient video reasoning.',
    language: 'en',
    moves: [
      { label: 'Background', text: 'Video reasoning with vision-language models is constrained by temporal and spatial redundancy.', start: 0, end: 86, confidence: 0.9 },
      { label: 'Objective', text: 'The work aims to allocate visual computation to the most informative frames and tokens.', start: 87, end: 167, confidence: 0.89 },
      { label: 'Method', text: 'TRIAGE combines frame-level budgeting with relevance- and diversity-aware token allocation.', start: 168, end: 257, confidence: 0.88 },
      { label: 'Result', text: 'The framework reduces token count, inference time, and memory while preserving benchmark performance.', start: 258, end: 357, confidence: 0.91 },
      { label: 'Conclusion', text: 'Hierarchical visual budgeting is an effective training-free strategy for efficient video reasoning.', start: 358, end: 450, confidence: 0.87 },
    ],
  },
]

function alignAbstract(response: AnyRecord, english: boolean, startIndex = 0) {
  const result = clone(response)
  const papers = english ? enAbstractMovePapers : zhAbstractMovePapers
  payloads(result).forEach((data, index) => {
    const profileIndex = (startIndex + index) % papers.length
    const paper = papers[profileIndex]
    // V7.74 schema：moves 含 move_code/move_name/label/text/sentence_indices(从0起)/
    // start/end/confidence；data 含 move_count/sentence_count/move_statistics/
    // move_confidence/input_type/confidence。文本模式不暴露文件来源(source)。
    const moves = paper.moves.map((move, moveIndex) => ({
      move_code: move.label,
      move_name: move.label,
      label: move.label,
      text: move.text,
      sentence_indices: [moveIndex],
      start: move.start,
      end: move.end,
      confidence: move.confidence,
    }))
    const moveStatistics: AnyRecord = {}
    const moveConfidence: AnyRecord = {}
    for (const move of moves) {
      moveStatistics[move.label] = (moveStatistics[move.label] || 0) + 1
      moveConfidence[move.label] = move.confidence
    }
    const overallConfidence = Number((moves.reduce((sum, m) => sum + m.confidence, 0) / moves.length).toFixed(3))
    data.document = { title: paper.title, abstract: paper.abstract, abstract_complete: true, language: paper.language }
    data.moves = moves
    data.move_count = moves.length
    data.sentence_count = moves.length
    data.input_type = 'text'
    data.confidence = overallConfidence
    data.move_statistics = moveStatistics
    data.move_confidence = moveConfidence
  })
  // meta 改为 V7.74 真实链路风格，去掉合成标记 data_source:"synthetic"。
  result.meta = {
    request_id: `req_demo_abstract_${english ? 'en' : 'zh'}_${startIndex}`,
    schema_version: '1.0',
    model_version: 'semantic-toolkit-2026.08',
    elapsed_ms: 1180 + startIndex * 60,
    created_at: '2026-08-30T02:01:50.850021+00:00',
    database_dialect: 'mysql',
    task_id: `tsk_demo_abstract_${english ? 'en' : 'zh'}_${startIndex}`,
    input_type: 'text',
    total: 1,
    success_count: 1,
    failed_count: 0,
    record_id: `rec_demo_abstract_${english ? 'en' : 'zh'}_${startIndex}`,
  }
  return result
}

const classificationProfiles = {
  zh: [
    { paper: zhClassificationPapers[0], interdisciplinary: true, classes: [['P315.9', '地震工程', '天文学、地球科学 > 地球物理学 > 地震学 > 地震工程', 0.97], ['TU311.3', '结构抗震分析', '工业技术 > 建筑科学 > 建筑结构 > 结构抗震分析', 0.92]], labels: ['地震工程', '结构抗震'] },
    { paper: zhClassificationPapers[1], interdisciplinary: true, classes: [['R587.1', '糖尿病', '医药、卫生 > 内科学 > 内分泌腺疾病及代谢病 > 糖尿病', 0.95], ['Q811.4', '生物信息学', '生物科学 > 生物工程学 > 生物信息学', 0.91]], labels: ['糖尿病肾病', '生物信息学'] },
    { paper: zhClassificationPapers[2], interdisciplinary: false, classes: [['TP391.41', '图像处理与计算机视觉', '工业技术 > 自动化技术、计算机技术 > 计算机视觉', 0.96], ['TH17', '机械制造工艺', '工业技术 > 机械、仪表工业 > 机械制造工艺', 0.9]], labels: ['工业缺陷检测', '智能制造'] },
  ],
  en: [
    { paper: enClassificationPapers[0], interdisciplinary: false, classes: [['TP18', '人工智能', '工业技术 > 自动化技术、计算机技术 > 人工智能', 0.96]], labels: ['视觉语言模型', '强化学习'] },
    { paper: enClassificationPapers[1], interdisciplinary: false, classes: [['TP391.41', '图像处理与计算机视觉', '工业技术 > 自动化技术、计算机技术 > 计算机视觉', 0.94], ['TP301.6', '算法理论', '工业技术 > 自动化技术、计算机技术 > 计算机科学理论 > 算法理论', 0.89]], labels: ['扩散模型', '高效推理'] },
    { paper: enClassificationPapers[2], interdisciplinary: false, classes: [['TP274.2', '数据采集与处理', '工业技术 > 自动化技术、计算机技术 > 自动化技术及设备 > 数据处理', 0.95], ['TP18', '人工智能', '工业技术 > 自动化技术、计算机技术 > 人工智能', 0.9]], labels: ['时间序列异常检测', '工业智能监测'] },
  ],
}

function alignClassification(response: AnyRecord, language: 'zh' | 'en', startIndex = 0) {
  const result = clone(response)
  payloads(result).forEach((data, index) => {
    const profile = classificationProfiles[language][(startIndex + index) % 3]
    data.document = { ...(data.document || {}), title: profile.paper.title, abstract: profile.paper.abstract, keywords: profile.paper.keywords, language }
    data.document_title = profile.paper.title
    const majorCategories = new Set(profile.classes.map(([clcCode]) => String(clcCode).trim().charAt(0).toUpperCase()).filter(Boolean))
    // A document is interdisciplinary only when its official results cross
    // different top-level CLC categories (for example P + T or R + Q).
    // Different subclasses inside the same major category remain candidate
    // alternatives instead of being presented as a main/secondary pair.
    data.is_interdisciplinary = profile.interdisciplinary && majorCategories.size > 1
    data.classifications = profile.classes.map(([clc_code, label, path, confidence], classIndex) => ({
      order: classIndex + 1,
      role: classIndex ? 'secondary' : 'main',
      clc_code,
      label,
      path,
      confidence,
      evidence: profile.paper.keywords.slice(0, 3),
    }))
    data.classification_count = data.classifications.length
    data.classification_confidence = data.classifications[0]?.confidence
    data.domain_labels = profile.labels.map((label, labelIndex) => ({ label, confidence: Number((0.95 - labelIndex * 0.04).toFixed(2)), role: labelIndex ? 'secondary' : 'primary' }))
    delete data.candidate_classifications
  })
  return result
}

const domainPapers = [
  zhPapers[2],
  {
    title: '基于单细胞转录组的肿瘤免疫微环境细胞亚群识别',
    abstract: '利用单细胞转录组测序数据识别肿瘤免疫微环境中的关键细胞亚群，并分析其差异表达特征与免疫调控作用。',
    keywords: ['单细胞转录组', '肿瘤免疫微环境', '细胞亚群识别'],
  },
  {
    title: '蛋白质互作网络驱动的疾病药物靶点预测研究',
    abstract: '融合蛋白质互作网络、疾病相关基因与机器学习方法，预测候选药物靶点并评估其潜在治疗价值。',
    keywords: ['蛋白质互作网络', '药物靶点预测', '机器学习'],
  },
]

const domainPaths = [
  ['医学与生命科学', '生物信息学', '糖尿病肾病关键基因发现'],
  ['医学与生命科学', '生物信息学', '单细胞转录组分析'],
  ['医学与生命科学', '生物信息学', '疾病药物靶点预测'],
]

const domainCandidatePaths = [
  [['医学与生命科学', '医学信息学', '疾病关键基因发现'], ['医学与生命科学', '转化医学', '分子靶点筛选']],
  [['医学与生命科学', '计算生物学', '细胞类型注释'], ['医学与生命科学', '医学数据科学', '肿瘤微环境分析']],
  [['医学与生命科学', '系统生物学', '蛋白质网络分析'], ['医学与生命科学', '转化医学', '药物发现与评价']],
]

function alignDomainClassification(response: AnyRecord, startIndex = 0) {
  const result = clone(response)
  payloads(result).forEach((data, index) => {
    const profileIndex = (startIndex + index) % 3
    const paper = domainPapers[profileIndex]
    const [level_1, level_2, level_3] = domainPaths[profileIndex]
    data.document = { ...(data.document || {}), title: paper.title, abstract: paper.abstract, keywords: paper.keywords, language: 'zh' }
    data.document_title = paper.title
    data.multilevel_classification_results = [{ order: 1, role: 'main', level_1, level_2, level_3, classification_path: [level_1, level_2, level_3], confidence: 0.95, evidence: paper.keywords.slice(0, 3) }]
    data.classification_confidence = { overall: 0.95, level_1: 0.98, level_2: 0.96, level_3: 0.92 }
    data.professional_domain = '生物医学信息学'
    data.domain_match_result = {
      status: 'matched',
      match_score: 0.95,
      selected_domain: { code: 'biomedical_informatics', name: '生物医学信息学' },
    }
    data.domain_labels = paper.keywords.slice(0, 3).map((label, labelIndex) => ({ label, confidence: Number((0.95 - labelIndex * 0.03).toFixed(2)) }))
    data.candidate_classifications = domainCandidatePaths[profileIndex].map((path, candidateIndex) => ({
      candidate_id: `domain_${profileIndex + 1}_${candidateIndex + 1}`,
      candidate_rank: candidateIndex + 1,
      level_1: path[0], level_2: path[1], level_3: path[2],
      classification_path: path,
      confidence: Number((0.89 - candidateIndex * 0.05).toFixed(2)),
    }))
    data.data_distribution_report = { document_count: 1, classified_document_count: 1, classification_assignment_count: 1, by_level_1: [{ category: level_1, document_count: 1, percentage: 100 }], by_level_2: [{ category: level_2, assignment_count: 1 }], by_level_3: [{ category: level_3, assignment_count: 1 }] }
  })
  return result
}

function alignKeywords(response: AnyRecord, english: boolean, startIndex = 0) {
  const result = clone(response)
  payloads(result).forEach((data, index) => {
    const paper = (english ? enClassificationPapers : zhClassificationPapers)[(startIndex + index) % 3]
    data.document = { ...(data.document || {}), abstract: paper.abstract, language: english ? 'en' : 'zh', abstract_complete: true, title: paper.title, source_file: paper.sourceFile }
    if (english) {
      data.keywords_or_topic_phrases = paper.keywords.map((term, rank) => ({ rank: rank + 1, term, type: term.includes(' ') ? 'topic_phrase' : 'keyword', normalized_term: term.toLowerCase(), confidence: Number((0.97 - rank * 0.02).toFixed(2)), source_position: { start: 25 + rank * 52, end: 25 + rank * 52 + term.length }, adaptive_resource_match: rank < 2, terminology_source: { type: 'external', library_name: '人工智能英文术语库' }, classification_mapping: { system: 'CLC', code: rank < 2 ? 'TP18' : 'TP391.41', label: rank < 2 ? '人工智能' : '计算机视觉', confidence: Number((0.95 - rank * 0.02).toFixed(2)) } }))
      data.term_count = data.keywords_or_topic_phrases.length
    } else {
      data.keywords = paper.keywords.map((keyword, rank) => ({ rank: rank + 1, keyword, type: keyword.length > 5 ? '关键短语' : '关键词', confidence: Number((0.98 - rank * 0.02).toFixed(2)), source_position: { start: 35 + rank * 48, end: 35 + rank * 48 + keyword.length }, adaptive_resource_match: rank < 2, custom_dictionary_hit: rank < 2, weight_change: rank < 2 ? 0.08 - rank * 0.02 : 0 }))
      data.keyword_count = data.keywords.length
    }
  })
  return result
}

const rqProfiles = [
  ['如何客观刻画不同地震动记录之间的频谱特性与关联规律？', '如何结合聚类分析与主成分分析实现自适应地震动记录选取？', '不同场地类别和聚类分组下的地震动推荐结果有何差异？'],
  ['哪些衰老相关分泌蛋白基因可作为糖尿病肾病的关键特征？', '如何结合WGCNA与多种机器学习算法提高关键基因筛选稳定性？', '关键基因的调控机制与潜在治疗价值如何验证？'],
  ['如何增强复杂工业表面微小缺陷的多尺度特征表达？', '如何结合跨层特征融合与局部注意力提高缺陷识别精度？', '该方法能否兼顾在线质量检测的准确率与推理效率？'],
]

function rqPayload(index: number) {
  const paper = zhClassificationPapers[index % 3]
  const questions = rqProfiles[index % 3]
  const constraintProfiles = [
    [
      ['震级与震中距范围限制', '场地类别差异', '地震动样本代表性'],
      ['聚类分组稳定性', '主成分排序一致性', '工程计算效率'],
      ['不同场地类别', '不同聚类分组', '规范反应谱约束'],
    ],
    [
      ['样本规模有限', '批次效应', '疾病异质性'],
      ['类别不平衡', '算法结果一致性', '特征筛选稳定性'],
      ['外部队列验证', '生物学机制证据', '临床转化可行性'],
    ],
    [
      ['缺陷尺度差异', '边缘模糊', '复杂背景纹理干扰'],
      ['跨层特征对齐', '注意力计算开销', '小样本类别不平衡'],
      ['在线检测时延', '设备算力限制', '跨数据集泛化能力'],
    ],
  ]
  const constraints = constraintProfiles[index % 3]
  return {
    tool: '研究问题识别', input_type: 'text',
    input: { file_name: paper.sourceFile, file_format: 'PDF', document_parse_status: 'success', section_extraction_status: 'success', text_format_validation_status: 'success' },
    document: { title: paper.title, language: 'zh', page_count: index === 1 ? 12 : 8, analysis_scope: ['摘要', '引言', '研究方法', '结论'] },
    research_question_sentences: questions.map((sentence, i) => ({ sentence_id: `S-${index + 1}-${i + 1}`, sentence, expression_type: i === 1 ? 'implicit' : 'explicit', trigger_patterns: i === 1 ? ['问题陈述'] : ['如何'], confidence: 0.97 - i * 0.02, position: { source_section: i === 0 ? '摘要' : i === 1 ? '引言 > 研究问题' : '结论 > 研究展望' } })),
    research_question_phrases: questions.map((question, i) => ({ phrase_id: `P-${index + 1}-${i + 1}`, sentence_id: `S-${index + 1}-${i + 1}`, phrase: question.replace(/[？?]$/, ''), normalized_question: question, confidence: 0.96 - i * 0.02 })),
    structured_research_questions: questions.map((question, i) => ({ research_question_id: `RQ-${index + 1}-${i + 1}`, role: i === 0 ? '核心问题' : '子问题', parent_question_id: i === 0 ? null : `RQ-${index + 1}-1`, question, question_type: i === 0 ? '机理与目标问题' : '方法与验证问题', research_object: paper.keywords[0], research_targets: paper.keywords.slice(1, 3), constraints: constraints[i], evidence_sentence_ids: [`S-${index + 1}-${i + 1}`], source_phrase_ids: [`P-${index + 1}-${i + 1}`], confidence: 0.96 - i * 0.02 })),
    research_question_statistics: { analyzed_section_count: 4, research_question_sentence_count: 3, explicit_question_sentence_count: 2, implicit_question_sentence_count: 1, research_question_phrase_count: 3, structured_question_count: 3, main_question_count: 1, sub_question_count: 2, question_type_distribution: [{ question_type: '核心问题', count: 1, percentage: 33.3 }, { question_type: '子问题', count: 2, percentage: 66.7 }], average_confidence: 0.95 },
  }
}

function alignResearchQuestions(response: AnyRecord, startIndex = 0) {
  const result = clone(response)
  payloads(result).forEach((data, index) => Object.assign(data, rqPayload(startIndex + index)))
  return result
}

const citationProfiles = [
  {
    paper: enPapers[0], marker: '[52]', sentence: 'Early doubts arise from LLM studies, where prior work [52] observes that performance ceilings remain constrained by base-model capabilities.',
    previous: 'Recent studies have demonstrated that reinforcement learning can enhance reasoning capabilities.', next: 'These findings motivate a direct comparison between RL models and their base counterparts.',
    sentiment: '局限性', sentimentCode: 'limitation', intent: '结果比较', intentCode: 'result_comparison', evidence: 'performance ceilings remain constrained', work: 'Reasoning limits of reinforcement learning models', authors: ['Prior research team'],
  },
  {
    paper: enPapers[1], marker: '[20, 29, 30, 38, 48]', sentence: 'Recent findings [20, 29, 30, 38, 48] indicate minimal variation in adjacent-timestep features.',
    previous: 'Diffusion models repeatedly execute denoising blocks and incur high inference costs.', next: 'This observation motivates feature reuse and timestep-specific computation.',
    sentiment: '支持', sentimentCode: 'support', intent: '方法引入', intentCode: 'method_introduction', evidence: 'indicate minimal variation', work: 'Feature reuse for diffusion acceleration', authors: ['Related diffusion-model researchers'],
  },
  {
    paper: enPapers[2], marker: '[8]', sentence: 'Frame-level methods have evolved from uniform sampling to adaptive methods that identify and discard irrelevant frames [8].',
    previous: 'Video reasoning suffers from temporal and spatial redundancy.', next: 'TRIAGE further unifies frame selection and token allocation as hierarchical visual budgeting.',
    sentiment: '中立', sentimentCode: 'neutral', intent: '背景介绍', intentCode: 'background_introduction', evidence: 'have evolved from uniform sampling to adaptive methods', work: 'Adaptive frame sampling for video understanding', authors: ['Prior video-reasoning researchers'],
  },
]

function citationPayload(index: number, intent: boolean) {
  const profile = citationProfiles[index % citationProfiles.length]
  const common = {
    citation_id: `CIT-${index + 1}`, citation_markers: [profile.marker], citation_sentence: profile.sentence,
    context: { previous_sentence: profile.previous, current_sentence: profile.sentence, next_sentence: profile.next },
    citation_metadata: { reference_id: `REF-${index + 1}`, citation_marker: profile.marker, cited_authors: profile.authors, authors: profile.authors, work_name: profile.work, year: 2025 },
    evidence_phrase: profile.evidence, source_position: { source_section: 'Introduction > Related Work' }, confidence: 0.96 - index * 0.02,
  }
  return intent ? { ...common, intent: profile.intent, intent_code: profile.intentCode, matched_training_examples: [] } : { ...common, sentiment: profile.sentiment, sentiment_code: profile.sentimentCode }
}

function alignCitation(response: AnyRecord, intent: boolean, startIndex = 0) {
  const result = clone(response)
  payloads(result).forEach((data, index) => {
    const profileIndex = (startIndex + index) % 3
    const profile = citationProfiles[profileIndex]
    data.document = { ...(data.document || {}), title: profile.paper.title, language: 'en', page_count: 12, source_file: profile.paper.sourceFile, analysis_scope: ['Introduction', 'Related Work'] }
    const key = intent ? 'citation_intent_results' : 'citation_sentiment_results'
    data[key] = [citationPayload(profileIndex, intent)]
    if (intent) {
      data.citation_intent_statistics = { citation_count: 1, background_introduction_count: profile.intentCode === 'background_introduction' ? 1 : 0, method_introduction_count: profile.intentCode === 'method_introduction' ? 1 : 0, result_comparison_count: profile.intentCode === 'result_comparison' ? 1 : 0, intent_distribution: [{ intent: profile.intent, count: 1, percentage: 100 }], average_confidence: 0.96 - index * 0.02 }
      delete data.training_set_summary
    } else {
      data.citation_sentiment_statistics = { citation_sentence_count: 1, support_count: profile.sentimentCode === 'support' ? 1 : 0, neutral_count: profile.sentimentCode === 'neutral' ? 1 : 0, limitation_count: profile.sentimentCode === 'limitation' ? 1 : 0, sentiment_distribution: [{ sentiment: profile.sentiment, count: 1, percentage: 100 }], average_confidence: 0.96 - index * 0.02 }
    }
  })
  return result
}

const definitionsByPaper = [
  [
    ['智慧治理', '智慧治理是以数据要素汇聚、智能分析和协同决策为基础，对高校体育场馆资源、服务与运营实施精细化管理的治理方式。'],
    ['数据驱动决策', '数据驱动决策是利用场馆运行、用户行为和资源配置数据支持管理判断与方案优化的决策过程。'],
  ],
  [
    ['模糊C-均值聚类', '模糊C-均值聚类是通过数据点对不同聚类中心的隶属度迭代更新，实现地震动记录软划分的方法。'],
    ['主成分分析', '主成分分析是将多个相关频谱指标转换为少数综合指标，并据此对地震动记录进行排序的方法。'],
  ],
  [
    ['加权基因共表达网络分析', '加权基因共表达网络分析是基于基因表达相关性构建共表达网络并识别关键模块的分析方法。'],
    ['特征基因', '特征基因是通过机器学习筛选得到、能够表征糖尿病肾病分子差异并具有诊断或治疗潜力的关键基因。'],
  ],
  [
    ['多尺度特征增强', '多尺度特征增强是融合不同分辨率层级的视觉特征，以提高模型对尺度差异明显和微小缺陷表征能力的方法。'],
    ['跨层特征融合', '跨层特征融合是联合建模浅层细节特征与深层语义特征，以改善复杂背景下缺陷区域表达的方法。'],
  ],
]

const definitionDocuments = [
  zhPapers[0],
  zhPapers[1],
  zhPapers[2],
  { title: '融合多尺度特征的工业表面微小缺陷检测', sourceFile: 'manufacturing.txt' },
]

function definitionPayload(index: number) {
  const profileIndex = index % definitionsByPaper.length
  const inputText = profileIndex === 0
    ? pureSingleTextByTool['definition-detect']
    : pureBatchTextByTool['definition-detect'][profileIndex - 1]?.text || ''
  const definitions = definitionsByPaper[profileIndex].map(([concept, sentence], itemIndex) => ({
    definition_id: `DEF-${index + 1}-${itemIndex + 1}`, concept, definition_sentence: sentence, definition_content: sentence.replace(/^.+?是/, ''),
    position: (() => {
      const startIndex = inputText.indexOf(sentence)
      return startIndex >= 0
        ? { start: startIndex + 1, end: startIndex + sentence.length, __demo_exact: true }
        : { chapter_path: [itemIndex ? '（二）理论与方法' : '（一）研究背景', itemIndex ? '2．方法定义' : '1．核心概念', `1.${itemIndex + 1} ${concept}`] }
    })(), confidence: 0.97 - itemIndex * 0.02, review_status: '已确认',
  }))
  return {
    definitions,
    concept_definition_mappings: definitions.map(item => ({ concept: item.concept, definition: item.definition_content })),
    summary: { definition_sentence_count: 2, concept_count: 2, mapping_count: 2, average_confidence: 0.96, pending_review_count: 0 },
    statistical_analysis_report: { definition_sentence_count: 2, concept_count: 2, mapping_count: 2, pending_review_count: 0, section_distribution: [{ section: '研究背景', count: 1, percentage: 50 }, { section: '理论与方法', count: 1, percentage: 50 }] },
    document: { title: definitionDocuments[profileIndex].title, source_file: definitionDocuments[profileIndex].sourceFile },
  }
}

function alignDefinitions(response: AnyRecord, startIndex = 0) {
  const result = clone(response)
  payloads(result).forEach((data, index) => Object.assign(data, definitionPayload(startIndex + index)))
  return result
}

const generalEntities = [
  [
    ['余洪涛', 'PERSON', 'PERSON-CN-001', '本文作者为余洪涛、佟志刚和崔芸熙。'],
    ['佟志刚', 'PERSON', 'PERSON-CN-002', '本文作者为余洪涛、佟志刚和崔芸熙。'],
    ['崔芸熙', 'PERSON', 'PERSON-CN-003', '本文作者为余洪涛、佟志刚和崔芸熙。'],
    ['石河子大学体育学院', 'ORGANIZATION', 'ORG-CN-SHZU-SPORT', '作者来自石河子大学体育学院。'],
    ['新疆石河子', 'LOCATION', 'LOC-CN-XJ-SHZ', '研究机构位于新疆石河子。'],
  ],
  [
    ['刘亭亭', 'PERSON', 'PERSON-CN-004', '刘亭亭、吕大刚和李鸿晶使用美国太平洋地震工程研究中心的PEER数据库开展地震动记录研究。'],
    ['吕大刚', 'PERSON', 'PERSON-CN-005', '刘亭亭、吕大刚和李鸿晶使用美国太平洋地震工程研究中心的PEER数据库开展地震动记录研究。'],
    ['李鸿晶', 'PERSON', 'PERSON-CN-006', '刘亭亭、吕大刚和李鸿晶使用美国太平洋地震工程研究中心的PEER数据库开展地震动记录研究。'],
    ['美国太平洋地震工程研究中心', 'ORGANIZATION', 'ORG-US-PEER', '研究使用美国太平洋地震工程研究中心PEER数据库。'],
    ['南京', 'LOCATION', 'LOC-CN-NANJING', '研究团队在南京完成实验分析。'],
  ],
  [
    ['桂林医学院', 'ORGANIZATION', 'ORG-CN-GLMU', '研究团队来自桂林医学院及其附属机构。'],
    ['糖尿病肾病关键基因研究', 'EVENT', 'EVENT-DN-GENE', '团队开展糖尿病肾病关键基因识别研究。'],
  ],
]

function generalNerPayload(index: number) {
  const profileIndex = index % 3
  const inputText = pureBatchTextByTool['general-ner'][profileIndex]?.text || ''
  const entities = generalEntities[profileIndex].map(([text, type, _id], itemIndex) => {
    const startIndex = inputText.indexOf(text)
    return {
      entity_id: `GNER-${index + 1}-${itemIndex + 1}`,
      text,
      type,
      language: 'zh',
      position: startIndex >= 0
        ? { start: startIndex + 1, end: startIndex + text.length, __demo_exact: true }
        : { chapter_path: ['（一）文献信息', type === 'PERSON' ? '1．人物信息' : '2．机构与地点', `1.${itemIndex + 1} 实体位置`] },
      context: inputText,
      confidence: Math.max(0.88, 0.99 - itemIndex * 0.015),
    }
  })
  return {
    summary: { entity_count: entities.length, person_count: entities.filter(item => item.type === 'PERSON').length, location_count: entities.filter(item => item.type === 'LOCATION').length, organization_count: entities.filter(item => item.type === 'ORGANIZATION').length, event_count: entities.filter(item => item.type === 'EVENT').length },
    entities,
    document: { title: zhPapers[index % 3].title, source_file: zhPapers[index % 3].sourceFile },
  }
}

const researchEntities = [
  [
    ['文献资料法', '科研方法', 'Literature Review Method'], ['逻辑分析法', '科研方法', 'Logical Analysis'], ['场馆运行数据', '数据资料', 'Venue Operational Data'], ['智慧治理', '理论原理', 'Smart Governance'], ['高校体育场馆可持续发展', '研究问题', 'Sustainable Development of University Sports Venues'],
  ],
  [
    ['模糊聚类', '科研方法', 'Fuzzy Clustering'], ['主成分分析', '科研方法', 'Principal Component Analysis'], ['PEER数据库', '数据资料', 'PEER Database'], ['水平双向地震动记录', '数据资料', 'Horizontal Bidirectional Ground-Motion Records'], ['地震动记录自适应选取', '研究问题', 'Adaptive Ground-Motion Selection'],
  ],
  [
    ['WGCNA', '科研方法', 'Weighted Gene Co-expression Network Analysis'], ['机器学习', '科研方法', 'Machine Learning'], ['GEO数据库', '数据资料', 'GEO Database'], ['糖尿病肾病关键基因识别', '研究问题', 'Key-Gene Identification for Diabetic Nephropathy'],
  ],
]

function researchNerPayload(index: number) {
  const profileIndex = index % 3
  const inputText = pureBatchTextByTool['research-ner'][profileIndex]?.text || pureSingleTextByTool['research-ner'] || ''
  const entities = researchEntities[profileIndex].map(([text, type, en], itemIndex) => {
    const startIndex = inputText.indexOf(text)
    return {
      research_entity_id: `RNER-${index + 1}-${itemIndex + 1}`,
      text,
      type,
      language: 'zh',
      position: startIndex >= 0
        ? { start: startIndex + 1, end: startIndex + text.length, __demo_exact: true }
        : { chapter_path: ['（二）研究内容', itemIndex < 2 ? '2．研究方法' : '3．数据与问题', `2.${itemIndex + 1} ${text}`] },
      context: inputText,
      standard_term_id: `STD-${index + 1}-${itemIndex + 1}`,
      standard_names: { zh: text, en },
      confidence: 0.98 - itemIndex * 0.015,
    }
  })
  return {
    summary: { entity_count: entities.length, method_count: entities.filter(item => item.type === '科研方法').length, data_resource_count: entities.filter(item => item.type === '数据资料').length, instrument_count: 0, theory_principle_count: entities.filter(item => item.type === '理论原理').length, research_problem_count: entities.filter(item => item.type === '研究问题').length },
    entities,
    standard_term_mappings: entities.map(item => ({ standard_term_id: item.standard_term_id, standard_names: item.standard_names, abbreviations: [], other_aliases: [], observed_mentions: [{ text: item.text }], type: item.type, mapping_status: '已映射', mapping_confidence: item.confidence })),
    document: { title: pureBatchTextByTool['research-ner'][profileIndex]?.title || zhPapers[profileIndex].title, source_file: zhPapers[profileIndex].sourceFile },
  }
}

const domainEntityProfiles = [
  [['高校体育场馆', '研究对象', 'SPORT:VENUE'], ['智慧治理', '治理模式', 'SPORT:GOVERNANCE'], ['数据治理体系', '管理机制', 'SPORT:DATA-GOVERNANCE'], ['运营管理机制', '管理机制', 'SPORT:OPERATION']],
  [['地震动记录', '工程数据', 'EQ:GROUND-MOTION'], ['震级', '地震参数', 'EQ:MAGNITUDE'], ['震中距', '地震参数', 'EQ:DISTANCE'], ['加速度反应谱', '工程指标', 'EQ:RESPONSE-SPECTRUM']],
  [['糖尿病肾病', '疾病', 'MESH:DN'], ['VWF', '基因', 'HGNC:12726'], ['转录组数据', '生物医学数据', 'DATA:TRANSCRIPTOME'], ['加权基因共表达网络分析', '生物信息分析方法', 'METHOD:WGCNA'], ['GEO数据库', '生物医学数据库', 'DB:GEO']],
]

function domainNerPayload(index: number) {
  const profileIndex = index % 3
  const domainName = profileIndex === 0 ? '体育科学' : profileIndex === 1 ? '地震工程' : '医学'
  const inputText = pureBatchTextByTool['domain-ner'][profileIndex]?.text || pureSingleTextByTool['domain-ner'] || ''
  const entities = domainEntityProfiles[profileIndex].map(([text, type, id], itemIndex) => {
    const startIndex = inputText.indexOf(text)
    return {
      entity_id: `DNER-${index + 1}-${itemIndex + 1}`,
      text,
      domain_name: domainName,
      type,
      position: startIndex >= 0
        ? { start: startIndex + 1, end: startIndex + text.length, __demo_exact: true }
        : { chapter_path: ['（二）研究内容', itemIndex < 2 ? '1．研究对象' : '2．方法与数据', `2.${itemIndex + 1} ${text}`] },
      context: inputText,
      standard_kb_id: id,
      confidence: 0.98 - itemIndex * 0.02,
    }
  })
  return {
    selected_domain: profileIndex === 0 ? 'sports_science' : profileIndex === 1 ? 'earthquake_engineering' : 'medicine',
    summary: { entity_count: entities.length, mapped_count: entities.length, pending_review_count: 0 },
    entities,
    ontology_mappings: entities.map(item => ({ standard_kb_id: item.standard_kb_id, domain_name: item.domain_name, type: item.type, standard_names: { zh: item.text, en: item.text }, ontology_path: `${item.domain_name} / ${item.type} / ${item.text}`, aliases: [], observed_mentions: [{ text: item.text }], mapping_status: '已映射', mapping_confidence: item.confidence })),
    document: { title: pureBatchTextByTool['domain-ner'][profileIndex]?.title || zhPapers[profileIndex].title, source_file: zhPapers[profileIndex].sourceFile },
  }
}

function alignNer(response: AnyRecord, variant: 'general' | 'research' | 'domain', startIndex = 0) {
  const result = clone(response)
  payloads(result).forEach((data, index) => {
    const profileIndex = startIndex + index
    Object.assign(data, variant === 'general' ? generalNerPayload(profileIndex) : variant === 'research' ? researchNerPayload(profileIndex) : domainNerPayload(profileIndex))
    if (variant === 'general') {
      delete data.entity_mappings
      delete data.mappings
    }
  })
  return result
}

const deepClusterResponse = {
  code: 200, message: 'clustering_completed',
  data: {
    tool: '深度聚类工具', input_type: 'texts', cluster_dimension: 'technology', cluster_dimension_name: '技术路线',
    input_summary: { document_count: 5, parsed_sentence_count: 286, file_names: ['18.pdf', '24.pdf', '28.pdf', '26.pdf', '30.pdf'], extracted_fields: ['text', 'publication_date'], year_range: [2026, 2026] },
    clustering_quality: { cluster_count: 3, noise_document_count: 0, silhouette_score: 0.781, average_intra_cluster_similarity: 0.846, average_inter_cluster_separation: 0.802 },
    training_evaluation: {
      dataset_version: 'DEEP-CLUSTER-DEMO-EVAL-2026.08',
      evidence_status: 'prototype_demo_configuration',
      notice: '当前数值用于原型演示，正式系统应从所选人工标注评测资源计算并返回；未配置评测资源时应显示“未配置”，不能用 0 代替。',
      metrics: {
        silhouette_score: 0.781,
        normalized_mutual_information: 0.804,
        adjusted_rand_index: 0.762,
        expert_agreement: 0.860,
      },
    },
    clusters: [
      { cluster_id: 'TECH-01', size: 2, ratio: 0.4, representative_terms: ['推理多样性', '策略优化', '慢思考', '多步推理'], representative_sentences: ['通过策略优化或慢思考机制增强模型的多路径推理能力。'], feature_statistics: { intra_cluster_similarity: 0.84, inter_cluster_separation: 0.81, semantic_density: 0.86, average_sentence_count: 58 }, representative_documents: [{ document_id: 'DOC-EN-018', title: enPapers[0].title, publication_year: 2026 }, { document_id: 'DOC-EN-026', title: 'Can Slow-Thinking LLMs Reason Over Time?', publication_year: 2026 }] },
      { cluster_id: 'TECH-02', size: 2, ratio: 0.4, representative_terms: ['分层资源分配', '块掩码', '特征复用', '高效推理'], representative_sentences: ['根据时间步、关键帧和视觉令牌重要性动态分配推理计算。'], feature_statistics: { intra_cluster_similarity: 0.87, inter_cluster_separation: 0.82, semantic_density: 0.88, average_sentence_count: 61 }, representative_documents: [{ document_id: 'DOC-EN-024', title: enPapers[1].title, publication_year: 2026 }, { document_id: 'DOC-EN-028', title: enPapers[2].title, publication_year: 2026 }] },
      { cluster_id: 'TECH-03', size: 1, ratio: 0.2, representative_terms: ['前景引导', '多视图预训练', '自适应表征'], representative_sentences: ['利用前景视图引导预训练过程聚焦目标区域并改善视觉表征。'], feature_statistics: { intra_cluster_similarity: 0.79, inter_cluster_separation: 0.78, semantic_density: 0.81, average_sentence_count: 54 }, representative_documents: [{ document_id: 'DOC-EN-030', title: 'FVG-PT: Adaptive Foreground View-Guided Pre-Training', publication_year: 2026 }] },
    ],
    document_assignments: [
      ['DOC-EN-018', enPapers[0].title, 'TECH-01', 0.89, '强化学习、多路径策略与推理多样性特征突出'],
      ['DOC-EN-026', 'Can Slow-Thinking LLMs Reason Over Time?', 'TECH-01', 0.82, '慢思考与多步时间推理机制相近'],
      ['DOC-EN-024', enPapers[1].title, 'TECH-02', 0.88, '按时间步实施块级计算裁剪与特征复用'],
      ['DOC-EN-028', enPapers[2].title, 'TECH-02', 0.86, '按关键帧和令牌层级分配视觉计算预算'],
      ['DOC-EN-030', 'FVG-PT: Adaptive Foreground View-Guided Pre-Training', 'TECH-03', 0.84, '以前景视图引导自适应预训练'],
    ].map(([document_id, title, cluster_id, similarity_to_centroid, key_evidence]) => ({ document_id, title, publication_year: 2026, cluster_id, similarity_to_centroid, key_evidence })),
    semantic_projection: [
      { document_id: 'DOC-EN-018', cluster_id: 'TECH-01', x: 18, y: 24 }, { document_id: 'DOC-EN-026', cluster_id: 'TECH-01', x: 27, y: 31 },
      { document_id: 'DOC-EN-024', cluster_id: 'TECH-02', x: 64, y: 22 }, { document_id: 'DOC-EN-028', cluster_id: 'TECH-02', x: 72, y: 30 },
      { document_id: 'DOC-EN-030', cluster_id: 'TECH-03', x: 48, y: 72 },
    ],
    theme_trend_analysis: { years: [2026], series: [{ cluster_id: 'TECH-01', representative_terms: ['推理多样性', '慢思考'], yearly_counts: [2], trend_score: 0.86 }, { cluster_id: 'TECH-02', representative_terms: ['高效推理', '资源分配'], yearly_counts: [2], trend_score: 0.9 }, { cluster_id: 'TECH-03', representative_terms: ['前景引导预训练'], yearly_counts: [1], trend_score: 0.77 }], rising_cluster_id: 'TECH-02', emerging_cluster_id: 'TECH-03', stable_cluster_id: 'TECH-01', summary: '2026年样本文献集中关注推理多样性与计算效率，前景引导预训练构成独立的新兴技术路线。' },
  },
}

const clusterLabelResponse = {
  code: 200, message: 'success', data: {
    cluster_count: 3, generated_label_count: 3, generation_strategy: 'multi_strategy_fusion', parameters: { label_length_limit: 12, language_type: 'zh', distinctiveness_threshold: 0.75 },
    labels: [
      { cluster_id: 'TECH-01', recommended_label: '多路径推理优化', confidence: 0.94, distinctiveness: 0.9, difference_explanation: '突出策略优化、慢思考和推理多样性，与计算裁剪路线区分明显。', linked_document_ids: ['DOC-EN-018', 'DOC-EN-026'], candidate_labels: [{ rank: 1, label: '多路径推理优化', confidence: 0.94 }, { rank: 2, label: '推理多样性增强', confidence: 0.91 }], evidence: { keywords: ['推理多样性', '策略优化', '慢思考'], named_entities: ['MUPO', 'TimeReasoner'], center_sentence: '通过策略优化和慢思考机制扩展模型的多步推理路径。', text_count: 2 } },
      { cluster_id: 'TECH-02', recommended_label: '分层计算预算', confidence: 0.95, distinctiveness: 0.92, difference_explanation: '概括时间步块掩码、关键帧选择和令牌预算的共同资源分配机制。', linked_document_ids: ['DOC-EN-024', 'DOC-EN-028'], candidate_labels: [{ rank: 1, label: '分层计算预算', confidence: 0.95 }, { rank: 2, label: '高效视觉推理', confidence: 0.9 }], evidence: { keywords: ['块掩码', '视觉预算', '特征复用'], named_entities: ['TRIAGE', 'DPM'], center_sentence: '按时间步、帧和令牌重要性动态分配推理计算。', text_count: 2 } },
      { cluster_id: 'TECH-03', recommended_label: '前景引导预训练', confidence: 0.93, distinctiveness: 0.94, difference_explanation: '聚焦前景视图引导的自适应预训练，不与推理阶段优化混淆。', linked_document_ids: ['DOC-EN-030'], candidate_labels: [{ rank: 1, label: '前景引导预训练', confidence: 0.93 }, { rank: 2, label: '自适应视觉表征', confidence: 0.86 }], evidence: { keywords: ['前景视图', '自适应预训练'], named_entities: ['FVG-PT'], center_sentence: '前景视图用于引导预训练模型学习目标区域表征。', text_count: 1 } },
    ],
    statistics: { average_confidence: 0.94, average_distinctiveness: 0.92, duplicate_candidate_count: 0, filtered_candidate_count: 2 },
    label_generation_process_report: {
      strategy: 'multi_strategy_fusion',
      stages: [
        { order: 1, name: '读取类簇结果', status: 'completed', output: '3个类簇' },
        { order: 2, name: '汇总代表特征', status: 'completed', output: '代表短语、中心句与命名实体' },
        { order: 3, name: '生成候选标签', status: 'completed', output: '6个候选标签' },
        { order: 4, name: '差异化筛选', status: 'completed', output: '保留3个区分度达标标签' },
        { order: 5, name: '输出推荐标签', status: 'completed', output: '3个推荐标签' },
      ],
      parameters: { label_length_limit: 12, language_type: 'zh', distinctiveness_threshold: 0.75 },
    },
    label_distinctiveness_optimization_result: {
      threshold: 0.75,
      duplicate_candidate_count: 0,
      filtered_candidate_count: 2,
      clusters: [
        { cluster_id: 'TECH-01', recommended_label: '多路径推理优化', distinctiveness: 0.9, optimization_status: 'passed', optimization_explanation: '突出策略优化、慢思考和推理多样性，并过滤与计算裁剪路线语义重叠的候选标签。' },
        { cluster_id: 'TECH-02', recommended_label: '分层计算预算', distinctiveness: 0.92, optimization_status: 'passed', optimization_explanation: '合并时间步块掩码、关键帧选择和令牌预算等共同特征，保留能够体现资源分配机制的标签。' },
        { cluster_id: 'TECH-03', recommended_label: '前景引导预训练', distinctiveness: 0.94, optimization_status: 'passed', optimization_explanation: '保留前景视图引导与预训练两个核心特征，排除过于宽泛的视觉表征类候选标签。' },
      ],
    },
  },
}

const reviewResponse = {
  code: 200, message: 'success', data: {
    tool: '结构化自动综述工具', review_id: 'REVIEW-DEMO-VLM-20260817', input_type: 'texts', topic: '视觉与语言模型的推理多样性、高效推理与时间推理', document_count: 4, language: 'auto', traceability: true,
    statistics: { research_question_count: 3, method_count: 4, progress_item_count: 4, evidence_sentence_count: 8, time_range: '2026' },
    tree: [
      { question_id: 'RQ-01', research_question: '如何避免强化学习视觉语言模型的推理多样性坍缩？', document_count: 1, methods: [{ method_id: 'M-01', method: '多组策略优化', progress: [{ summary: '研究从单组相对策略优化发展到跨多组解答显式奖励差异化推理路径。', conclusion: '多组策略优化能够改善准确率与多样性的平衡。', source_ids: ['DOC-EN-018'] }] }] },
      { question_id: 'RQ-02', research_question: '如何在保持任务性能的同时降低视觉生成与视频推理成本？', document_count: 2, methods: [{ method_id: 'M-02', method: '时间步感知块掩码与特征复用', progress: [{ summary: '扩散模型可按时间步学习块级掩码并复用相邻阶段特征。', conclusion: '按时间步优化计算路径可降低扩散推理延迟。', source_ids: ['DOC-EN-024'] }] }, { method_id: 'M-03', method: '帧—令牌分层视觉预算', progress: [{ summary: '视频推理由关键帧筛选进一步发展到核心令牌和上下文令牌的协同分配。', conclusion: '分层视觉预算可同时减少时间与空间冗余。', source_ids: ['DOC-EN-028'] }] }] },
      { question_id: 'RQ-03', research_question: '慢思考大语言模型能否在无任务训练条件下进行时间序列推理？', document_count: 1, methods: [{ method_id: 'M-04', method: '混合指令与推理时多步展开', progress: [{ summary: 'TimeReasoner将时间戳、序列值和上下文特征组织为混合指令，在推理阶段诱导多步时间推理。', conclusion: '慢思考模型具备训练外时间推理潜力，但稳定性和效率仍需验证。', source_ids: ['DOC-EN-026'] }] }] },
    ],
    cluster_induction_results: { cluster_count: 3, induction_basis: '研究问题语义相似度、方法机制与来源证据一致性', clusters: [{ cluster_id: 'PC-01', label: '推理多样性优化', document_count: 1 }, { cluster_id: 'PC-02', label: '高效视觉推理', document_count: 2 }, { cluster_id: 'PC-03', label: '时间序列慢思考', document_count: 1 }] },
    structured_report: { overview: '本综述基于4篇2026年英文文献，围绕模型推理的多样性、视觉计算效率与时间推理能力，归纳出策略优化、分层计算预算和推理时慢思考三条主要路线。', sections: [{ title: '一、研究问题', content: '现有研究重点解决强化学习导致的策略收敛、视觉输入冗余造成的计算开销，以及时间序列任务中显式多步推理不足。' }, { title: '二、研究方法', content: '代表方法包括MUPO多组策略优化、时间步感知块掩码、TRIAGE帧—令牌分层预算和TimeReasoner推理时多步展开。' }, { title: '三、研究进展', content: '研究正从单一路径和均匀计算转向多路径探索、按重要性分配计算资源及训练外显式推理。' }, { title: '四、结论与不足', content: '这些方法改善了多样性或效率，但跨模型泛化、统一评测和高风险场景可靠性仍需进一步研究。' }] },
    trend_hotspot_distribution: { time_range: '2026', hotspots: [{ name: '分层视觉计算预算', score: 0.93, status: '研究热点' }, { name: '推理多样性优化', score: 0.9, status: '快速发展' }, { name: '推理时慢思考', score: 0.84, status: '新兴方向' }] },
    evidence_index: [
      { document_id: 'DOC-EN-018', title: enPapers[0].title, source_section: 'Abstract > Method and Results', evidence_excerpt: 'MUPO incentivizes divergent reasoning across multiple solutions and improves the balance between accuracy and scalability.', supported_nodes: ['RQ-01', 'M-01'] },
      { document_id: 'DOC-EN-024', title: enPapers[1].title, source_section: 'Abstract > Method', evidence_excerpt: 'Timestep-specific masks determine which diffusion blocks execute or reuse cached features.', supported_nodes: ['RQ-02', 'M-02'] },
      { document_id: 'DOC-EN-028', title: enPapers[2].title, source_section: 'Abstract > Method', evidence_excerpt: 'Frame-level and token-level budgeting allocate computation to the most relevant visual information.', supported_nodes: ['RQ-02', 'M-03'] },
      { document_id: 'DOC-EN-026', title: 'Can Slow-Thinking LLMs Reason Over Time?', source_section: 'Abstract > TimeReasoner', evidence_excerpt: 'Hybrid instructions and rollout-based reasoning induce multi-step temporal reasoning at inference time.', supported_nodes: ['RQ-03', 'M-04'] },
    ],
  },
}

const singleProfileIndex: Record<string, number> = {
  'zh-classify': 0,
  'domain-classify': 0,
  'zh-keyword': 0,
  'rq-detect': 0,
  'general-ner': 1,
  'research-ner': 1,
  'domain-ner': 2,
}

function alignSingle(toolId: string, response: AnyRecord) {
  const startIndex = payloads(response).length === 1 ? singleProfileIndex[toolId] || 0 : 0
  if (toolId === 'zh-abstract-move') return alignAbstract(response, false, startIndex)
  if (toolId === 'en-abstract-move') return alignAbstract(response, true, startIndex)
  if (toolId === 'zh-classify') return alignClassification(response, 'zh', startIndex)
  if (toolId === 'en-classify') return alignClassification(response, 'en', startIndex)
  if (toolId === 'domain-classify') return alignDomainClassification(response, startIndex)
  if (toolId === 'zh-keyword') return alignKeywords(response, false, startIndex)
  if (toolId === 'en-keyword') return alignKeywords(response, true, startIndex)
  if (toolId === 'rq-detect') return alignResearchQuestions(response, startIndex)
  if (toolId === 'citation-sentiment') return alignCitation(response, false, startIndex)
  if (toolId === 'citation-intent') return alignCitation(response, true, startIndex)
  if (toolId === 'definition-detect') return alignDefinitions(response, startIndex)
  if (toolId === 'general-ner') return alignNer(response, 'general', startIndex)
  if (toolId === 'research-ner') return alignNer(response, 'research', startIndex)
  if (toolId === 'domain-ner') return alignNer(response, 'domain', startIndex)
  if (toolId === 'deep-cluster') return clone(deepClusterResponse)
  if (toolId === 'cluster-label') return clone(clusterLabelResponse)
  if (toolId === 'structured-review') return clone(reviewResponse)
  return clone(response)
}

const batchableProfileTools = new Set([
  'zh-keyword', 'en-keyword', 'rq-detect', 'citation-sentiment', 'citation-intent', 'definition-detect',
  'general-ner', 'research-ner', 'domain-ner',
])

export function alignDemoSemanticResponse(toolId: string, response: unknown) {
  return alignSingle(toolId, response as AnyRecord)
}

const classificationToolIds = new Set(['zh-classify', 'en-classify', 'domain-classify'])

const textModeFileMetadataKeys = [
  'file_name',
  'file_type',
  'file_format',
  'file_size',
  'page_count',
  'parse_status',
  'document_parse_status',
  'section_extraction_status',
  'text_format_validation_status',
  'citation_extraction_status',
  'context_extraction_status',
  'reference_metadata_match_status',
  'file_names',
]

function stripFileMetadataForTextMode(value: unknown, mode: InputMode) {
  const result = clone(value)
  if (mode !== 'text' && mode !== 'batch-text') return result

  const visit = (node: any, parentKey = '') => {
    if (Array.isArray(node)) {
      node.forEach(item => visit(item, parentKey))
      return
    }
    if (!node || typeof node !== 'object') return

    for (const key of textModeFileMetadataKeys) delete node[key]
    if (parentKey === 'document') {
      // 演示文本可以从 PDF 中整理，但文本模式的对外响应不应暴露文件来源。
      delete node.source
      delete node.source_file
    }
    Object.entries(node).forEach(([key, child]) => visit(child, key))
  }

  visit(result)
  return result
}

function cleanClassificationResponse(toolId: string, response: AnyRecord, mode: InputMode) {
  const result = clone(response)
  if (!classificationToolIds.has(toolId)) return stripFileMetadataForTextMode(result, mode)
  payloads(result).forEach(data => {
    // 题名、摘要、关键词及文件解析状态只用于分类算法内部预处理，
    // 不属于自动分类工具的对外响应契约；文本和文件模式均不向用户返回。
    data.document_title = data.document_title || data.document?.title || '未命名文献'
    delete data.document
    delete data.input
    delete data.parsed_document
    delete data.extracted_metadata
    delete data.title
    delete data.abstract
    delete data.keywords
    delete data.page_count
    delete data.file_name
    delete data.file_type
    delete data.parse_status
    data.input_type = mode === 'batch-text' ? 'batch_text' : mode === 'batch' ? 'batch_file' : mode
  })
  return stripFileMetadataForTextMode(result, mode)
}

/**
 * 取真实接口采集的响应快照。mode 映射：text→text，batch-text→batch-text，
 * file→text（文件模式复用单篇真实响应作示例），batch→batch-text。
 * deep-cluster/cluster-label/structured-review 只有 batch-text 快照。
 * 无快照（采集失败）返回 null，调用方回退到 alignXxx 合成数据。
 */
function realResponseForMode(toolId: string, mode: InputMode): AnyRecord | null {
  const entry = (realResponses as AnyRecord)?.[toolId]
  if (!entry) return null
  const key = mode === 'text' || mode === 'file' ? 'text' : 'batch-text'
  const real = entry[key]
  if (!real) return null
  return clone(real)
}

export function alignDemoSemanticResponseForMode(toolId: string, response: unknown, mode: InputMode) {
  // 优先用真实接口采集的响应快照（schema 与真实接口一致，甲方可复现）
  const real = realResponseForMode(toolId, mode)
  if (real) return cleanClassificationResponse(toolId, real, mode)
  const aligned = alignSingle(toolId, response as AnyRecord)
  if ((mode === 'text' || mode === 'file') && payloads(aligned).length > 1) {
    const rows = payloads(aligned)
    const index = singleProfileIndex[toolId] || 0
    return cleanClassificationResponse(toolId, { code: Number((aligned as AnyRecord)?.code ?? 200), message: 'success', data: clone(rows[index % rows.length]) }, mode)
  }
  if ((mode === 'batch-text' || mode === 'batch') && classificationToolIds.has(toolId) && payloads(aligned).length === 1) {
    const items = [0, 1, 2].map(index => {
      const itemResponse = toolId === 'zh-classify'
        ? alignClassification(response as AnyRecord, 'zh', index)
        : toolId === 'en-classify'
          ? alignClassification(response as AnyRecord, 'en', index)
          : alignDomainClassification(response as AnyRecord, index)
      return clone(payloads(itemResponse)[0])
    })
    return cleanClassificationResponse(toolId, batchFromPayloads(aligned, items, mode), mode)
  }
  if ((mode === 'batch-text' || mode === 'batch') && batchableProfileTools.has(toolId) && payloads(aligned).length === 1) {
    const items = [0, 1, 2].map(index => {
      if (toolId === 'zh-keyword') return clone(payloads(alignKeywords(response as AnyRecord, false, index))[0])
      if (toolId === 'en-keyword') return clone(payloads(alignKeywords(response as AnyRecord, true, index))[0])
      if (toolId === 'rq-detect') return rqPayload(index)
      if (toolId === 'citation-sentiment') return clone(payloads(alignCitation(response as AnyRecord, false, index))[0])
      if (toolId === 'citation-intent') return clone(payloads(alignCitation(response as AnyRecord, true, index))[0])
      // 批量文本演示数据依次为地震动、糖尿病肾病和工业缺陷，
      // definition profile 0 留给单文本的“智慧治理”示例，因此批量从 profile 1 开始。
      if (toolId === 'definition-detect') return definitionPayload(index + 1)
      if (toolId === 'general-ner') return generalNerPayload(index)
      if (toolId === 'research-ner') return researchNerPayload(index)
      return domainNerPayload(index)
    })
    return cleanClassificationResponse(toolId, batchFromPayloads(aligned, items, mode), mode)
  }
  return cleanClassificationResponse(toolId, aligned, mode)
}

export const demoDeepClusterPayload = {
  cluster_dimension: 'technology', algorithm: 'auto', cluster_count: null, minimum_cluster_size: 1, similarity_metric: 'cosine',
  documents: [
    { id: 'DOC-EN-018', publication_date: '2026-04-01', title: enPapers[0].title, text: enPapers[0].abstract },
    { id: 'DOC-EN-024', publication_date: '2026-03-20', title: enPapers[1].title, text: enPapers[1].abstract },
    { id: 'DOC-EN-028', publication_date: '2026-01-30', title: enPapers[2].title, text: enPapers[2].abstract },
    { id: 'DOC-EN-026', publication_date: '2026-02-15', title: 'Can Slow-Thinking LLMs Reason Over Time?', text: 'TimeReasoner reformulates time-series forecasting as an inference-time conditional reasoning process with hybrid instructions and rollout-based multi-step reasoning.' },
    { id: 'DOC-EN-030', publication_date: '2026-02-06', title: 'FVG-PT: Adaptive Foreground View-Guided Pre-Training', text: 'Foreground views guide adaptive visual pre-training so representations focus on semantically relevant object regions.' },
  ],
  output_format: 'JSON',
}

export const demoClusterLabelPayload = {
  cluster_phrase_sets: [
    { cluster_id: 'TECH-01', phrases: ['推理多样性', '多组策略优化', '慢思考', '多步推理'] },
    { cluster_id: 'TECH-02', phrases: ['时间步块掩码', '特征复用', '关键帧选择', '令牌预算'] },
    { cluster_id: 'TECH-03', phrases: ['前景引导', '自适应预训练', '视觉表征'] },
  ], label_length_limit: 12, language_type: 'zh', distinctiveness_threshold: 0.75,
}

export const demoReviewPayload = {
  topic_or_keywords: '视觉与语言模型的推理多样性、高效推理与时间推理',
  document_set: [
    { document_id: 'DOC-EN-018', text: enPapers[0].abstract },
    { document_id: 'DOC-EN-024', text: enPapers[1].abstract },
    { document_id: 'DOC-EN-028', text: enPapers[2].abstract },
    { document_id: 'DOC-EN-026', text: 'TimeReasoner studies whether slow-thinking language models can reason over temporal dynamics through inference-time multi-step reasoning.' },
  ],
  document_metadata: [
    { document_id: 'DOC-EN-018', title: enPapers[0].title, publication_date: '2026-04-01', source: 'arXiv' },
    { document_id: 'DOC-EN-024', title: enPapers[1].title, publication_date: '2026-03-20', source: 'arXiv' },
    { document_id: 'DOC-EN-028', title: enPapers[2].title, publication_date: '2026-01-30', source: 'Conference preprint' },
    { document_id: 'DOC-EN-026', title: 'Can Slow-Thinking LLMs Reason Over Time?', publication_date: '2026-02-15', source: 'Conference preprint' },
  ],
}

export function demoApiPayloadForTool(toolId: string): AnyRecord | undefined {
  const payloadsByTool: Record<string, AnyRecord> = {
    'zh-abstract-move': { input_type: 'text', text: zhAbstractMovePapers[0].abstract, language: 'zh', return_confidence: true, aggregate_by_move: true },
    'en-abstract-move': { input_type: 'text', text: enAbstractMovePapers[0].abstract, language: 'en', return_confidence: true, aggregate_by_move: true },
    'fund-move': { input_type: 'text', project_name: 'TiAl合金中氢原子团簇的第一性原理计算及实验研究', text: 'TiAl合金是一种在汽车及航空航天等领域具有广阔应用前景的轻质高强结构材料。本项目拟采用第一性原理计算和必要的实验方法，研究α2相、γ相及α2/γ界面中的氢原子团簇行为和氢脆微观机理。', aggregate_by_move: true, return_source_section: true },
    'zh-classify': { input_type: 'text', document_title: zhPapers[1].title, chinese_scientific_document_text: zhPapers[1].abstract, clc_labeled_data: { source: 'database', resource_id: 'RES-BUNDLED-CLC-ZH' } },
    'en-classify': { input_type: 'text', document_title: enClassificationPapers[0].title, english_scientific_document_text: enClassificationPapers[0].abstract, clc_labeled_data: { source: 'database', resource_id: 'RES-BUNDLED-CLC-ZH' } },
    'domain-classify': { input_type: 'text', document_title: zhPapers[2].title, domain_scientific_literature_data: zhPapers[2].abstract, professional_domain: 'biomedical_informatics', domain_classification_rules: { source: 'database', resource_id: 'RES-BUNDLED-DOMAIN-RULE' }, manually_labeled_training_data: { source: 'database', resource_id: 'RES-BUNDLED-DOMAIN-GOLD' } },
    'zh-keyword': { input_type: 'text', document_title: zhPapers[1].title, chinese_scientific_abstract: zhPapers[1].abstract },
    'en-keyword': { input_type: 'text', document_title: enClassificationPapers[0].title, english_scientific_abstract: enClassificationPapers[0].abstract, domain_terminology_library: { source: 'database', resource_id: 'RES-BUNDLED-EN-TERM' }, classification_standard_mapping_table: { source: 'database', resource_id: 'RES-BUNDLED-EN-CLASS-MAP' } },
    'rq-detect': { input_type: 'text', document_title: zhPapers[1].title, scientific_document_fragment: zhPapers[1].abstract, text_format_requirement: '自动识别' },
    'citation-sentiment': { input_type: 'text', document_title: citationProfiles[0].paper.title, scientific_document_full_text: `${citationProfiles[0].previous} ${citationProfiles[0].sentence} ${citationProfiles[0].next}`, reference_entries: `[52] ${citationProfiles[0].authors.join(', ')}. ${citationProfiles[0].work}. 2024.` },
    'citation-intent': { input_type: 'text', document_title: citationProfiles[0].paper.title, scientific_document_full_text: `${citationProfiles[0].previous} ${citationProfiles[0].sentence} ${citationProfiles[0].next}`, reference_entries: `[52] ${citationProfiles[0].authors.join(', ')}. ${citationProfiles[0].work}. 2024.`, preprocessed_training_set: { source: 'database', resource_id: 'RES-BUNDLED-CITATION-INTENT' } },
    'definition-detect': { input_type: 'text', scientific_document_fragment_or_batch_text: '智慧治理是以数据要素汇聚、智能分析和协同决策为基础，对高校体育场馆资源、服务与运营实施精细化管理的治理方式。数据驱动决策是利用场馆运行、用户行为和资源配置数据支持管理判断与方案优化的决策过程。' },
    'general-ner': { input_type: 'text', bilingual_scientific_document_text: '刘亭亭、吕大刚和李鸿晶使用美国太平洋地震工程研究中心PEER数据库开展地震动记录研究。', general_domain_annotated_corpus: { source: 'database', resource_id: 'RES-BUNDLED-NER-GENERAL' } },
    'research-ner': { input_type: 'text', academic_abstract_or_technical_report_text: pureSingleTextByTool['research-ner'], multi_domain_scientific_corpus: { source: 'database', resource_id: 'RES-BUNDLED-NER-RESEARCH' }, manually_labeled_data: { source: 'database', resource_id: 'RES-BUNDLED-NER-RESEARCH-GOLD' } },
    'domain-ner': { input_type: 'text', domain_scientific_document_text: pureSingleTextByTool['domain-ner'], ontology_classification_system: { source: 'database', resource_id: 'RES-BUNDLED-ONTOLOGY' }, domain_labeled_training_data: { source: 'database', resource_id: 'RES-BUNDLED-DOMAIN-NER-GOLD' } },
    'deep-cluster': demoDeepClusterPayload,
    'cluster-label': demoClusterLabelPayload,
    'structured-review': demoReviewPayload,
  }
  return payloadsByTool[toolId] ? clone(payloadsByTool[toolId]) : undefined
}
