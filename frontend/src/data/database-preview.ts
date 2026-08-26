export type DatabaseResourceOption = {
  id: string
  name: string
  version: string
  recordCount: string
  language: string
  updatedAt: string
  status?: 'current' | 'history'
}

export type ClusterTaskOption = {
  id: string
  name: string
  dimension: string
  completedAt: string
  documentCount: number
  clusterCount: number
  phraseSets: Array<{ clusterId: string; phrases: string[] }>
}

export type DocumentCollectionOption = {
  id: string
  name: string
  source: string
  documentCount: number
  timeRange: string
  updatedAt: string
}

export type NerHistoryOption = {
  id: string
  taskName: string
  nerType: string
  documentId: string
  sentenceId: string
  sentence: string
  entities: Array<{ text: string; type: string; start: number; end: number }>
  completedAt: string
}

const resource = (
  id: string,
  name: string,
  version: string,
  recordCount: string,
  language: string,
  updatedAt: string,
  status: 'current' | 'history' = 'current',
): DatabaseResourceOption => ({ id, name, version, recordCount, language, updatedAt, status })

export const databaseResourceCatalog: Record<string, DatabaseResourceOption[]> = {
  clc_labeled_data: [
    resource('RES-CLC-ZH-2026', '中图分类号标准标注数据', '2026.1', '128,460 条', '中文', '2026-08-10'),
    resource('RES-CLC-ZH-2025', '中图分类号标准标注数据', '2025.4', '116,820 条', '中文', '2025-12-18', 'history'),
  ],
  domain_scientific_literature_data: [
    resource('RES-DOMAIN-LIT-IM', '智能制造领域科技文献数据', '2026.3', '84,210 篇', '中英双语', '2026-08-12'),
    resource('RES-DOMAIN-LIT-BIO', '生物医学领域科技文献数据', '2026.2', '76,530 篇', '中英双语', '2026-07-26'),
  ],
  domain_classification_rules: [
    resource('RES-DOMAIN-RULE-CURRENT', '专业领域三级分类规则', '3.2', '1,286 条', '中文', '2026-08-06'),
    resource('RES-DOMAIN-RULE-HISTORY', '专业领域三级分类规则', '3.1', '1,204 条', '中文', '2026-04-19', 'history'),
  ],
  manually_labeled_training_data: [
    resource('RES-DOMAIN-GOLD-2026', '专业领域人工标注训练数据', '2026.2', '36,800 条', '中英双语', '2026-08-09'),
    resource('RES-DOMAIN-GOLD-2025', '专业领域人工标注训练数据', '2025.4', '31,600 条', '中英双语', '2025-12-20', 'history'),
  ],
  domain_terminology_dictionary: [
    resource('RES-ZH-TERM-2026', '中文科技领域术语词典', '2026.5', '245,600 词', '中文', '2026-08-11'),
    resource('RES-ZH-TERM-USER', '用户已保存领域词典', '1.3', '2,480 词', '中文', '2026-08-15'),
  ],
  domain_terminology_library: [
    resource('RES-EN-TERM-2026', '英文科技领域术语库', '2026.4', '318,900 词', '英文', '2026-08-09'),
    resource('RES-EN-TERM-2025', '英文科技领域术语库', '2025.4', '286,300 词', '英文', '2025-12-12', 'history'),
  ],
  classification_standard_mapping_table: [
    resource('RES-EN-CLASS-MAP-2026', '英文术语分类标准映射表', '2026.2', '96,240 条', '中英双语', '2026-08-07'),
    resource('RES-EN-CLASS-MAP-2025', '英文术语分类标准映射表', '2025.3', '88,560 条', '中英双语', '2025-11-25', 'history'),
  ],
  preprocessed_training_set: [
    resource('RES-CITATION-INTENT-2026', '引用意图预处理训练集', '2026.3', '42,180 条', '中英双语', '2026-08-10'),
    resource('RES-CITATION-INTENT-2025', '引用意图预处理训练集', '2025.4', '38,760 条', '中英双语', '2025-12-16', 'history'),
  ],
  general_domain_annotated_corpus: [
    resource('RES-NER-GENERAL-2026', '通用领域实体标注语料', '2026.4', '215,000 句', '中英双语', '2026-08-08'),
    resource('RES-NER-GENERAL-2025', '通用领域实体标注语料', '2025.4', '198,000 句', '中英双语', '2025-12-11', 'history'),
  ],
  multi_domain_scientific_corpus: [
    resource('RES-NER-RESEARCH-2026', '多领域科研语料', '2026.3', '186,500 篇', '中英双语', '2026-08-12'),
    resource('RES-NER-RESEARCH-2025', '多领域科研语料', '2025.4', '164,200 篇', '中英双语', '2025-12-06', 'history'),
  ],
  manually_labeled_data: [
    resource('RES-NER-RESEARCH-GOLD', '科研实体人工标注数据', '2026.2', '58,640 句', '中英双语', '2026-08-05'),
    resource('RES-NER-RESEARCH-GOLD-H', '科研实体人工标注数据', '2025.4', '51,300 句', '中英双语', '2025-12-02', 'history'),
  ],
  ontology_classification_system: [
    resource('RES-ONTOLOGY-2026', '专业领域本体分类体系', '2026.3', '18,420 概念', '中英双语', '2026-08-09'),
  ],
  domain_labeled_training_data: [
    resource('RES-DOMAIN-NER-GOLD', '专业领域实体标注训练数据', '2026.2', '72,800 句', '中英双语', '2026-08-08'),
  ],
  document_metadata: [
    resource('RES-DOC-META-2026', '科技文献元数据总表', '2026.8', '268,400 篇', '中英双语', '2026-08-15'),
    resource('RES-DOC-META-2025', '科技文献元数据总表', '2025.12', '231,700 篇', '中英双语', '2025-12-31', 'history'),
  ],
  training_samples: [
    resource('RES-CLUSTER-TRAIN-2026', '深度聚类训练样本', '2026.3', '48,000 条', '中英双语', '2026-08-11'),
    resource('RES-CLUSTER-TRAIN-2025', '深度聚类训练样本', '2025.4', '41,500 条', '中英双语', '2025-12-21', 'history'),
  ],
  manually_labeled_category_data: [
    resource('RES-CLUSTER-GOLD-2026', '聚类人工标注类目数据', '2026.2', '12,600 条', '中英双语', '2026-08-13'),
    resource('RES-CLUSTER-GOLD-2025', '聚类人工标注类目数据', '2025.4', '9,800 条', '中英双语', '2025-12-19', 'history'),
  ],
}

export const clusterTaskOptions: ClusterTaskOption[] = [
  {
    id: 'DCL-20260815-001',
    name: '工业缺陷检测文献聚类',
    dimension: '技术路线',
    completedAt: '2026-08-15 16:42',
    documentCount: 128,
    clusterCount: 6,
    phraseSets: [
      { clusterId: 'CLUSTER-001', phrases: ['表面缺陷检测', '机器视觉', '多尺度特征融合', '卷积神经网络'] },
      { clusterId: 'CLUSTER-002', phrases: ['异常检测', '时序建模', '自监督学习', '重构误差'] },
    ],
  },
  {
    id: 'DCL-20260814-006',
    name: '新能源材料研究聚类',
    dimension: '应用场景',
    completedAt: '2026-08-14 11:08',
    documentCount: 96,
    clusterCount: 5,
    phraseSets: [
      { clusterId: 'CLUSTER-001', phrases: ['锂离子电池', '容量衰减', '健康状态评估', '剩余寿命预测'] },
      { clusterId: 'CLUSTER-002', phrases: ['光伏材料', '能量转换', '器件稳定性', '钙钛矿'] },
    ],
  },
]

export const documentCollectionOptions: DocumentCollectionOption[] = [
  { id: 'COLL-202608-VLM-01', name: '视觉与语言模型推理专题文献集', source: '科研知识库', documentCount: 4, timeRange: '2026', updatedAt: '2026-08-17' },
]

export const nerHistoryOptions: NerHistoryOption[] = [
  {
    id: 'NER-20260816-001',
    taskName: '药物作用关系实体识别',
    nerType: '专业领域命名实体识别',
    documentId: 'DOC-MED-001',
    sentenceId: 'SENT-018',
    sentence: '阿司匹林能够抑制血小板聚集。',
    entities: [
      { text: '阿司匹林', type: '药物', start: 0, end: 5 },
      { text: '血小板聚集', type: '生物过程', start: 9, end: 14 },
    ],
    completedAt: '2026-08-16 09:42',
  },
  {
    id: 'NER-20260815-026',
    taskName: '科研方法与任务实体识别',
    nerType: '科研实体识别',
    documentId: 'DOC-AI-026',
    sentenceId: 'SENT-006',
    sentence: '多尺度卷积网络用于工业表面缺陷检测。',
    entities: [
      { text: '多尺度卷积网络', type: '科研方法', start: 0, end: 8 },
      { text: '工业表面缺陷检测', type: '研究问题', start: 10, end: 18 },
    ],
    completedAt: '2026-08-15 16:18',
  },
  {
    id: 'NER-20260815-011',
    taskName: '机构合作关系实体识别',
    nerType: '通用领域命名实体识别',
    documentId: 'DOC-ORG-011',
    sentenceId: 'SENT-003',
    sentence: '燕山大学与剑桥大学开展联合研究。',
    entities: [
      { text: '燕山大学', type: '机构', start: 0, end: 4 },
      { text: '剑桥大学', type: '机构', start: 5, end: 9 },
    ],
    completedAt: '2026-08-15 11:06',
  },
]

export const citationMetadataOptions = [
  { id: 'CIT-META-202608-01', name: '社交媒体机器人检测参考文献元数据', recordCount: 86, updatedAt: '2026-08-12' },
  { id: 'CIT-META-202607-04', name: '多模态分析文献参考文献元数据', recordCount: 124, updatedAt: '2026-07-29' },
]

export const savedDictionaryOptions = [
  { id: 'DICT-USER-202608-01', name: '智能制造用户领域词典', termCount: 2480, updatedAt: '2026-08-15' },
  { id: 'DICT-USER-202607-03', name: '新能源材料用户领域词典', termCount: 1860, updatedAt: '2026-07-28' },
]

