import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const root = process.cwd()
const read = file => fs.readFileSync(path.join(root, file), 'utf8')
const contractSource = read('src/data/requirement-contracts.ts')
const overridesSource = read('src/data/tool-overrides.ts')
const testerSource = read('src/components/OnlineTester.vue')
const supplementSource = read('src/components/RequirementSupplement.vue')
const docsSource = read('src/components/DocumentationPanel.vue')
const rendererSource = read('src/utils/prototypeVisualizationRenderers.js')
const databasePreviewSource = read('src/data/database-preview.ts')

const expected = {
  'zh-abstract-move': { inputs: ['chinese_scientific_abstract'], outputs: ['move_category', 'sentence_position', 'original_fragment', 'confidence'] },
  'en-abstract-move': { inputs: ['english_scientific_abstract'], outputs: ['move_type', 'sentence_position', 'context', 'confidence'] },
  'fund-move': { inputs: ['project_document_text'], outputs: ['category_label', 'text_position', 'original_fragment', 'confidence'] },
  'zh-classify': { inputs: ['chinese_scientific_document_text', 'clc_labeled_data'], outputs: ['clc_prediction', 'classification_confidence', 'domain_labels', 'classification_statistics_table'] },
  'en-classify': { inputs: ['english_scientific_document_text', 'clc_standard_and_mapping_rules'], outputs: ['clc_prediction', 'cross_language_category_mapping', 'domain_labels', 'literature_distribution_analysis_report'] },
  'domain-classify': { inputs: ['domain_scientific_literature_data', 'domain_classification_rules', 'manually_labeled_training_data'], outputs: ['multilevel_domain_classification', 'classification_confidence', 'domain_labels', 'data_distribution_report'] },
  'zh-keyword': { inputs: ['chinese_scientific_abstract', 'domain_terminology_dictionary'], outputs: ['structured_keywords'] },
  'en-keyword': { inputs: ['english_scientific_abstract', 'domain_terminology_library', 'classification_standard_mapping_table'], outputs: ['structured_keywords_or_topic_phrases'] },
  'rq-detect': { inputs: ['scientific_document_fragment', 'text_format_requirement'], outputs: ['research_question_sentences', 'research_question_phrases', 'structured_research_questions', 'research_question_statistics'] },
  'citation-sentiment': { inputs: ['scientific_document_full_text', 'citation_sentence_and_context', 'citation_metadata'], outputs: ['citation_sentiment_results', 'context_fragments', 'confidence'] },
  'citation-intent': { inputs: ['citation_sentence_and_context', 'citation_metadata', 'preprocessed_training_set'], outputs: ['citation_intent_label', 'citation_sentence', 'context_fragment', 'confidence'] },
  'definition-detect': { inputs: ['scientific_document_fragment_or_batch_text', 'domain_label', 'output_format_requirement'], outputs: ['definition_sentences', 'concept_terms', 'concept_definition_mappings', 'statistical_analysis_report'] },
  'general-ner': { inputs: ['bilingual_scientific_document_text', 'general_domain_annotated_corpus'], outputs: ['entities'] },
  'research-ner': { inputs: ['academic_abstract_or_technical_report_text', 'multi_domain_scientific_corpus', 'manually_labeled_data'], outputs: ['entity_type', 'sentence_position', 'associated_context', 'standard_term_mapping'] },
  'domain-ner': { inputs: ['domain_scientific_document_text', 'ontology_classification_system', 'domain_labeled_training_data'], outputs: ['entity_type', 'entity_position', 'domain_label', 'standard_knowledge_base_mapping_id'] },
  'relation-extract': { inputs: ['identified_entities', 'original_sentence_text', 'dependency_parse_result'], outputs: ['relation_triples', 'context_fragments', 'confidence'] },
  'deep-cluster': { inputs: ['scientific_document_texts', 'document_metadata', 'training_samples', 'manually_labeled_category_data', 'clustering_algorithm_type', 'cluster_count', 'output_format'], outputs: ['cluster_results', 'cluster_feature_statistics', 'topic_trend_analysis'] },
  'cluster-label': { inputs: ['cluster_phrase_sets', 'label_length_limit', 'language_type', 'distinctiveness_threshold'], outputs: ['cluster_labels', 'label_generation_process_report', 'label_distinctiveness_optimization_result'] },
  'structured-review': { inputs: ['document_set', 'topic_or_keywords', 'document_metadata'], outputs: ['three_level_review_tree', 'cluster_induction_results', 'structured_text_review_report', 'trend_and_hotspot_distribution'] },
}

const failures = []
const ids = Object.keys(expected)
ids.forEach((id, index) => {
  const start = contractSource.indexOf(`'${id}':`)
  const end = index + 1 < ids.length ? contractSource.indexOf(`'${ids[index + 1]}':`, start + 1) : contractSource.length
  const block = start >= 0 ? contractSource.slice(start, end) : ''
  if (!block) failures.push(`${id}: 缺少需规契约`)
  for (const field of [...expected[id].inputs, ...expected[id].outputs]) {
    if (!block.includes(`'${field}'`)) failures.push(`${id}: 缺少字段 ${field}`)
  }
})

const sourceChecks = [
  [overridesSource.includes('params: strictContract?.inputs'), '请求参数未由需规契约覆盖'],
  [overridesSource.includes('requirementOutputs: strictContract?.outputs'), '响应输出未由需规契约覆盖'],
  [docsSource.includes('响应输出') && docsSource.includes('tool.requirementOutputs'), '文档页未展示需规响应输出表'],
  [testerSource.includes('已识别的实体列表') && testerSource.includes('原始句子文本') && testerSource.includes('依存句法分析结果'), '实体关系识别三项输入不完整'],
  [!testerSource.includes('自动文本/文件模式'), '实体关系识别仍存在需规外自动输入模式'],
  [testerSource.includes('类簇短语集合') && testerSource.includes('类簇短语预览'), '聚类标签输入未从深度聚类结果读取类簇短语集合'],
  [!testerSource.includes('三种数据源'), '聚类标签仍保留需规外三种数据源'],
  [!testerSource.includes('minimum_cluster_size') && !testerSource.includes('similarity_metric'), '深度聚类仍显示需规外聚类参数'],
  [supplementSource.includes("manually_labeled_category_data") && supplementSource.includes('文献元数据、训练样本和人工标注类目标签数据均属于需规输入'), '深度聚类三类配套输入未严格标记'],
  [rendererSource.includes('三层树形结构综述视图') && rendererSource.includes('聚类及类簇归纳结果') && rendererSource.includes('结构化文本综述报告') && rendererSource.includes('趋势分析与研究热点分布图'), '结构化自动综述四类输出弹窗不完整'],
  [overridesSource.includes('source.cluster_induction_results') && overridesSource.includes('evidence_index: evidenceIndex'), '结构化自动综述响应整理可能丢失真实类簇或溯源数据'],
  [testerSource.includes('selectedClusterTaskId') && testerSource.includes('选择已完成的深度聚类任务'), '聚类标签未使用数据库深度聚类结果选择器'],
  [!testerSource.includes('手动提交类簇短语') && !testerSource.includes('addPhraseSet') && !testerSource.includes('clusterLabelSource'), '聚类标签仍包含需规未要求的手动提交入口'],
  [testerSource.includes('选择已有文献集') && testerSource.includes('selectedCollectionId'), '结构化综述指定文献集仍是普通文本输入'],
  [testerSource.includes('从数据库选择已保存的用户词典') && testerSource.includes('selectedDictionaryId'), '用户自定义领域词典缺少数据库选择模式'],
  [supplementSource.includes('databaseResourceCatalog') && supplementSource.includes('从数据库选择当前资源') && supplementSource.includes('从数据库选择历史版本'), '需规资源字段未使用数据库资源选择组件'],
  [supplementSource.includes('clc_standard_and_mapping_rules') && supplementSource.includes('general_domain_annotated_corpus') && supplementSource.includes('multi_domain_scientific_corpus'), '数据库资源选择组件仍使用旧字段名'],
  [databasePreviewSource.includes('clusterTaskOptions') && databasePreviewSource.includes('documentCollectionOptions') && databasePreviewSource.includes('databaseResourceCatalog'), '缺少数据库资源、历史任务或文献集预览数据'],
  [testerSource.includes('class="input numeric-stepper-input"') && testerSource.includes('@click="adjustThreshold(1)"') && testerSource.includes('@click="adjustThreshold(-1)"'), '差异度阈值未使用上下步进控件'],
  [testerSource.includes('@click="adjustWeightBoost(1)"') && testerSource.includes('@click="adjustWeightBoost(-1)"'), '命中权重增量未使用上下步进控件'],
  [!testerSource.includes('thresholdOptions') && !testerSource.includes('范围 0—1，使用固定数值选择') && !testerSource.includes('范围 0—0.5'), '阈值或增量仍显示范围说明或使用下拉选项'],
  [!testerSource.includes('<small>original_sentence_text</small>') && !testerSource.includes('<small>identified_entities</small>') && !testerSource.includes('<small>dependency_parse_result</small>'), '实体关系请求标签仍显示英文参数名'],
  [!testerSource.includes('<small>cluster_dimension</small>') && !testerSource.includes('<small>clustering_algorithm_type</small>') && !testerSource.includes('<small>cluster_count') && !testerSource.includes('<small>output_format</small>'), '深度聚类请求标签仍显示英文参数名'],
  [!testerSource.includes('<small>label_length_limit</small>') && !testerSource.includes('<small>language_type</small>') && !testerSource.includes('<small>distinctiveness_threshold'), '聚类标签请求标签仍显示英文参数名'],
  [!supplementSource.includes('<small>{{ field.key }}</small>') && !supplementSource.includes('<small>document_type</small>') && !supplementSource.includes('<small>citation_metadata</small>') && !supplementSource.includes('<small>document_metadata</small>'), '补充请求参数仍显示英文参数名'],
  [!testerSource.includes('数据库将返回完整的 cluster_phrase_sets') && !testerSource.includes('发表时间和 text 均') && !testerSource.includes('读取每篇文献的 text 和对应元数据'), '在线测试功能说明仍显示后端英文字段名'],
  [testerSource.includes('v-for="(item,index) in batchTexts"') && testerSource.includes('@click="addBatchText"') && testerSource.includes('@click="removeBatchText(item.id)"'), '批量文本仍未使用可新增删除的多条输入布局'],
  [testerSource.includes('v-for="(item,index) in citationBatchItems"') && testerSource.includes('addCitationBatchItem'), '批量引用数据仍未使用逐条结构化输入布局'],
  [!testerSource.includes('v-model="form.batchText" class="textarea main-textarea"'), '批量文本仍错误复用单一大文本框'],
  [testerSource.includes("mode === 'file'") && testerSource.includes('single-file-upload-zone') && testerSource.includes("mode === 'batch'") && testerSource.includes('batch-file-queue'), '单文件与批量文件仍未使用不同布局'],
  [rendererSource.includes('label-generation-report-cover') && rendererSource.includes('任务概况') && rendererSource.includes('处理过程明细') && rendererSource.includes('报告结论'), '标签生成过程报告仍未使用正式报告结构'],
  [testerSource.includes("'zh-abstract-move': '中文科技文献摘要文本'") && testerSource.includes("'en-abstract-move': '英文科技论文摘要'") && testerSource.includes(")[props.toolId] || '文本'") && !testerSource.includes("'zh-keyword': '中文科技文献摘要'") && !testerSource.includes("'en-keyword': '英文科研文献摘要'"), '除中英文摘要语步识别外，在线测试输入标签未统一为文本'],
]
for (const [passed, message] of sourceChecks) if (!passed) failures.push(message)

if (failures.length) {
  console.error(`需规审查失败：${failures.length} 项`)
  failures.forEach(item => console.error(`- ${item}`))
  process.exit(1)
}

console.log(`需规审查通过：19/19 个功能点，${ids.reduce((sum, id) => sum + expected[id].inputs.length, 0)} 个输入字段，${ids.reduce((sum, id) => sum + expected[id].outputs.length, 0)} 个输出字段。`)
