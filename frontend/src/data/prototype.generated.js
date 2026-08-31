// 由 V7.74 HTML 原型机械提取。不要手工修改；业务修订写入 tool-overrides.ts。
export const groups = [
      { name: "语步识别工具", items: [
        ["zh-abstract-move", "中文摘要语步识别"],
        ["en-abstract-move", "英文摘要语步识别"],
        ["fund-move", "中文基金项目语步识别"]
      ]},
      { name: "自动分类工具", items: [
        ["zh-classify", "中文科技文献分类"],
        ["en-classify", "英文科技文献分类"],
        ["domain-classify", "专业领域科技文献分类"]
      ]},
      { name: "关键词识别工具", items: [
        ["zh-keyword", "中文科技文献关键词识别"],
        ["en-keyword", "英文科技文献关键词识别"]
      ]},
      { name: "研究问题识别工具", items: [["rq-detect", "研究问题句及短语识别"]]},
      { name: "引用句识别工具", items: [
        ["citation-sentiment", "引用情感识别"],
        ["citation-intent", "引用意图识别"]
      ]},
      { name: "概念定义句识别工具", items: [["definition-detect", "概念定义句识别工具"]]},
      { name: "命名实体识别工具", items: [
        ["general-ner", "中英文通用领域命名实体识别"],
        ["research-ner", "中英文通用科研实体识别"],
        ["domain-ner", "专业领域科研实体识别"],
        ["relation-extract", "实体关系识别"]
      ]},
      { name: "深度聚类工具", items: [["deep-cluster", "深度聚类工具"]]},
      { name: "聚类标签生成工具", items: [["cluster-label", "聚类标签生成工具"]]},
      { name: "结构化自动综述工具", items: [["structured-review", "结构化自动综述工具"]]}
    ]

export const tools = {
      "zh-abstract-move": {
        group: "语步识别工具",
        title: "中文摘要语步识别",
        description: "自动识别中文科技文献摘要中的研究背景、研究目的、研究方法、研究结果和研究结论，支持单文本、批量文本、单文件和批量文件四种调用方式。",
        features: "篇章结构分析、五类语步识别、批量文本处理、批量文件处理、文档解析与摘要定位、置信度输出",
        scenarios: "中文论文摘要解析、批量科研文献处理、科研情报分析、接口联调",
        endpoint: "/api/v1/move/abstract/zh/text",
        textEndpoint: "/api/v1/move/abstract/zh/text",
        batchTextEndpoint: "/api/v1/move/abstract/zh/texts",
        fileEndpoint: "/api/v1/move/abstract/zh/file",
        batchFileEndpoint: "/api/v1/move/abstract/zh/files",
        supportsFileUpload: true,
        supportsBatchUpload: true,
        acceptedFiles: [".pdf", ".docx", ".txt"],
        maxFileSizeMB: 50,
        maxBatchFiles: 20,
        maxBatchTexts: 20,
        demoFileSha256: "c2125d1a7652661ed4b43889eb4d7dc87255ae3b87b5656801f85b60e3df3e16",
        params: [
          ["input_type", "string", "required", "输入方式，取值为 text、texts、file 或 files"],
          ["text", "string", "conditional", "当 input_type=text 时必填：中文科技文献摘要原文"],
          ["texts", "object[]", "conditional", "当 input_type=texts 时必填：[{id: 'text1', text: '摘要1'}, ...]，最多 20 条"],
          ["file", "file", "conditional", "当 input_type=file 时必填：支持 PDF、DOCX、TXT"],
          ["files", "file[]", "conditional", "当 input_type=files 时必填：一次上传多个 PDF、DOCX、TXT 文件，最多 20 个"],
          ["language", "string", "optional", "语言类型，默认 zh"],
          ["return_confidence", "boolean", "optional", "是否返回语步置信度，默认 true"],
          ["aggregate_by_move", "boolean", "optional", "是否按语步类别聚合同类句子"],
          ["max_concurrency", "integer", "optional", "批量任务并发数，默认 3，仅批量模式生效"],
          ["continue_on_error", "boolean", "optional", "单个任务失败时是否继续处理其他任务，仅批量模式生效"]
        ],
        payload: {"input_type":"text","text":"智能制造场景中的金属表面缺陷具有尺度差异大、边缘模糊和背景纹理复杂等特点，现有视觉检测方法容易出现漏检和误检。为提高复杂工业表面微小缺陷的识别精度与检测效率，本文研究多尺度特征增强与关键区域自适应建模问题。提出一种融合轻量级卷积网络和动态注意力机制的缺陷检测模型，通过多尺度特征聚合、区域权重分配和边界约束学习增强缺陷表征。在三个公开工业缺陷数据集上的实验结果表明，该模型的平均检测精度较主流基线方法提高3.8个百分点，同时保持较低的推理延迟。研究结果说明，所提出的方法能够兼顾检测精度与计算效率，适用于复杂生产环境下的在线质量检测。","language":"zh","return_confidence":true,"aggregate_by_move":true},
        demoText: "智能制造场景中的金属表面缺陷具有尺度差异大、边缘模糊和背景纹理复杂等特点，现有视觉检测方法容易出现漏检和误检。为提高复杂工业表面微小缺陷的识别精度与检测效率，本文研究多尺度特征增强与关键区域自适应建模问题。提出一种融合轻量级卷积网络和动态注意力机制的缺陷检测模型，通过多尺度特征聚合、区域权重分配和边界约束学习增强缺陷表征。在三个公开工业缺陷数据集上的实验结果表明，该模型的平均检测精度较主流基线方法提高3.8个百分点，同时保持较低的推理延迟。研究结果说明，所提出的方法能够兼顾检测精度与计算效率，适用于复杂生产环境下的在线质量检测。",
        demoBatchTexts: [{"id": "text1", "text": "多中心医学影像数据能够提升疾病识别模型的泛化能力，但隐私限制和机构间数据分布差异使集中式训练难以实施。为在不共享原始影像的前提下提高跨机构分类性能，本文研究面向非独立同分布数据的联邦协同学习问题。提出一种结合动态客户端加权和特征原型对齐的联邦医学影像分类方法，通过局部模型训练、原型聚合与一致性约束减小机构间差异。在四家机构构成的多中心实验中，该方法的平均分类准确率较传统联邦平均方法提高4.2个百分点，并降低了不同机构间的性能波动。实验结果表明，该方法能够在保护数据隐私的同时增强多中心医学影像模型的稳定性与泛化能力。"}, {"id": "text2", "text": "城市道路交通状态同时受到空间拓扑、周期规律和突发事件影响，传统时间序列模型难以充分刻画路段之间的动态传播关系。为提高复杂路网中短时交通流预测的准确性，本文研究时空依赖关系的联合表示与自适应更新问题。提出一种融合动态图神经网络和门控时序编码器的预测模型，利用可学习邻接矩阵捕捉路段关联，并通过多尺度时间窗口提取周期与趋势特征。在两个公开交通数据集上的实验显示，该模型在15分钟、30分钟和60分钟预测任务中均取得更低的平均绝对误差。研究表明，动态空间关系建模与多尺度时序表示能够有效提升城市交通流预测的精度和鲁棒性。"}, {"id": "text3", "text": "锂离子电池在长期循环过程中呈现容量非线性衰减和工况差异，导致剩余寿命预测结果容易受到噪声与分布偏移影响。为提升不同运行条件下电池寿命预测的可靠性，本文研究退化特征提取与跨工况迁移建模问题。构建一种融合变分模态分解、双向时序网络和域适配约束的剩余寿命预测方法，从电压与容量曲线中提取多尺度退化特征并完成跨工况知识迁移。在多组电池循环实验数据上的验证结果表明，该方法的预测误差低于对比模型，并在早期循环阶段保持稳定的寿命估计能力。结果说明，所提出的方法能够提高电池健康管理中的预测精度，为储能系统维护决策提供有效支持。"}],
        demoBatchResults: [{"id": "text1", "text": "多中心医学影像数据能够提升疾病识别模型的泛化能力，但隐私限制和机构间数据分布差异使集中式训练难以实施。为在不共享原始影像的前提下提高跨机构分类性能，本文研究面向非独立同分布数据的联邦协同学习问题。提出一种结合动态客户端加权和特征原型对齐的联邦医学影像分类方法，通过局部模型训练、原型聚合与一致性约束减小机构间差异。在四家机构构成的多中心实验中，该方法的平均分类准确率较传统联邦平均方法提高4.2个百分点，并降低了不同机构间的性能波动。实验结果表明，该方法能够在保护数据隐私的同时增强多中心医学影像模型的稳定性与泛化能力。", "source": "generated_text", "moves": [{"label": "研究背景", "text": "多中心医学影像数据能够提升疾病识别模型的泛化能力，但隐私限制和机构间数据分布差异使集中式训练难以实施。", "sentence_indices": [1], "confidence": 0.98}, {"label": "研究目的", "text": "为在不共享原始影像的前提下提高跨机构分类性能，本文研究面向非独立同分布数据的联邦协同学习问题。", "sentence_indices": [2], "confidence": 0.97}, {"label": "研究方法", "text": "提出一种结合动态客户端加权和特征原型对齐的联邦医学影像分类方法，通过局部模型训练、原型聚合与一致性约束减小机构间差异。", "sentence_indices": [3], "confidence": 0.98}, {"label": "研究结果", "text": "在四家机构构成的多中心实验中，该方法的平均分类准确率较传统联邦平均方法提高4.2个百分点，并降低了不同机构间的性能波动。", "sentence_indices": [4], "confidence": 0.97}, {"label": "研究结论", "text": "实验结果表明，该方法能够在保护数据隐私的同时增强多中心医学影像模型的稳定性与泛化能力。", "sentence_indices": [5], "confidence": 0.96}]}, {"id": "text2", "text": "城市道路交通状态同时受到空间拓扑、周期规律和突发事件影响，传统时间序列模型难以充分刻画路段之间的动态传播关系。为提高复杂路网中短时交通流预测的准确性，本文研究时空依赖关系的联合表示与自适应更新问题。提出一种融合动态图神经网络和门控时序编码器的预测模型，利用可学习邻接矩阵捕捉路段关联，并通过多尺度时间窗口提取周期与趋势特征。在两个公开交通数据集上的实验显示，该模型在15分钟、30分钟和60分钟预测任务中均取得更低的平均绝对误差。研究表明，动态空间关系建模与多尺度时序表示能够有效提升城市交通流预测的精度和鲁棒性。", "source": "generated_text", "moves": [{"label": "研究背景", "text": "城市道路交通状态同时受到空间拓扑、周期规律和突发事件影响，传统时间序列模型难以充分刻画路段之间的动态传播关系。", "sentence_indices": [1], "confidence": 0.98}, {"label": "研究目的", "text": "为提高复杂路网中短时交通流预测的准确性，本文研究时空依赖关系的联合表示与自适应更新问题。", "sentence_indices": [2], "confidence": 0.97}, {"label": "研究方法", "text": "提出一种融合动态图神经网络和门控时序编码器的预测模型，利用可学习邻接矩阵捕捉路段关联，并通过多尺度时间窗口提取周期与趋势特征。", "sentence_indices": [3], "confidence": 0.99}, {"label": "研究结果", "text": "在两个公开交通数据集上的实验显示，该模型在15分钟、30分钟和60分钟预测任务中均取得更低的平均绝对误差。", "sentence_indices": [4], "confidence": 0.97}, {"label": "研究结论", "text": "研究表明，动态空间关系建模与多尺度时序表示能够有效提升城市交通流预测的精度和鲁棒性。", "sentence_indices": [5], "confidence": 0.96}]}, {"id": "text3", "text": "锂离子电池在长期循环过程中呈现容量非线性衰减和工况差异，导致剩余寿命预测结果容易受到噪声与分布偏移影响。为提升不同运行条件下电池寿命预测的可靠性，本文研究退化特征提取与跨工况迁移建模问题。构建一种融合变分模态分解、双向时序网络和域适配约束的剩余寿命预测方法，从电压与容量曲线中提取多尺度退化特征并完成跨工况知识迁移。在多组电池循环实验数据上的验证结果表明，该方法的预测误差低于对比模型，并在早期循环阶段保持稳定的寿命估计能力。结果说明，所提出的方法能够提高电池健康管理中的预测精度，为储能系统维护决策提供有效支持。", "source": "generated_text", "moves": [{"label": "研究背景", "text": "锂离子电池在长期循环过程中呈现容量非线性衰减和工况差异，导致剩余寿命预测结果容易受到噪声与分布偏移影响。", "sentence_indices": [1], "confidence": 0.98}, {"label": "研究目的", "text": "为提升不同运行条件下电池寿命预测的可靠性，本文研究退化特征提取与跨工况迁移建模问题。", "sentence_indices": [2], "confidence": 0.97}, {"label": "研究方法", "text": "构建一种融合变分模态分解、双向时序网络和域适配约束的剩余寿命预测方法，从电压与容量曲线中提取多尺度退化特征并完成跨工况知识迁移。", "sentence_indices": [3], "confidence": 0.98}, {"label": "研究结果", "text": "在多组电池循环实验数据上的验证结果表明，该方法的预测误差低于对比模型，并在早期循环阶段保持稳定的寿命估计能力。", "sentence_indices": [4], "confidence": 0.97}, {"label": "研究结论", "text": "结果说明，所提出的方法能够提高电池健康管理中的预测精度，为储能系统维护决策提供有效支持。", "sentence_indices": [5], "confidence": 0.96}]}],
        demoTextResult: {"code": 0, "message": "success", "data": {"tool": "中文摘要语步识别", "document": {"abstract": "智能制造场景中的金属表面缺陷具有尺度差异大、边缘模糊和背景纹理复杂等特点，现有视觉检测方法容易出现漏检和误检。为提高复杂工业表面微小缺陷的识别精度与检测效率，本文研究多尺度特征增强与关键区域自适应建模问题。提出一种融合轻量级卷积网络和动态注意力机制的缺陷检测模型，通过多尺度特征聚合、区域权重分配和边界约束学习增强缺陷表征。在三个公开工业缺陷数据集上的实验结果表明，该模型的平均检测精度较主流基线方法提高3.8个百分点，同时保持较低的推理延迟。研究结果说明，所提出的方法能够兼顾检测精度与计算效率，适用于复杂生产环境下的在线质量检测。", "abstract_complete": true, "language": "zh", "source": "generated_text"}, "moves": [{"label": "研究背景", "text": "智能制造场景中的金属表面缺陷具有尺度差异大、边缘模糊和背景纹理复杂等特点，现有视觉检测方法容易出现漏检和误检。", "sentence_indices": [1], "confidence": 0.98}, {"label": "研究目的", "text": "为提高复杂工业表面微小缺陷的识别精度与检测效率，本文研究多尺度特征增强与关键区域自适应建模问题。", "sentence_indices": [2], "confidence": 0.97}, {"label": "研究方法", "text": "提出一种融合轻量级卷积网络和动态注意力机制的缺陷检测模型，通过多尺度特征聚合、区域权重分配和边界约束学习增强缺陷表征。", "sentence_indices": [3], "confidence": 0.99}, {"label": "研究结果", "text": "在三个公开工业缺陷数据集上的实验结果表明，该模型的平均检测精度较主流基线方法提高3.8个百分点，同时保持较低的推理延迟。", "sentence_indices": [4], "confidence": 0.98}, {"label": "研究结论", "text": "研究结果说明，所提出的方法能够兼顾检测精度与计算效率，适用于复杂生产环境下的在线质量检测。", "sentence_indices": [5], "confidence": 0.97}], "move_count": 5, "sentence_count": 5}, "meta": {"request_id": "req_text_202607180001", "data_source": "synthetic", "elapsed_ms": 684}},
        demoFileResult: {"code": 0, "message": "success", "data": {"tool": "中文摘要语步识别", "document": {"title": "强化多视图多模态网络的社交媒体机器人检测", "abstract": "社交媒体机器人的快速增长虽然促进了信息传播，但也带来了隐私泄露和虚假信息传播等问题。因此，开发更加有效的机器人检测方法至关重要。提出了一种新颖的基于多头注意力机制和多视图集成分类的检测模型BotAttVCDN。该模型通过结合多模态数据，学习不同视图在标签空间中的重要性和相关性，有效捕捉多模态数据之间的关系，以提高分类性能。在Cresci-2015、TwiBot-20和TwiBot-22数据集上的实验结果表明，BotAttVCDN在分类准确率和F1-score方面均优于现有的13个基线模型，包括BotMOE和BotRGCN等，此外，通过结合注意力机制权重分配热图和SHAP分析，验证了BotAttVCDN模型不仅有效提升了社交媒体机器人检测的准确度和F1-socre，还显著增强了可解释性，使得决策过程更加透明和易于理解。这表明，该模型在应对多样化和复杂化的社交媒体机器人检测任务中具有较高的竞争力和优越性。", "abstract_complete": true, "language": "zh"}, "moves": [{"label": "研究背景", "text": "社交媒体机器人的快速增长虽然促进了信息传播，但也带来了隐私泄露和虚假信息传播等问题。", "sentence_indices": [1], "confidence": 0.99}, {"label": "研究目的", "text": "因此，开发更加有效的机器人检测方法至关重要。", "sentence_indices": [2], "confidence": 0.96}, {"label": "研究方法", "text": "提出了一种新颖的基于多头注意力机制和多视图集成分类的检测模型BotAttVCDN。该模型通过结合多模态数据，学习不同视图在标签空间中的重要性和相关性，有效捕捉多模态数据之间的关系，以提高分类性能。", "sentence_indices": [3, 4], "confidence": 0.99}, {"label": "研究结果", "text": "在Cresci-2015、TwiBot-20和TwiBot-22数据集上的实验结果表明，BotAttVCDN在分类准确率和F1-score方面均优于现有的13个基线模型，包括BotMOE和BotRGCN等，此外，通过结合注意力机制权重分配热图和SHAP分析，验证了BotAttVCDN模型不仅有效提升了社交媒体机器人检测的准确度和F1-socre，还显著增强了可解释性，使得决策过程更加透明和易于理解。", "sentence_indices": [5], "confidence": 0.99}, {"label": "研究结论", "text": "这表明，该模型在应对多样化和复杂化的社交媒体机器人检测任务中具有较高的竞争力和优越性。", "sentence_indices": [6], "confidence": 0.98}], "move_count": 5, "sentence_count": 6}, "meta": {"request_id": "req_file_202607180001", "elapsed_ms": 862}},
        response: {"code": 0, "message": "batch_completed", "data": {"batch_id": "batch_move_202607180001", "input_type": "files", "total": 2, "success_count": 2, "failed_count": 0, "results": [{"index": 1, "file_name": "paper_01.pdf", "status": "success", "document_title": "强化多视图多模态网络的社交媒体机器人检测", "moves": [{"label": "研究背景", "text": "社交媒体机器人的快速增长虽然促进了信息传播，但也带来了隐私泄露和虚假信息传播等问题。", "sentence_indices": [1], "confidence": 0.99}, {"label": "研究目的", "text": "因此，开发更加有效的机器人检测方法至关重要。", "sentence_indices": [2], "confidence": 0.96}, {"label": "研究方法", "text": "提出了一种新颖的基于多头注意力机制和多视图集成分类的检测模型BotAttVCDN。该模型通过结合多模态数据，学习不同视图在标签空间中的重要性和相关性，有效捕捉多模态数据之间的关系，以提高分类性能。", "sentence_indices": [3, 4], "confidence": 0.99}, {"label": "研究结果", "text": "在Cresci-2015、TwiBot-20和TwiBot-22数据集上的实验结果表明，BotAttVCDN在分类准确率和F1-score方面均优于现有的13个基线模型，包括BotMOE和BotRGCN等，此外，通过结合注意力机制权重分配热图和SHAP分析，验证了BotAttVCDN模型不仅有效提升了社交媒体机器人检测的准确度和F1-socre，还显著增强了可解释性，使得决策过程更加透明和易于理解。", "sentence_indices": [5], "confidence": 0.99}, {"label": "研究结论", "text": "这表明，该模型在应对多样化和复杂化的社交媒体机器人检测任务中具有较高的竞争力和优越性。", "sentence_indices": [6], "confidence": 0.98}]}, {"index": 2, "file_name": "paper_02.docx", "status": "success", "document_title": "示例科技论文", "moves": [{"label": "研究背景", "confidence": 0.95}, {"label": "研究目的", "confidence": 0.93}, {"label": "研究方法", "confidence": 0.97}, {"label": "研究结果", "confidence": 0.96}, {"label": "研究结论", "confidence": 0.94}]}]}, "meta": {"elapsed_ms": 1538, "max_concurrency": 3}}
      },
      "en-abstract-move": {
        "group": "语步识别工具",
        "title": "英文摘要语步识别",
        "description": "自动识别英文科技文献摘要中的 Background、Objective、Method、Result 和 Conclusion，支持单文本、批量文本、单文件和批量文件四种调用方式。",
        "features": "英文篇章结构分析、五类语步识别、批量文本处理、批量文件处理、文档解析与摘要定位、置信度输出",
        "scenarios": "英文论文摘要解析、批量国际文献处理、国际科技情报分析、接口联调",
        "endpoint": "/api/v1/move/abstract/en/text",
        "textEndpoint": "/api/v1/move/abstract/en/text",
        "batchTextEndpoint": "/api/v1/move/abstract/en/texts",
        "fileEndpoint": "/api/v1/move/abstract/en/file",
        "batchFileEndpoint": "/api/v1/move/abstract/en/files",
        "languageCode": "en",
        "languageName": "英文",
        "moveSummaryText": "Background、Objective、Method、Result 和 Conclusion",
        "sampleFileName": "s41467-021-23774-w.pdf",
        "sampleFileSize": "1.26 MB",
        "supportsFileUpload": true,
        "supportsBatchUpload": true,
        "acceptedFiles": [
                ".pdf",
                ".docx",
                ".txt"
        ],
        "maxFileSizeMB": 50,
        "maxBatchFiles": 20,
        "maxBatchTexts": 20,
        "demoFileSha256": "6f6f55bc4c5556fdbdad09d2d51ca05bd8da9adb8e992d5fb0b85cac0f28cda5",
        "params": [
                [
                        "input_type",
                        "string",
                        "required",
                        "输入方式，取值为 text、texts、file 或 files"
                ],
                [
                        "text",
                        "string",
                        "conditional",
                        "当 input_type=text 时必填：英文科技文献摘要原文"
                ],
                [
                        "texts",
                        "object[]",
                        "conditional",
                        "当 input_type=texts 时必填：[{id: 'text1', text: 'Abstract 1'}, ...]，最多 20 条"
                ],
                [
                        "file",
                        "file",
                        "conditional",
                        "当 input_type=file 时必填：支持 PDF、DOCX、TXT"
                ],
                [
                        "files",
                        "file[]",
                        "conditional",
                        "当 input_type=files 时必填：一次上传多个 PDF、DOCX、TXT 文件，最多 20 个"
                ],
                [
                        "language",
                        "string",
                        "optional",
                        "语言类型，默认 en"
                ],
                [
                        "return_confidence",
                        "boolean",
                        "optional",
                        "是否返回语步置信度，默认 true"
                ],
                [
                        "aggregate_by_move",
                        "boolean",
                        "optional",
                        "是否按语步类别聚合同类句子"
                ],
                [
                        "max_concurrency",
                        "integer",
                        "optional",
                        "批量任务并发数，默认 3，仅批量模式生效"
                ],
                [
                        "continue_on_error",
                        "boolean",
                        "optional",
                        "单个任务失败时是否继续处理其他任务，仅批量模式生效"
                ]
        ],
        "payload": {
                "input_type": "text",
                "text": "Reliable anomaly detection in multivariate industrial time series remains challenging because sensor noise, missing observations, and operating-condition shifts can obscure weak fault signatures. This study aims to improve detection accuracy and robustness under heterogeneous operating conditions. We propose a dual-branch temporal graph network that combines adaptive dependency learning with multi-scale temporal encoding and consistency regularization. Experiments on three public industrial datasets show that the proposed method reduces the average false-alarm rate by 18.6% and improves the F1-score by 4.1 percentage points over strong baselines. These results demonstrate that joint spatial-temporal modeling provides reliable and efficient anomaly detection for real-time industrial monitoring.",
                "language": "en",
                "return_confidence": true,
                "aggregate_by_move": true
        },
        "demoText": "Reliable anomaly detection in multivariate industrial time series remains challenging because sensor noise, missing observations, and operating-condition shifts can obscure weak fault signatures. This study aims to improve detection accuracy and robustness under heterogeneous operating conditions. We propose a dual-branch temporal graph network that combines adaptive dependency learning with multi-scale temporal encoding and consistency regularization. Experiments on three public industrial datasets show that the proposed method reduces the average false-alarm rate by 18.6% and improves the F1-score by 4.1 percentage points over strong baselines. These results demonstrate that joint spatial-temporal modeling provides reliable and efficient anomaly detection for real-time industrial monitoring.",
        "demoBatchTexts": [
                {
                        "id": "text1",
                        "text": "Medical image analysis across multiple institutions can improve model generalization, but privacy constraints and non-identically distributed data prevent centralized training. This study aims to improve cross-institutional classification without sharing raw patient images. We develop a federated learning framework that combines dynamic client weighting, prototype alignment, and consistency regularization. Experiments involving four medical centers show that the framework improves average classification accuracy by 4.2 percentage points and reduces performance variation among institutions. The results indicate that the proposed approach enhances stability and generalization while preserving data privacy."
                },
                {
                        "id": "text2",
                        "text": "Urban traffic states are jointly affected by road topology, periodic patterns, and unexpected events, making dynamic propagation difficult to capture with conventional time-series models. This work aims to improve short-term traffic-flow prediction in complex road networks. We propose a forecasting model that integrates a dynamic graph neural network with a gated temporal encoder and multi-scale time windows. Evaluations on two public traffic datasets show lower mean absolute errors for 15-minute, 30-minute, and 60-minute forecasting horizons than representative baselines. These findings confirm that adaptive spatial modeling and multi-scale temporal representation improve prediction accuracy and robustness."
                },
                {
                        "id": "text3",
                        "text": "Lithium-ion batteries exhibit nonlinear capacity degradation and substantial operating-condition differences, which make remaining-useful-life prediction sensitive to noise and distribution shifts. This study aims to improve prediction reliability across heterogeneous battery operating conditions. We construct a remaining-useful-life model that combines variational mode decomposition, a bidirectional temporal network, and domain-adaptation constraints. Experiments on multiple battery-cycling datasets show lower prediction errors than competing models and stable estimates during early cycles. The results demonstrate that the proposed model improves battery-health prognostics and supports maintenance decisions for energy-storage systems."
                }
        ],
        "demoBatchResults": [
                {
                        "id": "text1",
                        "text": "Medical image analysis across multiple institutions can improve model generalization, but privacy constraints and non-identically distributed data prevent centralized training. This study aims to improve cross-institutional classification without sharing raw patient images. We develop a federated learning framework that combines dynamic client weighting, prototype alignment, and consistency regularization. Experiments involving four medical centers show that the framework improves average classification accuracy by 4.2 percentage points and reduces performance variation among institutions. The results indicate that the proposed approach enhances stability and generalization while preserving data privacy.",
                        "source": "generated_text",
                        "moves": [
                                {
                                        "label": "Background",
                                        "text": "Medical image analysis across multiple institutions can improve model generalization, but privacy constraints and non-identically distributed data prevent centralized training.",
                                        "sentence_indices": [
                                                1
                                        ],
                                        "confidence": 0.98
                                },
                                {
                                        "label": "Objective",
                                        "text": "This study aims to improve cross-institutional classification without sharing raw patient images.",
                                        "sentence_indices": [
                                                2
                                        ],
                                        "confidence": 0.97
                                },
                                {
                                        "label": "Method",
                                        "text": "We develop a federated learning framework that combines dynamic client weighting, prototype alignment, and consistency regularization.",
                                        "sentence_indices": [
                                                3
                                        ],
                                        "confidence": 0.98
                                },
                                {
                                        "label": "Result",
                                        "text": "Experiments involving four medical centers show that the framework improves average classification accuracy by 4.2 percentage points and reduces performance variation among institutions.",
                                        "sentence_indices": [
                                                4
                                        ],
                                        "confidence": 0.97
                                },
                                {
                                        "label": "Conclusion",
                                        "text": "The results indicate that the proposed approach enhances stability and generalization while preserving data privacy.",
                                        "sentence_indices": [
                                                5
                                        ],
                                        "confidence": 0.96
                                }
                        ]
                },
                {
                        "id": "text2",
                        "text": "Urban traffic states are jointly affected by road topology, periodic patterns, and unexpected events, making dynamic propagation difficult to capture with conventional time-series models. This work aims to improve short-term traffic-flow prediction in complex road networks. We propose a forecasting model that integrates a dynamic graph neural network with a gated temporal encoder and multi-scale time windows. Evaluations on two public traffic datasets show lower mean absolute errors for 15-minute, 30-minute, and 60-minute forecasting horizons than representative baselines. These findings confirm that adaptive spatial modeling and multi-scale temporal representation improve prediction accuracy and robustness.",
                        "source": "generated_text",
                        "moves": [
                                {
                                        "label": "Background",
                                        "text": "Urban traffic states are jointly affected by road topology, periodic patterns, and unexpected events, making dynamic propagation difficult to capture with conventional time-series models.",
                                        "sentence_indices": [
                                                1
                                        ],
                                        "confidence": 0.98
                                },
                                {
                                        "label": "Objective",
                                        "text": "This work aims to improve short-term traffic-flow prediction in complex road networks.",
                                        "sentence_indices": [
                                                2
                                        ],
                                        "confidence": 0.97
                                },
                                {
                                        "label": "Method",
                                        "text": "We propose a forecasting model that integrates a dynamic graph neural network with a gated temporal encoder and multi-scale time windows.",
                                        "sentence_indices": [
                                                3
                                        ],
                                        "confidence": 0.99
                                },
                                {
                                        "label": "Result",
                                        "text": "Evaluations on two public traffic datasets show lower mean absolute errors for 15-minute, 30-minute, and 60-minute forecasting horizons than representative baselines.",
                                        "sentence_indices": [
                                                4
                                        ],
                                        "confidence": 0.97
                                },
                                {
                                        "label": "Conclusion",
                                        "text": "These findings confirm that adaptive spatial modeling and multi-scale temporal representation improve prediction accuracy and robustness.",
                                        "sentence_indices": [
                                                5
                                        ],
                                        "confidence": 0.96
                                }
                        ]
                },
                {
                        "id": "text3",
                        "text": "Lithium-ion batteries exhibit nonlinear capacity degradation and substantial operating-condition differences, which make remaining-useful-life prediction sensitive to noise and distribution shifts. This study aims to improve prediction reliability across heterogeneous battery operating conditions. We construct a remaining-useful-life model that combines variational mode decomposition, a bidirectional temporal network, and domain-adaptation constraints. Experiments on multiple battery-cycling datasets show lower prediction errors than competing models and stable estimates during early cycles. The results demonstrate that the proposed model improves battery-health prognostics and supports maintenance decisions for energy-storage systems.",
                        "source": "generated_text",
                        "moves": [
                                {
                                        "label": "Background",
                                        "text": "Lithium-ion batteries exhibit nonlinear capacity degradation and substantial operating-condition differences, which make remaining-useful-life prediction sensitive to noise and distribution shifts.",
                                        "sentence_indices": [
                                                1
                                        ],
                                        "confidence": 0.98
                                },
                                {
                                        "label": "Objective",
                                        "text": "This study aims to improve prediction reliability across heterogeneous battery operating conditions.",
                                        "sentence_indices": [
                                                2
                                        ],
                                        "confidence": 0.97
                                },
                                {
                                        "label": "Method",
                                        "text": "We construct a remaining-useful-life model that combines variational mode decomposition, a bidirectional temporal network, and domain-adaptation constraints.",
                                        "sentence_indices": [
                                                3
                                        ],
                                        "confidence": 0.98
                                },
                                {
                                        "label": "Result",
                                        "text": "Experiments on multiple battery-cycling datasets show lower prediction errors than competing models and stable estimates during early cycles.",
                                        "sentence_indices": [
                                                4
                                        ],
                                        "confidence": 0.97
                                },
                                {
                                        "label": "Conclusion",
                                        "text": "The results demonstrate that the proposed model improves battery-health prognostics and supports maintenance decisions for energy-storage systems.",
                                        "sentence_indices": [
                                                5
                                        ],
                                        "confidence": 0.96
                                }
                        ]
                }
        ],
        "demoTextResult": {
                "code": 0,
                "message": "success",
                "data": {
                        "tool": "英文摘要语步识别",
                        "document": {
                                "abstract": "Reliable anomaly detection in multivariate industrial time series remains challenging because sensor noise, missing observations, and operating-condition shifts can obscure weak fault signatures. This study aims to improve detection accuracy and robustness under heterogeneous operating conditions. We propose a dual-branch temporal graph network that combines adaptive dependency learning with multi-scale temporal encoding and consistency regularization. Experiments on three public industrial datasets show that the proposed method reduces the average false-alarm rate by 18.6% and improves the F1-score by 4.1 percentage points over strong baselines. These results demonstrate that joint spatial-temporal modeling provides reliable and efficient anomaly detection for real-time industrial monitoring.",
                                "abstract_complete": true,
                                "language": "en",
                                "source": "generated_text"
                        },
                        "moves": [
                                {
                                        "label": "Background",
                                        "text": "Reliable anomaly detection in multivariate industrial time series remains challenging because sensor noise, missing observations, and operating-condition shifts can obscure weak fault signatures.",
                                        "sentence_indices": [
                                                1
                                        ],
                                        "confidence": 0.98
                                },
                                {
                                        "label": "Objective",
                                        "text": "This study aims to improve detection accuracy and robustness under heterogeneous operating conditions.",
                                        "sentence_indices": [
                                                2
                                        ],
                                        "confidence": 0.97
                                },
                                {
                                        "label": "Method",
                                        "text": "We propose a dual-branch temporal graph network that combines adaptive dependency learning with multi-scale temporal encoding and consistency regularization.",
                                        "sentence_indices": [
                                                3
                                        ],
                                        "confidence": 0.99
                                },
                                {
                                        "label": "Result",
                                        "text": "Experiments on three public industrial datasets show that the proposed method reduces the average false-alarm rate by 18.6% and improves the F1-score by 4.1 percentage points over strong baselines.",
                                        "sentence_indices": [
                                                4
                                        ],
                                        "confidence": 0.98
                                },
                                {
                                        "label": "Conclusion",
                                        "text": "These results demonstrate that joint spatial-temporal modeling provides reliable and efficient anomaly detection for real-time industrial monitoring.",
                                        "sentence_indices": [
                                                5
                                        ],
                                        "confidence": 0.97
                                }
                        ],
                        "move_count": 5,
                        "sentence_count": 5
                },
                "meta": {
                        "request_id": "req_text_en_202607190001",
                        "data_source": "synthetic",
                        "elapsed_ms": 712
                }
        },
        "demoFileResult": {
                "code": 0,
                "message": "success",
                "data": {
                        "tool": "英文摘要语步识别",
                        "document": {
                                "title": "MOGONET integrates multi-omics data using graph convolutional networks allowing patient classification and biomarker identification",
                                "abstract": "To fully utilize the advances in omics technologies and achieve a more comprehensive understanding of human diseases, novel computational methods are required for integrative analysis of multiple types of omics data. Here, we present a novel multi-omics integrative method named Multi-Omics Graph cOnvolutional NETworks (MOGONET) for biomedical classification. MOGONET jointly explores omics-specific learning and cross-omics correlation learning for effective multi-omics data classification. We demonstrate that MOGONET outperforms other state-of-the-art supervised multi-omics integrative analysis approaches from different biomedical classification applications using mRNA expression data, DNA methylation data, and microRNA expression data. Furthermore, MOGONET can identify important biomarkers from different omics data types related to the investigated biomedical problems.",
                                "abstract_complete": true,
                                "language": "en"
                        },
                        "moves": [
                                {
                                        "label": "Background",
                                        "text": "To fully utilize the advances in omics technologies and achieve a more comprehensive understanding of human diseases, novel computational methods are required for integrative analysis of multiple types of omics data.",
                                        "sentence_indices": [
                                                1
                                        ],
                                        "confidence": 0.99
                                },
                                {
                                        "label": "Objective",
                                        "text": "Here, we present a novel multi-omics integrative method named Multi-Omics Graph cOnvolutional NETworks (MOGONET) for biomedical classification.",
                                        "sentence_indices": [
                                                2
                                        ],
                                        "confidence": 0.98
                                },
                                {
                                        "label": "Method",
                                        "text": "MOGONET jointly explores omics-specific learning and cross-omics correlation learning for effective multi-omics data classification.",
                                        "sentence_indices": [
                                                3
                                        ],
                                        "confidence": 0.99
                                },
                                {
                                        "label": "Result",
                                        "text": "We demonstrate that MOGONET outperforms other state-of-the-art supervised multi-omics integrative analysis approaches from different biomedical classification applications using mRNA expression data, DNA methylation data, and microRNA expression data.",
                                        "sentence_indices": [
                                                4
                                        ],
                                        "confidence": 0.99
                                },
                                {
                                        "label": "Conclusion",
                                        "text": "Furthermore, MOGONET can identify important biomarkers from different omics data types related to the investigated biomedical problems.",
                                        "sentence_indices": [
                                                5
                                        ],
                                        "confidence": 0.97
                                }
                        ],
                        "move_count": 5,
                        "sentence_count": 5
                },
                "meta": {
                        "request_id": "req_file_en_202607190002",
                        "elapsed_ms": 1086
                }
        },
        "response": {
                "code": 0,
                "message": "batch_completed",
                "data": {
                        "batch_id": "batch_move_en_202607190001",
                        "input_type": "files",
                        "total": 2,
                        "success_count": 2,
                        "failed_count": 0,
                        "results": [
                                {
                                        "index": 1,
                                        "file_name": "MOGONET.pdf",
                                        "status": "success",
                                        "document_title": "MOGONET integrates multi-omics data using graph convolutional networks allowing patient classification and biomarker identification",
                                        "moves": [
                                                {
                                                        "label": "Background",
                                                        "text": "To fully utilize the advances in omics technologies and achieve a more comprehensive understanding of human diseases, novel computational methods are required for integrative analysis of multiple types of omics data.",
                                                        "sentence_indices": [
                                                                1
                                                        ],
                                                        "confidence": 0.99
                                                },
                                                {
                                                        "label": "Objective",
                                                        "text": "Here, we present a novel multi-omics integrative method named Multi-Omics Graph cOnvolutional NETworks (MOGONET) for biomedical classification.",
                                                        "sentence_indices": [
                                                                2
                                                        ],
                                                        "confidence": 0.98
                                                },
                                                {
                                                        "label": "Method",
                                                        "text": "MOGONET jointly explores omics-specific learning and cross-omics correlation learning for effective multi-omics data classification.",
                                                        "sentence_indices": [
                                                                3
                                                        ],
                                                        "confidence": 0.99
                                                },
                                                {
                                                        "label": "Result",
                                                        "text": "We demonstrate that MOGONET outperforms other state-of-the-art supervised multi-omics integrative analysis approaches from different biomedical classification applications using mRNA expression data, DNA methylation data, and microRNA expression data.",
                                                        "sentence_indices": [
                                                                4
                                                        ],
                                                        "confidence": 0.99
                                                },
                                                {
                                                        "label": "Conclusion",
                                                        "text": "Furthermore, MOGONET can identify important biomarkers from different omics data types related to the investigated biomedical problems.",
                                                        "sentence_indices": [
                                                                5
                                                        ],
                                                        "confidence": 0.97
                                                }
                                        ]
                                },
                                {
                                        "index": 2,
                                        "file_name": "english_paper_02.docx",
                                        "status": "success",
                                        "document_title": "Cross-Domain Representation Learning for Scientific Document Analysis",
                                        "moves": [
                                                {
                                                        "label": "Background",
                                                        "confidence": 0.95
                                                },
                                                {
                                                        "label": "Objective",
                                                        "confidence": 0.94
                                                },
                                                {
                                                        "label": "Method",
                                                        "confidence": 0.97
                                                },
                                                {
                                                        "label": "Result",
                                                        "confidence": 0.96
                                                },
                                                {
                                                        "label": "Conclusion",
                                                        "confidence": 0.94
                                                }
                                        ]
                                }
                        ]
                },
                "meta": {
                        "elapsed_ms": 1492,
                        "max_concurrency": 3
                }
        },
        "demoFileSizeBytes": 1322087,
        "demoFileFnv1a32": "15a27ddf"
},
      "fund-move": {
        "group": "语步识别工具",
        "title": "中文基金项目语步识别",
        "description": "识别基金申请书或立项书中的立项依据、研究目标、技术实施方案、预期成果和应用价值，并保留来源章节。",
        "features": "章节结构识别、基金语步分类、来源章节溯源、同类内容聚合、单文件与批量文件处理",
        "scenarios": "基金申请书解析、科研项目要素抽取、项目评审辅助、批量项目材料处理",
        "endpoint": "/api/v1/move/fund/zh/file",
        "fileEndpoint": "/api/v1/move/fund/zh/file",
        "batchFileEndpoint": "/api/v1/move/fund/zh/files",
        "languageCode": "zh",
        "languageName": "中文",
        "documentType": "fund",
        "documentTarget": "基金项目申请书章节",
        "moveSummaryText": "立项依据、研究目标、技术实施方案、预期成果和应用价值",
        "inputModes": [
                "file",
                "batch"
        ],
        "supportsFileUpload": true,
        "supportsBatchUpload": true,
        "acceptedFiles": [
                ".pdf",
                ".docx",
                ".txt"
        ],
        "maxFileSizeMB": 50,
        "maxBatchFiles": 20,
        "sampleFileName": "多模态场景下约束生成个性化推荐方法研究.pdf",
        "sampleFileSize": "1.40 MB",
        "demoFileSizeBytes": 1471275,
        "demoFileSha256": "78d9ea1dce97701e1a555cbd57b2e9a73eeb13c806ab939462ab664afc7d348f",
        "demoFileFnv1a32": "2f5636b3",
        "params": [
                [
                        "input_type",
                        "string",
                        "required",
                        "输入方式，取值为 file 或 files"
                ],
                [
                        "file",
                        "file",
                        "conditional",
                        "当 input_type=file 时必填：上传一个基金申请书或项目文档"
                ],
                [
                        "files",
                        "file[]",
                        "conditional",
                        "当 input_type=files 时必填：批量上传基金申请书或项目文档，最多20个"
                ],
                [
                        "aggregate_by_move",
                        "boolean",
                        "optional",
                        "是否按五类基金语步聚合同类内容，默认 true"
                ],
                [
                        "return_source_section",
                        "boolean",
                        "optional",
                        "是否返回语步内容对应的来源章节，默认 true"
                ],
                [
                        "max_concurrency",
                        "integer",
                        "optional",
                        "批量文件并发数，默认 3"
                ],
                [
                        "continue_on_error",
                        "boolean",
                        "optional",
                        "单个文件失败时是否继续处理其他文件，默认 true"
                ]
        ],
        "payload": {
                "input_type": "file",
                "aggregate_by_move": true,
                "return_source_section": true,
                "max_concurrency": 3,
                "continue_on_error": true
        },
        "fileProcessingHint": "上传后自动解析基金项目文档、提取章节结构并识别五类语步",
        "batchProcessingHint": "批量接口按文件分别完成章节提取、内容分块、五类语步识别与来源章节溯源，并返回逐文件结果。",
        "demoFileResult": {
                "code": 0,
                "message": "success",
                "data": {
                        "tool": "中文基金项目语步识别",
                        "document": {
                                "title": "多模态场景下约束生成个性化推荐方法研究",
                                "file_name": "多模态场景下约束生成个性化推荐方法研究.pdf",
                                "file_type": "PDF",
                                "page_count": 30,
                                "language": "zh",
                                "document_type": "中文基金项目申请书",
                                "parse_status": "success"
                        },
                        "moves": [
                                {
                                        "label": "立项依据",
                                        "text": "随着电商平台、内容社区与短视频应用快速发展，推荐系统的数据形态已全面迈向多模态，但多模态异构性、长尾稀疏、语义层次复杂以及用户偏好多尺度变化，使现有推荐系统在表示学习、排序稳定性与结果可控性方面面临挑战。生成式推荐虽然能够以序列生成统一候选选择与排序，但仍存在大规模候选空间与数据表示不匹配、多尺度偏好建模不足、合法候选约束与训练—推理不一致等问题。因此，本项目围绕多模态语义表示、端到端生成建模和约束一致性优化开展研究，为复杂多模态环境下生成式推荐提供理论与方法支撑。",
                                        "source_sections": [
                                                "（一）立项依据",
                                                "1．研究背景与动机",
                                                "2．研究意义",
                                                "3．国内外研究现状",
                                                "3.4 当前研究存在的不足"
                                        ],
                                        "source_pages": [
                                                1,
                                                2,
                                                3,
                                                4,
                                                5,
                                                6,
                                                7,
                                                8
                                        ],
                                        "confidence": 0.99
                                },
                                {
                                        "label": "研究目标",
                                        "text": "构建一套面向生成式推荐系统设计与实现的关键技术方法体系，使系统具备多模态语义感知能力、端到端生成建模能力以及生成过程的可控性与一致性。具体包括：研究融合内容一致性与协同信号的多模态语义标识构建与统一表征方法；研究面向多尺度用户偏好的端到端生成式推荐建模方法；研究面向约束一致性的生成式排序优化与可控推荐方法。",
                                        "source_sections": [
                                                "（二）研究内容",
                                                "3．研究目标"
                                        ],
                                        "source_pages": [
                                                13,
                                                14
                                        ],
                                        "confidence": 0.99
                                },
                                {
                                        "label": "技术实施方案",
                                        "text": "首先，从文本、图像与协同行为数据中提取多模态表征，通过跨模态一致性约束、门控融合、协同信号对比学习和多码本矢量量化，构建可生成、可索引的分层语义标识（SID）及双向映射索引。其次，采用 Encoder–Decoder、自注意力、混合专家与动态路由机制，对短期、中期和长期用户偏好进行多尺度建模，并以自回归方式生成推荐语义标识序列。最后，引入基于前缀树的合法候选约束、约束感知损失、训练—推理一致性建模和奖励驱动排序优化，提升生成结果的合法性、稳定性与 Top-K 排序质量，并在 Aminer 科技论文推荐和学堂在线教育推荐场景中开展示范验证。",
                                        "source_sections": [
                                                "2．研究内容",
                                                "2.1 融合内容一致性与协同信号的多模态语义标识索引方法",
                                                "2.2 面向多尺度偏好建模的端到端生成推荐架构",
                                                "2.3 约束感知的生成式排序优化方法",
                                                "4．研究方案",
                                                "4.1 多模态语义信息融合及标识索引构建",
                                                "4.2 面向多尺度用户偏好建模的端到端生成式推荐架构"
                                        ],
                                        "source_pages": [
                                                10,
                                                11,
                                                12,
                                                13,
                                                14,
                                                15,
                                                16,
                                                17,
                                                18,
                                                19,
                                                20
                                        ],
                                        "confidence": 0.99
                                },
                                {
                                        "label": "预期成果",
                                        "text": "构建语义—协同双驱的多模态离散标识与索引理论，建立面向多尺度偏好建模的端到端生成式推荐架构，提出约束感知与训练—推理一致性的生成排序优化方法。计划在国内外高水平期刊与会议发表至少8篇高质量论文，申请4项发明专利，培养2至3名博士研究生和12至15名硕士研究生，并通过学术交流与合作研究推动成果传播。",
                                        "source_sections": [
                                                "6．年度研究计划及预期研究结果",
                                                "6.3 预期研究成果"
                                        ],
                                        "source_pages": [
                                                24,
                                                25
                                        ],
                                        "confidence": 0.99
                                },
                                {
                                        "label": "应用价值",
                                        "text": "研究成果可提升推荐系统对复杂多模态信息的理解能力，缓解数据稀疏、长尾物品和冷启动问题，增强个性化推荐的准确性、稳定性、合法性与可控性。项目拟在 Aminer 科技论文推荐与学堂在线教育推荐等真实场景中开展验证，为多模态生成式推荐在论文推荐、在线教育、电商及其他内容分发平台中的稳定部署和工程化推广提供技术支撑。",
                                        "source_sections": [
                                                "2．研究意义",
                                                "5.1 项目特色",
                                                "4．研究方案",
                                                "示范应用与技术验证"
                                        ],
                                        "source_pages": [
                                                3,
                                                5,
                                                14,
                                                15,
                                                22,
                                                23
                                        ],
                                        "confidence": 0.98
                                }
                        ],
                        "move_count": 5
                },
                "meta": {
                        "request_id": "req_fund_file_202607190002",
                        "elapsed_ms": 4386
                }
        },
        "response": {
                "code": 0,
                "message": "batch_completed",
                "data": {
                        "batch_id": "batch_fund_file_202607190002",
                        "input_type": "files",
                        "total": 2,
                        "success_count": 2,
                        "failed_count": 0,
                        "results": [
                                {
                                        "index": 1,
                                        "file_name": "多模态场景下约束生成个性化推荐方法研究.pdf",
                                        "status": "success",
                                        "code": 0,
                                        "result": {
                                                "tool": "中文基金项目语步识别",
                                                "document": {
                                                        "title": "多模态场景下约束生成个性化推荐方法研究",
                                                        "file_name": "多模态场景下约束生成个性化推荐方法研究.pdf",
                                                        "file_type": "PDF",
                                                        "page_count": 30,
                                                        "language": "zh",
                                                        "document_type": "中文基金项目申请书",
                                                        "parse_status": "success"
                                                },
                                                "moves": [
                                                        {
                                                                "label": "立项依据",
                                                                "text": "随着电商平台、内容社区与短视频应用快速发展，推荐系统的数据形态已全面迈向多模态，但多模态异构性、长尾稀疏、语义层次复杂以及用户偏好多尺度变化，使现有推荐系统在表示学习、排序稳定性与结果可控性方面面临挑战。生成式推荐虽然能够以序列生成统一候选选择与排序，但仍存在大规模候选空间与数据表示不匹配、多尺度偏好建模不足、合法候选约束与训练—推理不一致等问题。因此，本项目围绕多模态语义表示、端到端生成建模和约束一致性优化开展研究，为复杂多模态环境下生成式推荐提供理论与方法支撑。",
                                                                "source_sections": [
                                                                        "（一）立项依据",
                                                                        "1．研究背景与动机",
                                                                        "2．研究意义",
                                                                        "3．国内外研究现状",
                                                                        "3.4 当前研究存在的不足"
                                                                ],
                                                                "source_pages": [
                                                                        1,
                                                                        2,
                                                                        3,
                                                                        4,
                                                                        5,
                                                                        6,
                                                                        7,
                                                                        8
                                                                ],
                                                                "confidence": 0.99
                                                        },
                                                        {
                                                                "label": "研究目标",
                                                                "text": "构建一套面向生成式推荐系统设计与实现的关键技术方法体系，使系统具备多模态语义感知能力、端到端生成建模能力以及生成过程的可控性与一致性。具体包括：研究融合内容一致性与协同信号的多模态语义标识构建与统一表征方法；研究面向多尺度用户偏好的端到端生成式推荐建模方法；研究面向约束一致性的生成式排序优化与可控推荐方法。",
                                                                "source_sections": [
                                                                        "（二）研究内容",
                                                                        "3．研究目标"
                                                                ],
                                                                "source_pages": [
                                                                        13,
                                                                        14
                                                                ],
                                                                "confidence": 0.99
                                                        },
                                                        {
                                                                "label": "技术实施方案",
                                                                "text": "首先，从文本、图像与协同行为数据中提取多模态表征，通过跨模态一致性约束、门控融合、协同信号对比学习和多码本矢量量化，构建可生成、可索引的分层语义标识（SID）及双向映射索引。其次，采用 Encoder–Decoder、自注意力、混合专家与动态路由机制，对短期、中期和长期用户偏好进行多尺度建模，并以自回归方式生成推荐语义标识序列。最后，引入基于前缀树的合法候选约束、约束感知损失、训练—推理一致性建模和奖励驱动排序优化，提升生成结果的合法性、稳定性与 Top-K 排序质量，并在 Aminer 科技论文推荐和学堂在线教育推荐场景中开展示范验证。",
                                                                "source_sections": [
                                                                        "2．研究内容",
                                                                        "2.1 融合内容一致性与协同信号的多模态语义标识索引方法",
                                                                        "2.2 面向多尺度偏好建模的端到端生成推荐架构",
                                                                        "2.3 约束感知的生成式排序优化方法",
                                                                        "4．研究方案",
                                                                        "4.1 多模态语义信息融合及标识索引构建",
                                                                        "4.2 面向多尺度用户偏好建模的端到端生成式推荐架构"
                                                                ],
                                                                "source_pages": [
                                                                        10,
                                                                        11,
                                                                        12,
                                                                        13,
                                                                        14,
                                                                        15,
                                                                        16,
                                                                        17,
                                                                        18,
                                                                        19,
                                                                        20
                                                                ],
                                                                "confidence": 0.99
                                                        },
                                                        {
                                                                "label": "预期成果",
                                                                "text": "构建语义—协同双驱的多模态离散标识与索引理论，建立面向多尺度偏好建模的端到端生成式推荐架构，提出约束感知与训练—推理一致性的生成排序优化方法。计划在国内外高水平期刊与会议发表至少8篇高质量论文，申请4项发明专利，培养2至3名博士研究生和12至15名硕士研究生，并通过学术交流与合作研究推动成果传播。",
                                                                "source_sections": [
                                                                        "6．年度研究计划及预期研究结果",
                                                                        "6.3 预期研究成果"
                                                                ],
                                                                "source_pages": [
                                                                        24,
                                                                        25
                                                                ],
                                                                "confidence": 0.99
                                                        },
                                                        {
                                                                "label": "应用价值",
                                                                "text": "研究成果可提升推荐系统对复杂多模态信息的理解能力，缓解数据稀疏、长尾物品和冷启动问题，增强个性化推荐的准确性、稳定性、合法性与可控性。项目拟在 Aminer 科技论文推荐与学堂在线教育推荐等真实场景中开展验证，为多模态生成式推荐在论文推荐、在线教育、电商及其他内容分发平台中的稳定部署和工程化推广提供技术支撑。",
                                                                "source_sections": [
                                                                        "2．研究意义",
                                                                        "5.1 项目特色",
                                                                        "4．研究方案",
                                                                        "示范应用与技术验证"
                                                                ],
                                                                "source_pages": [
                                                                        3,
                                                                        5,
                                                                        14,
                                                                        15,
                                                                        22,
                                                                        23
                                                                ],
                                                                "confidence": 0.98
                                                        }
                                                ],
                                                "move_count": 5
                                        }
                                },
                                {
                                        "index": 2,
                                        "file_name": "fund_project_02.pdf",
                                        "status": "success",
                                        "code": 0,
                                        "result": {
                                                "tool": "中文基金项目语步识别",
                                                "document": {
                                                        "title": "面向低碳园区的多能协同优化与智能调度研究",
                                                        "file_type": "PDF",
                                                        "language": "zh",
                                                        "document_type": "中文基金项目申请书",
                                                        "parse_status": "success"
                                                },
                                                "moves": [
                                                        {
                                                                "label": "立项依据",
                                                                "source_sections": [
                                                                        "1.1 研究背景"
                                                                ],
                                                                "confidence": 0.97
                                                        },
                                                        {
                                                                "label": "研究目标",
                                                                "source_sections": [
                                                                        "3．研究目标"
                                                                ],
                                                                "confidence": 0.96
                                                        },
                                                        {
                                                                "label": "技术实施方案",
                                                                "source_sections": [
                                                                        "4．研究方案"
                                                                ],
                                                                "confidence": 0.96
                                                        },
                                                        {
                                                                "label": "预期成果",
                                                                "source_sections": [
                                                                        "6.3 预期研究成果"
                                                                ],
                                                                "confidence": 0.97
                                                        },
                                                        {
                                                                "label": "应用价值",
                                                                "source_sections": [
                                                                        "5.1 项目特色"
                                                                ],
                                                                "confidence": 0.95
                                                        }
                                                ],
                                                "move_count": 5
                                        }
                                }
                        ]
                },
                "meta": {
                        "max_concurrency": 3,
                        "elapsed_ms": 7162
                }
        }
},
      "zh-classify": {
        "group": "自动分类工具",
        "title": "中文科技文献分类",
        "description": "依据中图分类法对中文科技文献进行自动分类，支持单文本、批量文本、单文件和批量文件。单篇任务输出中图分类号预测结果、分类置信度和领域标签；批量任务除逐篇结果外，额外输出归类统计表。",
        "features": "标题—摘要—关键词联合建模、中图分类号预测、分类置信度、领域标签、批量归类统计表、批量文本分类、文档元数据自动提取、批量文件处理、原文分类号校验、单学科与跨学科自动判断",
        "scenarios": "中文论文归类、科技报告编目、跨学科文献组织、专题文献管理",
        "endpoint": "/api/v1/classify/clc/zh/text",
        "textEndpoint": "/api/v1/classify/clc/zh/text",
        "fileEndpoint": "/api/v1/classify/clc/zh/file",
        "languageCode": "zh",
        "languageName": "中文",
        "documentType": "classification",
        "documentTarget": "文献标题、摘要和关键词",
        "inputModes": [
                "text",
                "batch-text",
                "file",
                "batch"
        ],
        "modeLabels": {
                "text": "单文本",
                "batch-text": "批量文本",
                "file": "单文件",
                "batch": "批量文件"
        },
        "supportsFileUpload": true,
        "supportsBatchUpload": true,
        "acceptedFiles": [
                ".pdf",
                ".docx",
                ".txt"
        ],
        "maxFileSizeMB": 50,
        "maxBatchFiles": 20,
        "sampleFileName": "强化多视图多模态网络的社交媒体机器人检测.pdf",
        "sampleFileSize": "1.95 MB",
        "demoFileSizeBytes": 2041313,
        "demoFileSha256": "c2125d1a7652661ed4b43889eb4d7dc87255ae3b87b5656801f85b60e3df3e16",
        "demoFileFnv1a32": "13b35303",
        "fileProcessingHint": "上传后自动提取文献标题、摘要和关键词，并根据文献真实内容完成中图分类",
        "params": [
                [
                        "input_type",
                        "string",
                        "required",
                        "输入方式，取值为 text、texts、file 或 files"
                ],
                [
                        "title",
                        "string",
                        "conditional",
                        "当 input_type=text 时必填：中文科技文献标题"
                ],
                [
                        "abstract",
                        "string",
                        "conditional",
                        "当 input_type=text 时必填：中文科技文献摘要"
                ],
                [
                        "keywords",
                        "string[]",
                        "conditional",
                        "当 input_type=text 时必填：中文关键词列表"
                ],
                [
                        "texts",
                        "object[]",
                        "conditional",
                        "当 input_type=texts 时必填：每条包含 id、title、abstract 和 keywords，最多20条"
                ],
                [
                        "file",
                        "file",
                        "conditional",
                        "当 input_type=file 时必填：上传一个 PDF、DOCX 或 TXT 文件"
                ],
                [
                        "files",
                        "file[]",
                        "conditional",
                        "当 input_type=files 时必填：批量上传 PDF、DOCX 或 TXT 文件，最多20个"
                ],
                [
                        "max_concurrency",
                        "integer",
                        "optional",
                        "批量任务并发数，默认3"
                ],
                [
                        "continue_on_error",
                        "boolean",
                        "optional",
                        "单条任务失败时是否继续处理其他任务，默认true"
                ]
        ],
        "payload": {
                "input_type": "text",
                "title": "强化多视图多模态网络的社交媒体机器人检测",
                "abstract": "社交媒体机器人的快速增长虽然促进了信息传播，但也带来了隐私泄露和虚假信息传播等问题。因此，开发更加有效的机器人检测方法至关重要。提出了一种新颖的基于多头注意力机制和多视图集成分类的检测模型BotAttVCDN。该模型通过结合多模态数据，学习不同视图在标签空间中的重要性和相关性，有效捕捉多模态数据之间的关系，以提高分类性能。在Cresci-2015、TwiBot-20和TwiBot-22数据集上的实验结果表明，BotAttVCDN在分类准确率和F1-score方面均优于现有的13个基线模型，包括BotMOE和BotRGCN等。此外，通过结合注意力机制权重分配热图和SHAP分析，验证了BotAttVCDN模型不仅有效提升了社交媒体机器人检测的准确度和F1-score，还显著增强了可解释性，使得决策过程更加透明和易于理解。这表明，该模型在应对多样化和复杂化的社交媒体机器人检测任务中具有较高的竞争力和优越性。",
                "keywords": [
                        "社交媒体机器人",
                        "BotAttVCDN模型",
                        "多模态数据",
                        "多头注意力机制",
                        "多视图集成",
                        "SHAP分析",
                        "可解释性"
                ]
        },
        "demoClassificationInput": {
                "title": "强化多视图多模态网络的社交媒体机器人检测",
                "abstract": "社交媒体机器人的快速增长虽然促进了信息传播，但也带来了隐私泄露和虚假信息传播等问题。因此，开发更加有效的机器人检测方法至关重要。提出了一种新颖的基于多头注意力机制和多视图集成分类的检测模型BotAttVCDN。该模型通过结合多模态数据，学习不同视图在标签空间中的重要性和相关性，有效捕捉多模态数据之间的关系，以提高分类性能。在Cresci-2015、TwiBot-20和TwiBot-22数据集上的实验结果表明，BotAttVCDN在分类准确率和F1-score方面均优于现有的13个基线模型，包括BotMOE和BotRGCN等。此外，通过结合注意力机制权重分配热图和SHAP分析，验证了BotAttVCDN模型不仅有效提升了社交媒体机器人检测的准确度和F1-score，还显著增强了可解释性，使得决策过程更加透明和易于理解。这表明，该模型在应对多样化和复杂化的社交媒体机器人检测任务中具有较高的竞争力和优越性。",
                "keywords": [
                        "社交媒体机器人",
                        "BotAttVCDN模型",
                        "多模态数据",
                        "多头注意力机制",
                        "多视图集成",
                        "SHAP分析",
                        "可解释性"
                ]
        },
        "demoTextResult": {
                "code": 0,
                "message": "success",
                "data": {
                        "tool": "中文科技文献分类",
                        "input_type": "text",
                        "document": {
                                "title": "强化多视图多模态网络的社交媒体机器人检测",
                                "abstract": "社交媒体机器人的快速增长虽然促进了信息传播，但也带来了隐私泄露和虚假信息传播等问题。因此，开发更加有效的机器人检测方法至关重要。提出了一种新颖的基于多头注意力机制和多视图集成分类的检测模型BotAttVCDN。该模型通过结合多模态数据，学习不同视图在标签空间中的重要性和相关性，有效捕捉多模态数据之间的关系，以提高分类性能。在Cresci-2015、TwiBot-20和TwiBot-22数据集上的实验结果表明，BotAttVCDN在分类准确率和F1-score方面均优于现有的13个基线模型，包括BotMOE和BotRGCN等。此外，通过结合注意力机制权重分配热图和SHAP分析，验证了BotAttVCDN模型不仅有效提升了社交媒体机器人检测的准确度和F1-score，还显著增强了可解释性，使得决策过程更加透明和易于理解。这表明，该模型在应对多样化和复杂化的社交媒体机器人检测任务中具有较高的竞争力和优越性。",
                                "keywords": [
                                        "社交媒体机器人",
                                        "BotAttVCDN模型",
                                        "多模态数据",
                                        "多头注意力机制",
                                        "多视图集成",
                                        "SHAP分析",
                                        "可解释性"
                                ],
                                "language": "zh"
                        },
                        "is_interdisciplinary": false,
                        "classification_count": 1,
                        "classifications": [
                                {
                                        "order": 1,
                                        "role": "main",
                                        "clc_code": "TP181",
                                        "label": "自动识别与检测",
                                        "path": "工业技术 > 自动化技术、计算机技术 > 自动化基础理论 > 自动识别与检测",
                                        "confidence": 0.99,
                                        "evidence": [
                                                "论文首页明确标注中图分类号：TP181",
                                                "核心任务为社交媒体机器人自动检测",
                                                "主要方法为多模态学习、多头注意力机制和多视图集成分类"
                                        ]
                                }
                        ],
                        "classification_confidence": 0.99,
                        "domain_labels": [
                                {
                                        "label": "人工智能",
                                        "confidence": 0.98
                                },
                                {
                                        "label": "社交媒体安全",
                                        "confidence": 0.95
                                },
                                {
                                        "label": "多模态学习",
                                        "confidence": 0.94
                                }
                        ]
                },
                "meta": {
                        "request_id": "req_classify_zh_text_202607190003",
                        "elapsed_ms": 900
                }
        },
        "demoFileResult": {
                "code": 0,
                "message": "success",
                "data": {
                        "tool": "中文科技文献分类",
                        "input_type": "file",
                        "document": {
                                "title": "强化多视图多模态网络的社交媒体机器人检测",
                                "abstract": "社交媒体机器人的快速增长虽然促进了信息传播，但也带来了隐私泄露和虚假信息传播等问题。因此，开发更加有效的机器人检测方法至关重要。提出了一种新颖的基于多头注意力机制和多视图集成分类的检测模型BotAttVCDN。该模型通过结合多模态数据，学习不同视图在标签空间中的重要性和相关性，有效捕捉多模态数据之间的关系，以提高分类性能。在Cresci-2015、TwiBot-20和TwiBot-22数据集上的实验结果表明，BotAttVCDN在分类准确率和F1-score方面均优于现有的13个基线模型，包括BotMOE和BotRGCN等。此外，通过结合注意力机制权重分配热图和SHAP分析，验证了BotAttVCDN模型不仅有效提升了社交媒体机器人检测的准确度和F1-score，还显著增强了可解释性，使得决策过程更加透明和易于理解。这表明，该模型在应对多样化和复杂化的社交媒体机器人检测任务中具有较高的竞争力和优越性。",
                                "keywords": [
                                        "社交媒体机器人",
                                        "BotAttVCDN模型",
                                        "多模态数据",
                                        "多头注意力机制",
                                        "多视图集成",
                                        "SHAP分析",
                                        "可解释性"
                                ],
                                "language": "zh",
                                "file_type": "PDF",
                                "metadata_extraction_status": "success"
                        },
                        "is_interdisciplinary": false,
                        "classification_count": 1,
                        "classifications": [
                                {
                                        "order": 1,
                                        "role": "main",
                                        "clc_code": "TP181",
                                        "label": "自动识别与检测",
                                        "path": "工业技术 > 自动化技术、计算机技术 > 自动化基础理论 > 自动识别与检测",
                                        "confidence": 0.99,
                                        "evidence": [
                                                "论文首页明确标注中图分类号：TP181",
                                                "核心任务为社交媒体机器人自动检测",
                                                "主要方法为多模态学习、多头注意力机制和多视图集成分类"
                                        ]
                                }
                        ],
                        "classification_confidence": 0.99,
                        "domain_labels": [
                                {
                                        "label": "人工智能",
                                        "confidence": 0.98
                                },
                                {
                                        "label": "社交媒体安全",
                                        "confidence": 0.95
                                },
                                {
                                        "label": "多模态学习",
                                        "confidence": 0.94
                                }
                        ]
                },
                "meta": {
                        "request_id": "req_classify_zh_file_202607190003",
                        "elapsed_ms": 1450
                }
        },
        "response": {
                "code": 0,
                "message": "batch_completed",
                "data": {
                        "batch_id": "batch_classify_zh_file_202607190001",
                        "input_type": "files",
                        "total": 2,
                        "success_count": 2,
                        "failed_count": 0,
                        "results": [
                                {
                                        "index": 1,
                                        "file_name": "强化多视图多模态网络的社交媒体机器人检测.pdf",
                                        "status": "success",
                                        "code": 0,
                                        "result": {
                                                "tool": "中文科技文献分类",
                                                "input_type": "file",
                                                "document": {
                                                        "title": "强化多视图多模态网络的社交媒体机器人检测",
                                                        "abstract": "社交媒体机器人的快速增长虽然促进了信息传播，但也带来了隐私泄露和虚假信息传播等问题。因此，开发更加有效的机器人检测方法至关重要。提出了一种新颖的基于多头注意力机制和多视图集成分类的检测模型BotAttVCDN。该模型通过结合多模态数据，学习不同视图在标签空间中的重要性和相关性，有效捕捉多模态数据之间的关系，以提高分类性能。在Cresci-2015、TwiBot-20和TwiBot-22数据集上的实验结果表明，BotAttVCDN在分类准确率和F1-score方面均优于现有的13个基线模型，包括BotMOE和BotRGCN等。此外，通过结合注意力机制权重分配热图和SHAP分析，验证了BotAttVCDN模型不仅有效提升了社交媒体机器人检测的准确度和F1-score，还显著增强了可解释性，使得决策过程更加透明和易于理解。这表明，该模型在应对多样化和复杂化的社交媒体机器人检测任务中具有较高的竞争力和优越性。",
                                                        "keywords": [
                                                                "社交媒体机器人",
                                                                "BotAttVCDN模型",
                                                                "多模态数据",
                                                                "多头注意力机制",
                                                                "多视图集成",
                                                                "SHAP分析",
                                                                "可解释性"
                                                        ],
                                                        "language": "zh",
                                                        "file_type": "PDF",
                                                        "metadata_extraction_status": "success"
                                                },
                                                "is_interdisciplinary": false,
                                                "classification_count": 1,
                                                "classifications": [
                                                        {
                                                                "order": 1,
                                                                "role": "main",
                                                                "clc_code": "TP181",
                                                                "label": "自动识别与检测",
                                                                "path": "工业技术 > 自动化技术、计算机技术 > 自动化基础理论 > 自动识别与检测",
                                                                "confidence": 0.99,
                                                                "evidence": [
                                                                        "论文首页明确标注中图分类号：TP181",
                                                                        "核心任务为社交媒体机器人自动检测",
                                                                        "主要方法为多模态学习、多头注意力机制和多视图集成分类"
                                                                ]
                                                        }
                                                ],
                                                "classification_confidence": 0.99,
                                                "domain_labels": [
                                                        {
                                                                "label": "人工智能",
                                                                "confidence": 0.98
                                                        },
                                                        {
                                                                "label": "社交媒体安全",
                                                                "confidence": 0.95
                                                        },
                                                        {
                                                                "label": "多模态学习",
                                                                "confidence": 0.94
                                                        }
                                                ]
                                        }
                                },
                                {
                                        "index": 2,
                                        "file_name": "复杂工业表面微小缺陷检测方法.txt",
                                        "status": "success",
                                        "code": 0,
                                        "result": {
                                                "tool": "中文科技文献分类",
                                                "input_type": "file",
                                                "document": {
                                                        "title": "面向复杂工业表面的多尺度微小缺陷检测方法",
                                                        "abstract": "复杂工业表面中的裂纹、划痕与孔洞通常具有尺度差异大、边缘模糊和背景纹理干扰强等特点，导致传统视觉检测方法容易出现漏检和误检。本文提出一种融合多尺度特征金字塔、局部注意力增强和难样本重加权的工业表面缺陷检测方法，在不同分辨率下提取全局结构与局部细节，并通过跨层特征融合提升微小缺陷表征能力。多个公开工业缺陷数据集上的实验结果表明，该方法在检测准确率、召回率和小目标识别性能方面均优于对比模型，可为智能制造质量检测提供技术支撑。",
                                                        "keywords": [
                                                                "工业表面缺陷",
                                                                "微小目标检测",
                                                                "多尺度特征",
                                                                "注意力机制",
                                                                "机器视觉"
                                                        ],
                                                        "language": "zh",
                                                        "file_type": "TXT",
                                                        "metadata_extraction_status": "success"
                                                },
                                                "is_interdisciplinary": false,
                                                "classification_count": 1,
                                                "classifications": [
                                                        {
                                                                "order": 1,
                                                                "role": "main",
                                                                "clc_code": "TP181",
                                                                "label": "自动识别与检测",
                                                                "path": "工业技术 > 自动化技术、计算机技术 > 自动化基础理论 > 自动识别与检测",
                                                                "confidence": 0.96,
                                                                "evidence": [
                                                                        "核心任务为工业表面缺陷自动检测",
                                                                        "主要方法为机器视觉、多尺度特征建模和目标识别"
                                                                ]
                                                        }
                                                ],
                                                "classification_confidence": 0.96,
                                                "domain_labels": [
                                                        {
                                                                "label": "机器视觉",
                                                                "confidence": 0.97
                                                        },
                                                        {
                                                                "label": "工业缺陷检测",
                                                                "confidence": 0.96
                                                        },
                                                        {
                                                                "label": "智能制造",
                                                                "confidence": 0.94
                                                        }
                                                ]
                                        }
                                }
                        ],
                        "classification_statistics_table": {
                                "document_count": 2,
                                "classified_document_count": 2,
                                "clc_category_count": 1,
                                "rows": [
                                        {
                                                "clc_code": "TP181",
                                                "category_name": "自动识别与检测",
                                                "classification_path": "工业技术 > 自动化技术、计算机技术 > 自动化基础理论 > 自动识别与检测",
                                                "document_count": 2,
                                                "document_percentage": 100.0,
                                                "average_confidence": 0.975
                                        }
                                ]
                        }
                },
                "meta": {
                        "max_concurrency": 3,
                        "elapsed_ms": 2964
                }
        },
        "batchTextEndpoint": "/api/v1/classify/clc/zh/texts",
        "batchFileEndpoint": "/api/v1/classify/clc/zh/files",
        "maxBatchTexts": 20,
        "demoFileFixtures": [
                {
                        "file_name": "强化多视图多模态网络的社交媒体机器人检测.pdf",
                        "size_bytes": 2041313,
                        "sha256": "c2125d1a7652661ed4b43889eb4d7dc87255ae3b87b5656801f85b60e3df3e16",
                        "fnv1a32": "13b35303",
                        "result": {
                                "code": 0,
                                "message": "success",
                                "data": {
                                        "tool": "中文科技文献分类",
                                        "input_type": "file",
                                        "document": {
                                                "title": "强化多视图多模态网络的社交媒体机器人检测",
                                                "abstract": "社交媒体机器人的快速增长虽然促进了信息传播，但也带来了隐私泄露和虚假信息传播等问题。因此，开发更加有效的机器人检测方法至关重要。提出了一种新颖的基于多头注意力机制和多视图集成分类的检测模型BotAttVCDN。该模型通过结合多模态数据，学习不同视图在标签空间中的重要性和相关性，有效捕捉多模态数据之间的关系，以提高分类性能。在Cresci-2015、TwiBot-20和TwiBot-22数据集上的实验结果表明，BotAttVCDN在分类准确率和F1-score方面均优于现有的13个基线模型，包括BotMOE和BotRGCN等。此外，通过结合注意力机制权重分配热图和SHAP分析，验证了BotAttVCDN模型不仅有效提升了社交媒体机器人检测的准确度和F1-score，还显著增强了可解释性，使得决策过程更加透明和易于理解。这表明，该模型在应对多样化和复杂化的社交媒体机器人检测任务中具有较高的竞争力和优越性。",
                                                "keywords": [
                                                        "社交媒体机器人",
                                                        "BotAttVCDN模型",
                                                        "多模态数据",
                                                        "多头注意力机制",
                                                        "多视图集成",
                                                        "SHAP分析",
                                                        "可解释性"
                                                ],
                                                "language": "zh",
                                                "file_type": "PDF",
                                                "metadata_extraction_status": "success"
                                        },
                                        "is_interdisciplinary": false,
                                        "classification_count": 1,
                                        "classifications": [
                                                {
                                                        "order": 1,
                                                        "role": "main",
                                                        "clc_code": "TP181",
                                                        "label": "自动识别与检测",
                                                        "path": "工业技术 > 自动化技术、计算机技术 > 自动化基础理论 > 自动识别与检测",
                                                        "confidence": 0.99,
                                                        "evidence": [
                                                                "论文首页明确标注中图分类号：TP181",
                                                                "核心任务为社交媒体机器人自动检测",
                                                                "主要方法为多模态学习、多头注意力机制和多视图集成分类"
                                                        ]
                                                }
                                        ],
                                        "classification_confidence": 0.99,
                                        "domain_labels": [
                                                {
                                                        "label": "人工智能",
                                                        "confidence": 0.98
                                                },
                                                {
                                                        "label": "社交媒体安全",
                                                        "confidence": 0.95
                                                },
                                                {
                                                        "label": "多模态学习",
                                                        "confidence": 0.94
                                                }
                                        ]
                                },
                                "meta": {
                                        "request_id": "req_classify_zh_file_202607190003",
                                        "elapsed_ms": 1450
                                }
                        }
                },
                {
                        "file_name": "复杂工业表面微小缺陷检测方法.txt",
                        "size_bytes": 842,
                        "sha256": "8ff6b6a7d2f45c3c57b8058849e95175f0ebf32876173d0637a1e8f4b3704f61",
                        "fnv1a32": "a8f1e419",
                        "result": {
                                "code": 0,
                                "message": "success",
                                "data": {
                                        "tool": "中文科技文献分类",
                                        "input_type": "file",
                                        "document": {
                                                "title": "面向复杂工业表面的多尺度微小缺陷检测方法",
                                                "abstract": "复杂工业表面中的裂纹、划痕与孔洞通常具有尺度差异大、边缘模糊和背景纹理干扰强等特点，导致传统视觉检测方法容易出现漏检和误检。本文提出一种融合多尺度特征金字塔、局部注意力增强和难样本重加权的工业表面缺陷检测方法，在不同分辨率下提取全局结构与局部细节，并通过跨层特征融合提升微小缺陷表征能力。多个公开工业缺陷数据集上的实验结果表明，该方法在检测准确率、召回率和小目标识别性能方面均优于对比模型，可为智能制造质量检测提供技术支撑。",
                                                "keywords": [
                                                        "工业表面缺陷",
                                                        "微小目标检测",
                                                        "多尺度特征",
                                                        "注意力机制",
                                                        "机器视觉"
                                                ],
                                                "language": "zh",
                                                "file_type": "TXT",
                                                "metadata_extraction_status": "success"
                                        },
                                        "is_interdisciplinary": false,
                                        "classification_count": 1,
                                        "classifications": [
                                                {
                                                        "order": 1,
                                                        "role": "main",
                                                        "clc_code": "TP181",
                                                        "label": "自动识别与检测",
                                                        "path": "工业技术 > 自动化技术、计算机技术 > 自动化基础理论 > 自动识别与检测",
                                                        "confidence": 0.96,
                                                        "evidence": [
                                                                "核心任务为工业表面缺陷自动检测",
                                                                "主要方法为机器视觉、多尺度特征建模和目标识别"
                                                        ]
                                                }
                                        ],
                                        "classification_confidence": 0.96,
                                        "domain_labels": [
                                                {
                                                        "label": "机器视觉",
                                                        "confidence": 0.97
                                                },
                                                {
                                                        "label": "工业缺陷检测",
                                                        "confidence": 0.96
                                                },
                                                {
                                                        "label": "智能制造",
                                                        "confidence": 0.94
                                                }
                                        ]
                                },
                                "meta": {
                                        "request_id": "req_classify_zh_file_202607190004",
                                        "elapsed_ms": 1450
                                }
                        }
                }
        ],
        "demoBatchClassificationInputs": [
                {
                        "id": "text1",
                        "title": "强化多视图多模态网络的社交媒体机器人检测",
                        "abstract": "社交媒体机器人的快速增长虽然促进了信息传播，但也带来了隐私泄露和虚假信息传播等问题。因此，开发更加有效的机器人检测方法至关重要。提出了一种新颖的基于多头注意力机制和多视图集成分类的检测模型BotAttVCDN。该模型通过结合多模态数据，学习不同视图在标签空间中的重要性和相关性，有效捕捉多模态数据之间的关系，以提高分类性能。在Cresci-2015、TwiBot-20和TwiBot-22数据集上的实验结果表明，BotAttVCDN在分类准确率和F1-score方面均优于现有的13个基线模型，包括BotMOE和BotRGCN等。此外，通过结合注意力机制权重分配热图和SHAP分析，验证了BotAttVCDN模型不仅有效提升了社交媒体机器人检测的准确度和F1-score，还显著增强了可解释性，使得决策过程更加透明和易于理解。这表明，该模型在应对多样化和复杂化的社交媒体机器人检测任务中具有较高的竞争力和优越性。",
                        "keywords": [
                                "社交媒体机器人",
                                "BotAttVCDN模型",
                                "多模态数据",
                                "多头注意力机制",
                                "多视图集成",
                                "SHAP分析",
                                "可解释性"
                        ]
                },
                {
                        "id": "text2",
                        "title": "面向复杂工业表面的多尺度微小缺陷检测方法",
                        "abstract": "复杂工业表面中的裂纹、划痕与孔洞通常具有尺度差异大、边缘模糊和背景纹理干扰强等特点，导致传统视觉检测方法容易出现漏检和误检。本文提出一种融合多尺度特征金字塔、局部注意力增强和难样本重加权的工业表面缺陷检测方法，在不同分辨率下提取全局结构与局部细节，并通过跨层特征融合提升微小缺陷表征能力。多个公开工业缺陷数据集上的实验结果表明，该方法在检测准确率、召回率和小目标识别性能方面均优于对比模型，可为智能制造质量检测提供技术支撑。",
                        "keywords": [
                                "工业表面缺陷",
                                "微小目标检测",
                                "多尺度特征",
                                "注意力机制",
                                "机器视觉"
                        ]
                },
                {
                        "id": "text3",
                        "title": "基于多源遥感影像的城市地表覆盖精细分类方法",
                        "abstract": "城市地表覆盖类型具有光谱混叠、空间结构复杂和跨区域分布差异显著等特点，单一遥感数据难以实现稳定的精细分类。本文联合利用高分辨率光学影像、合成孔径雷达数据和地形辅助信息，构建多源特征协同编码网络，通过跨模态对齐和区域上下文建模增强建筑、道路、植被和水体等类别的区分能力。多城市区域实验表明，该方法能够提高总体分类精度和边界区域识别质量，为城市空间监测与土地利用调查提供可靠支持。",
                        "keywords": [
                                "遥感影像",
                                "地表覆盖分类",
                                "多源数据融合",
                                "跨模态对齐",
                                "城市空间监测"
                        ]
                }
        ],
        "demoBatchClassificationResults": [
                {
                        "id": "text1",
                        "title": "强化多视图多模态网络的社交媒体机器人检测",
                        "abstract": "社交媒体机器人的快速增长虽然促进了信息传播，但也带来了隐私泄露和虚假信息传播等问题。因此，开发更加有效的机器人检测方法至关重要。提出了一种新颖的基于多头注意力机制和多视图集成分类的检测模型BotAttVCDN。该模型通过结合多模态数据，学习不同视图在标签空间中的重要性和相关性，有效捕捉多模态数据之间的关系，以提高分类性能。在Cresci-2015、TwiBot-20和TwiBot-22数据集上的实验结果表明，BotAttVCDN在分类准确率和F1-score方面均优于现有的13个基线模型，包括BotMOE和BotRGCN等。此外，通过结合注意力机制权重分配热图和SHAP分析，验证了BotAttVCDN模型不仅有效提升了社交媒体机器人检测的准确度和F1-score，还显著增强了可解释性，使得决策过程更加透明和易于理解。这表明，该模型在应对多样化和复杂化的社交媒体机器人检测任务中具有较高的竞争力和优越性。",
                        "keywords": [
                                "社交媒体机器人",
                                "BotAttVCDN模型",
                                "多模态数据",
                                "多头注意力机制",
                                "多视图集成",
                                "SHAP分析",
                                "可解释性"
                        ],
                        "classifications": [
                                {
                                        "order": 1,
                                        "role": "main",
                                        "clc_code": "TP181",
                                        "label": "自动识别与检测",
                                        "path": "工业技术 > 自动化技术、计算机技术 > 自动化基础理论 > 自动识别与检测",
                                        "confidence": 0.99,
                                        "evidence": [
                                                "论文首页明确标注中图分类号：TP181",
                                                "核心任务为社交媒体机器人自动检测",
                                                "主要方法为多模态学习、多头注意力机制和多视图集成分类"
                                        ]
                                }
                        ],
                        "classification_confidence": 0.99,
                        "domain_labels": [
                                {
                                        "label": "人工智能",
                                        "confidence": 0.98
                                },
                                {
                                        "label": "社交媒体安全",
                                        "confidence": 0.95
                                },
                                {
                                        "label": "多模态学习",
                                        "confidence": 0.94
                                }
                        ]
                },
                {
                        "id": "text2",
                        "title": "面向复杂工业表面的多尺度微小缺陷检测方法",
                        "abstract": "复杂工业表面中的裂纹、划痕与孔洞通常具有尺度差异大、边缘模糊和背景纹理干扰强等特点，导致传统视觉检测方法容易出现漏检和误检。本文提出一种融合多尺度特征金字塔、局部注意力增强和难样本重加权的工业表面缺陷检测方法，在不同分辨率下提取全局结构与局部细节，并通过跨层特征融合提升微小缺陷表征能力。多个公开工业缺陷数据集上的实验结果表明，该方法在检测准确率、召回率和小目标识别性能方面均优于对比模型，可为智能制造质量检测提供技术支撑。",
                        "keywords": [
                                "工业表面缺陷",
                                "微小目标检测",
                                "多尺度特征",
                                "注意力机制",
                                "机器视觉"
                        ],
                        "classifications": [
                                {
                                        "order": 1,
                                        "role": "main",
                                        "clc_code": "TP181",
                                        "label": "自动识别与检测",
                                        "path": "工业技术 > 自动化技术、计算机技术 > 自动化基础理论 > 自动识别与检测",
                                        "confidence": 0.96,
                                        "evidence": [
                                                "核心任务为工业表面缺陷自动检测",
                                                "主要方法为机器视觉、多尺度特征建模和目标识别"
                                        ]
                                }
                        ],
                        "classification_confidence": 0.96,
                        "domain_labels": [
                                {
                                        "label": "机器视觉",
                                        "confidence": 0.97
                                },
                                {
                                        "label": "工业缺陷检测",
                                        "confidence": 0.96
                                },
                                {
                                        "label": "智能制造",
                                        "confidence": 0.94
                                }
                        ]
                },
                {
                        "id": "text3",
                        "title": "基于多源遥感影像的城市地表覆盖精细分类方法",
                        "abstract": "城市地表覆盖类型具有光谱混叠、空间结构复杂和跨区域分布差异显著等特点，单一遥感数据难以实现稳定的精细分类。本文联合利用高分辨率光学影像、合成孔径雷达数据和地形辅助信息，构建多源特征协同编码网络，通过跨模态对齐和区域上下文建模增强建筑、道路、植被和水体等类别的区分能力。多城市区域实验表明，该方法能够提高总体分类精度和边界区域识别质量，为城市空间监测与土地利用调查提供可靠支持。",
                        "keywords": [
                                "遥感影像",
                                "地表覆盖分类",
                                "多源数据融合",
                                "跨模态对齐",
                                "城市空间监测"
                        ],
                        "classifications": [
                                {
                                        "order": 1,
                                        "role": "main",
                                        "clc_code": "TP79",
                                        "label": "遥感技术",
                                        "path": "工业技术 > 自动化技术、计算机技术 > 遥感技术",
                                        "confidence": 0.95,
                                        "evidence": [
                                                "核心研究对象为多源遥感影像",
                                                "主要任务为城市地表覆盖精细分类"
                                        ]
                                }
                        ],
                        "classification_confidence": 0.95,
                        "domain_labels": [
                                {
                                        "label": "遥感技术",
                                        "confidence": 0.98
                                },
                                {
                                        "label": "地表覆盖分类",
                                        "confidence": 0.96
                                },
                                {
                                        "label": "城市空间监测",
                                        "confidence": 0.95
                                }
                        ]
                }
        ],
        "demoBatchTextResult": {
                "code": 0,
                "message": "batch_completed",
                "data": {
                        "batch_id": "batch_classify_zh_text_202607190001",
                        "input_type": "texts",
                        "total": 3,
                        "success_count": 3,
                        "failed_count": 0,
                        "results": [
                                {
                                        "index": 1,
                                        "input_id": "text1",
                                        "status": "success",
                                        "code": 0,
                                        "result": {
                                                "tool": "中文科技文献分类",
                                                "input_type": "text",
                                                "document": {
                                                        "title": "强化多视图多模态网络的社交媒体机器人检测",
                                                        "abstract": "社交媒体机器人的快速增长虽然促进了信息传播，但也带来了隐私泄露和虚假信息传播等问题。因此，开发更加有效的机器人检测方法至关重要。提出了一种新颖的基于多头注意力机制和多视图集成分类的检测模型BotAttVCDN。该模型通过结合多模态数据，学习不同视图在标签空间中的重要性和相关性，有效捕捉多模态数据之间的关系，以提高分类性能。在Cresci-2015、TwiBot-20和TwiBot-22数据集上的实验结果表明，BotAttVCDN在分类准确率和F1-score方面均优于现有的13个基线模型，包括BotMOE和BotRGCN等。此外，通过结合注意力机制权重分配热图和SHAP分析，验证了BotAttVCDN模型不仅有效提升了社交媒体机器人检测的准确度和F1-score，还显著增强了可解释性，使得决策过程更加透明和易于理解。这表明，该模型在应对多样化和复杂化的社交媒体机器人检测任务中具有较高的竞争力和优越性。",
                                                        "keywords": [
                                                                "社交媒体机器人",
                                                                "BotAttVCDN模型",
                                                                "多模态数据",
                                                                "多头注意力机制",
                                                                "多视图集成",
                                                                "SHAP分析",
                                                                "可解释性"
                                                        ],
                                                        "language": "zh"
                                                },
                                                "is_interdisciplinary": false,
                                                "classification_count": 1,
                                                "classifications": [
                                                        {
                                                                "order": 1,
                                                                "role": "main",
                                                                "clc_code": "TP181",
                                                                "label": "自动识别与检测",
                                                                "path": "工业技术 > 自动化技术、计算机技术 > 自动化基础理论 > 自动识别与检测",
                                                                "confidence": 0.99,
                                                                "evidence": [
                                                                        "论文首页明确标注中图分类号：TP181",
                                                                        "核心任务为社交媒体机器人自动检测",
                                                                        "主要方法为多模态学习、多头注意力机制和多视图集成分类"
                                                                ]
                                                        }
                                                ],
                                                "classification_confidence": 0.99,
                                                "domain_labels": [
                                                        {
                                                                "label": "人工智能",
                                                                "confidence": 0.98
                                                        },
                                                        {
                                                                "label": "社交媒体安全",
                                                                "confidence": 0.95
                                                        },
                                                        {
                                                                "label": "多模态学习",
                                                                "confidence": 0.94
                                                        }
                                                ]
                                        }
                                },
                                {
                                        "index": 2,
                                        "input_id": "text2",
                                        "status": "success",
                                        "code": 0,
                                        "result": {
                                                "tool": "中文科技文献分类",
                                                "input_type": "text",
                                                "document": {
                                                        "title": "面向复杂工业表面的多尺度微小缺陷检测方法",
                                                        "abstract": "复杂工业表面中的裂纹、划痕与孔洞通常具有尺度差异大、边缘模糊和背景纹理干扰强等特点，导致传统视觉检测方法容易出现漏检和误检。本文提出一种融合多尺度特征金字塔、局部注意力增强和难样本重加权的工业表面缺陷检测方法，在不同分辨率下提取全局结构与局部细节，并通过跨层特征融合提升微小缺陷表征能力。多个公开工业缺陷数据集上的实验结果表明，该方法在检测准确率、召回率和小目标识别性能方面均优于对比模型，可为智能制造质量检测提供技术支撑。",
                                                        "keywords": [
                                                                "工业表面缺陷",
                                                                "微小目标检测",
                                                                "多尺度特征",
                                                                "注意力机制",
                                                                "机器视觉"
                                                        ],
                                                        "language": "zh"
                                                },
                                                "is_interdisciplinary": false,
                                                "classification_count": 1,
                                                "classifications": [
                                                        {
                                                                "order": 1,
                                                                "role": "main",
                                                                "clc_code": "TP181",
                                                                "label": "自动识别与检测",
                                                                "path": "工业技术 > 自动化技术、计算机技术 > 自动化基础理论 > 自动识别与检测",
                                                                "confidence": 0.96,
                                                                "evidence": [
                                                                        "核心任务为工业表面缺陷自动检测",
                                                                        "主要方法为机器视觉、多尺度特征建模和目标识别"
                                                                ]
                                                        }
                                                ],
                                                "classification_confidence": 0.96,
                                                "domain_labels": [
                                                        {
                                                                "label": "机器视觉",
                                                                "confidence": 0.97
                                                        },
                                                        {
                                                                "label": "工业缺陷检测",
                                                                "confidence": 0.96
                                                        },
                                                        {
                                                                "label": "智能制造",
                                                                "confidence": 0.94
                                                        }
                                                ]
                                        }
                                },
                                {
                                        "index": 3,
                                        "input_id": "text3",
                                        "status": "success",
                                        "code": 0,
                                        "result": {
                                                "tool": "中文科技文献分类",
                                                "input_type": "text",
                                                "document": {
                                                        "title": "基于多源遥感影像的城市地表覆盖精细分类方法",
                                                        "abstract": "城市地表覆盖类型具有光谱混叠、空间结构复杂和跨区域分布差异显著等特点，单一遥感数据难以实现稳定的精细分类。本文联合利用高分辨率光学影像、合成孔径雷达数据和地形辅助信息，构建多源特征协同编码网络，通过跨模态对齐和区域上下文建模增强建筑、道路、植被和水体等类别的区分能力。多城市区域实验表明，该方法能够提高总体分类精度和边界区域识别质量，为城市空间监测与土地利用调查提供可靠支持。",
                                                        "keywords": [
                                                                "遥感影像",
                                                                "地表覆盖分类",
                                                                "多源数据融合",
                                                                "跨模态对齐",
                                                                "城市空间监测"
                                                        ],
                                                        "language": "zh"
                                                },
                                                "is_interdisciplinary": false,
                                                "classification_count": 1,
                                                "classifications": [
                                                        {
                                                                "order": 1,
                                                                "role": "main",
                                                                "clc_code": "TP79",
                                                                "label": "遥感技术",
                                                                "path": "工业技术 > 自动化技术、计算机技术 > 遥感技术",
                                                                "confidence": 0.95,
                                                                "evidence": [
                                                                        "核心研究对象为多源遥感影像",
                                                                        "主要任务为城市地表覆盖精细分类"
                                                                ]
                                                        }
                                                ],
                                                "classification_confidence": 0.95,
                                                "domain_labels": [
                                                        {
                                                                "label": "遥感技术",
                                                                "confidence": 0.98
                                                        },
                                                        {
                                                                "label": "地表覆盖分类",
                                                                "confidence": 0.96
                                                        },
                                                        {
                                                                "label": "城市空间监测",
                                                                "confidence": 0.95
                                                        }
                                                ]
                                        }
                                }
                        ],
                        "classification_statistics_table": {
                                "document_count": 3,
                                "classified_document_count": 3,
                                "clc_category_count": 2,
                                "rows": [
                                        {
                                                "clc_code": "TP181",
                                                "category_name": "自动识别与检测",
                                                "classification_path": "工业技术 > 自动化技术、计算机技术 > 自动化基础理论 > 自动识别与检测",
                                                "document_count": 2,
                                                "document_percentage": 66.67,
                                                "average_confidence": 0.975
                                        },
                                        {
                                                "clc_code": "TP79",
                                                "category_name": "遥感技术",
                                                "classification_path": "工业技术 > 自动化技术、计算机技术 > 遥感技术",
                                                "document_count": 1,
                                                "document_percentage": 33.33,
                                                "average_confidence": 0.95
                                        }
                                ]
                        }
                },
                "meta": {
                        "max_concurrency": 3,
                        "elapsed_ms": 2186
                }
        },
        "demoBatchFileResult": {
                "code": 0,
                "message": "batch_completed",
                "data": {
                        "batch_id": "batch_classify_zh_file_202607190001",
                        "input_type": "files",
                        "total": 2,
                        "success_count": 2,
                        "failed_count": 0,
                        "results": [
                                {
                                        "index": 1,
                                        "file_name": "强化多视图多模态网络的社交媒体机器人检测.pdf",
                                        "status": "success",
                                        "code": 0,
                                        "result": {
                                                "tool": "中文科技文献分类",
                                                "input_type": "file",
                                                "document": {
                                                        "title": "强化多视图多模态网络的社交媒体机器人检测",
                                                        "abstract": "社交媒体机器人的快速增长虽然促进了信息传播，但也带来了隐私泄露和虚假信息传播等问题。因此，开发更加有效的机器人检测方法至关重要。提出了一种新颖的基于多头注意力机制和多视图集成分类的检测模型BotAttVCDN。该模型通过结合多模态数据，学习不同视图在标签空间中的重要性和相关性，有效捕捉多模态数据之间的关系，以提高分类性能。在Cresci-2015、TwiBot-20和TwiBot-22数据集上的实验结果表明，BotAttVCDN在分类准确率和F1-score方面均优于现有的13个基线模型，包括BotMOE和BotRGCN等。此外，通过结合注意力机制权重分配热图和SHAP分析，验证了BotAttVCDN模型不仅有效提升了社交媒体机器人检测的准确度和F1-score，还显著增强了可解释性，使得决策过程更加透明和易于理解。这表明，该模型在应对多样化和复杂化的社交媒体机器人检测任务中具有较高的竞争力和优越性。",
                                                        "keywords": [
                                                                "社交媒体机器人",
                                                                "BotAttVCDN模型",
                                                                "多模态数据",
                                                                "多头注意力机制",
                                                                "多视图集成",
                                                                "SHAP分析",
                                                                "可解释性"
                                                        ],
                                                        "language": "zh",
                                                        "file_type": "PDF",
                                                        "metadata_extraction_status": "success"
                                                },
                                                "is_interdisciplinary": false,
                                                "classification_count": 1,
                                                "classifications": [
                                                        {
                                                                "order": 1,
                                                                "role": "main",
                                                                "clc_code": "TP181",
                                                                "label": "自动识别与检测",
                                                                "path": "工业技术 > 自动化技术、计算机技术 > 自动化基础理论 > 自动识别与检测",
                                                                "confidence": 0.99,
                                                                "evidence": [
                                                                        "论文首页明确标注中图分类号：TP181",
                                                                        "核心任务为社交媒体机器人自动检测",
                                                                        "主要方法为多模态学习、多头注意力机制和多视图集成分类"
                                                                ]
                                                        }
                                                ],
                                                "classification_confidence": 0.99,
                                                "domain_labels": [
                                                        {
                                                                "label": "人工智能",
                                                                "confidence": 0.98
                                                        },
                                                        {
                                                                "label": "社交媒体安全",
                                                                "confidence": 0.95
                                                        },
                                                        {
                                                                "label": "多模态学习",
                                                                "confidence": 0.94
                                                        }
                                                ]
                                        }
                                },
                                {
                                        "index": 2,
                                        "file_name": "复杂工业表面微小缺陷检测方法.txt",
                                        "status": "success",
                                        "code": 0,
                                        "result": {
                                                "tool": "中文科技文献分类",
                                                "input_type": "file",
                                                "document": {
                                                        "title": "面向复杂工业表面的多尺度微小缺陷检测方法",
                                                        "abstract": "复杂工业表面中的裂纹、划痕与孔洞通常具有尺度差异大、边缘模糊和背景纹理干扰强等特点，导致传统视觉检测方法容易出现漏检和误检。本文提出一种融合多尺度特征金字塔、局部注意力增强和难样本重加权的工业表面缺陷检测方法，在不同分辨率下提取全局结构与局部细节，并通过跨层特征融合提升微小缺陷表征能力。多个公开工业缺陷数据集上的实验结果表明，该方法在检测准确率、召回率和小目标识别性能方面均优于对比模型，可为智能制造质量检测提供技术支撑。",
                                                        "keywords": [
                                                                "工业表面缺陷",
                                                                "微小目标检测",
                                                                "多尺度特征",
                                                                "注意力机制",
                                                                "机器视觉"
                                                        ],
                                                        "language": "zh",
                                                        "file_type": "TXT",
                                                        "metadata_extraction_status": "success"
                                                },
                                                "is_interdisciplinary": false,
                                                "classification_count": 1,
                                                "classifications": [
                                                        {
                                                                "order": 1,
                                                                "role": "main",
                                                                "clc_code": "TP181",
                                                                "label": "自动识别与检测",
                                                                "path": "工业技术 > 自动化技术、计算机技术 > 自动化基础理论 > 自动识别与检测",
                                                                "confidence": 0.96,
                                                                "evidence": [
                                                                        "核心任务为工业表面缺陷自动检测",
                                                                        "主要方法为机器视觉、多尺度特征建模和目标识别"
                                                                ]
                                                        }
                                                ],
                                                "classification_confidence": 0.96,
                                                "domain_labels": [
                                                        {
                                                                "label": "机器视觉",
                                                                "confidence": 0.97
                                                        },
                                                        {
                                                                "label": "工业缺陷检测",
                                                                "confidence": 0.96
                                                        },
                                                        {
                                                                "label": "智能制造",
                                                                "confidence": 0.94
                                                        }
                                                ]
                                        }
                                }
                        ],
                        "classification_statistics_table": {
                                "document_count": 2,
                                "classified_document_count": 2,
                                "clc_category_count": 1,
                                "rows": [
                                        {
                                                "clc_code": "TP181",
                                                "category_name": "自动识别与检测",
                                                "classification_path": "工业技术 > 自动化技术、计算机技术 > 自动化基础理论 > 自动识别与检测",
                                                "document_count": 2,
                                                "document_percentage": 100.0,
                                                "average_confidence": 0.975
                                        }
                                ]
                        }
                },
                "meta": {
                        "max_concurrency": 3,
                        "elapsed_ms": 2964
                }
        },
        "hasClassificationStatistics": true,
        "statisticsModes": [
                "batch-text",
                "batch"
        ]
},
      "en-classify": {
        "group": "自动分类工具",
        "title": "英文科技文献分类",
        "description": "依据中图分类法对英文科技文献进行跨语言自动分类。单篇任务输出中图分类号预测结果和一个主领域标签；批量任务额外输出中图分类号分布及主领域标签分布分析报告。",
        "features": "英文标题—摘要—关键词联合建模、跨语言中图类目映射、中图分类号预测、单一主领域标签、批量文献分布分析报告、批量文本分类、文档元数据自动提取、批量文件处理、单学科与跨学科自动判断",
        "scenarios": "SCI/EI文献分类、国际科技文献编目、跨语言文献管理、跨学科英文文献组织",
        "endpoint": "/api/v1/classify/clc/en/text",
        "textEndpoint": "/api/v1/classify/clc/en/text",
        "batchTextEndpoint": "/api/v1/classify/clc/en/texts",
        "fileEndpoint": "/api/v1/classify/clc/en/file",
        "batchFileEndpoint": "/api/v1/classify/clc/en/files",
        "languageCode": "en",
        "languageName": "英文",
        "documentType": "classification",
        "documentTarget": "英文文献标题、摘要和关键词",
        "inputModes": [
                "text",
                "batch-text",
                "file",
                "batch"
        ],
        "modeLabels": {
                "text": "单文本",
                "batch-text": "批量文本",
                "file": "单文件",
                "batch": "批量文件"
        },
        "supportsFileUpload": true,
        "supportsBatchUpload": true,
        "acceptedFiles": [
                ".pdf",
                ".docx",
                ".txt"
        ],
        "maxFileSizeMB": 50,
        "maxBatchFiles": 20,
        "maxBatchTexts": 20,
        "sampleFileName": "MOGONET.pdf",
        "sampleFileSize": "1.26 MB",
        "batchSampleFileNames": [
                "MOGONET.pdf",
                "HGTS-Former.txt"
        ],
        "demoFileSizeBytes": 1322087,
        "demoFileSha256": "6f6f55bc4c5556fdbdad09d2d51ca05bd8da9adb8e992d5fb0b85cac0f28cda5",
        "demoFileFnv1a32": "15a27ddf",
        "demoFileFixtures": [
                {
                        "file_name": "MOGONET.pdf",
                        "size_bytes": 1322087,
                        "sha256": "6f6f55bc4c5556fdbdad09d2d51ca05bd8da9adb8e992d5fb0b85cac0f28cda5",
                        "fnv1a32": "15a27ddf",
                        "result": {
                                "code": 0,
                                "message": "success",
                                "data": {
                                        "tool": "英文科技文献分类",
                                        "input_type": "file",
                                        "document": {
                                                "title": "MOGONET integrates multi-omics data using graph convolutional networks allowing patient classification and biomarker identification",
                                                "abstract": "To fully utilize the advances in omics technologies and achieve a more comprehensive understanding of human diseases, novel computational methods are required for integrative analysis of multiple types of omics data. Here, we present a novel multi-omics integrative method named Multi-Omics Graph cOnvolutional NETworks (MOGONET) for biomedical classification. MOGONET jointly explores omics-specific learning and cross-omics correlation learning for effective multi-omics data classification. We demonstrate that MOGONET outperforms other state-of-the-art supervised multi-omics integrative analysis approaches in different biomedical classification applications using mRNA expression data, DNA methylation data, and microRNA expression data. Furthermore, MOGONET can identify important biomarkers from different omics data types related to the investigated biomedical problems.",
                                                "keywords": [
                                                        "multi-omics data integration",
                                                        "graph convolutional networks",
                                                        "patient classification",
                                                        "biomarker identification",
                                                        "cross-omics correlation"
                                                ],
                                                "language": "en",
                                                "file_type": "PDF",
                                                "metadata_extraction_status": "success"
                                        },
                                        "is_interdisciplinary": true,
                                        "classification_count": 2,
                                        "classifications": [
                                                {
                                                        "order": 1,
                                                        "role": "main",
                                                        "clc_code": "Q811.4",
                                                        "label": "生物信息论",
                                                        "path": "生物科学 > 生物工程学 > 生物工程基础理论 > 生物信息论",
                                                        "confidence": 0.95,
                                                        "evidence": [
                                                                "The study integrates mRNA expression, DNA methylation, and microRNA expression data.",
                                                                "Its central application is biomedical patient classification and biomarker identification."
                                                        ]
                                                },
                                                {
                                                        "order": 2,
                                                        "role": "secondary",
                                                        "clc_code": "TP181",
                                                        "label": "自动识别与检测",
                                                        "path": "工业技术 > 自动化技术、计算机技术 > 自动化基础理论 > 自动识别与检测",
                                                        "confidence": 0.89,
                                                        "evidence": [
                                                                "The proposed method uses graph convolutional networks for supervised classification.",
                                                                "The technical contribution includes representation learning and automated classification."
                                                        ]
                                                }
                                        ],
                                        "domain_labels": [
                                                {
                                                        "label": "生物医学信息学",
                                                        "confidence": 0.98,
                                                        "role": "primary"
                                                }
                                        ]
                                },
                                "meta": {
                                        "request_id": "req_classify_en_file_202607190001",
                                        "elapsed_ms": 1530
                                }
                        }
                },
                {
                        "file_name": "HGTS-Former.txt",
                        "size_bytes": 874,
                        "sha256": "a16f4a14a9457f96fa487abb0c3acf34894835349f1a2839447e67ed49d32d46",
                        "fnv1a32": "8e512625",
                        "result": {
                                "code": 0,
                                "message": "success",
                                "data": {
                                        "tool": "英文科技文献分类",
                                        "input_type": "file",
                                        "document": {
                                                "title": "HGTS-Former: A Hypergraph-Based Transformer Backbone for Multivariate Time Series Analysis",
                                                "abstract": "Multivariate time series analysis remains challenging because of high dimensionality, dynamic temporal patterns, and complex interactions among variables. This paper proposes HGTS-Former, a hypergraph-based Transformer backbone for multivariate time series analysis. The method normalizes and embeds patches into tokens, applies multi-head self-attention, constructs hierarchical hypergraphs to aggregate temporal patterns and cross-variable relations, and converts hyperedge features into node representations. Experiments on multiple representative time series tasks and public datasets validate the effectiveness of the proposed model.",
                                                "keywords": [
                                                        "multivariate time series",
                                                        "hypergraph neural network",
                                                        "Transformer",
                                                        "multi-head self-attention",
                                                        "cross-variable relations"
                                                ],
                                                "language": "en",
                                                "file_type": "TXT",
                                                "metadata_extraction_status": "success"
                                        },
                                        "is_interdisciplinary": false,
                                        "classification_count": 1,
                                        "classifications": [
                                                {
                                                        "order": 1,
                                                        "role": "main",
                                                        "clc_code": "TP181",
                                                        "label": "自动识别与检测",
                                                        "path": "工业技术 > 自动化技术、计算机技术 > 自动化基础理论 > 自动识别与检测",
                                                        "confidence": 0.96,
                                                        "evidence": [
                                                                "The core contribution is a Transformer and hypergraph learning model.",
                                                                "The work focuses on automated multivariate time-series representation and analysis."
                                                        ]
                                                }
                                        ],
                                        "domain_labels": [
                                                {
                                                        "label": "时间序列分析",
                                                        "confidence": 0.97,
                                                        "role": "primary"
                                                }
                                        ]
                                },
                                "meta": {
                                        "request_id": "req_classify_en_file_202607190002",
                                        "elapsed_ms": 1530
                                }
                        }
                }
        ],
        "fileProcessingHint": "上传后自动提取英文文献标题、摘要和关键词，并根据真实研究内容完成中图分类",
        "batchProcessingHint": "批量接口按文件分别提取英文题名、摘要和关键词，并返回每篇文献的实际分类数量。",
        "params": [
                [
                        "input_type",
                        "string",
                        "required",
                        "输入方式，取值为 text、texts、file 或 files"
                ],
                [
                        "title",
                        "string",
                        "conditional",
                        "当 input_type=text 时必填：英文科技文献标题"
                ],
                [
                        "abstract",
                        "string",
                        "conditional",
                        "当 input_type=text 时必填：英文科技文献摘要"
                ],
                [
                        "keywords",
                        "string[]",
                        "conditional",
                        "当 input_type=text 时必填：英文关键词列表"
                ],
                [
                        "texts",
                        "object[]",
                        "conditional",
                        "当 input_type=texts 时必填：每条包含 id、title、abstract 和 keywords，最多20条"
                ],
                [
                        "file",
                        "file",
                        "conditional",
                        "当 input_type=file 时必填：上传一个 PDF、DOCX 或 TXT 文件"
                ],
                [
                        "files",
                        "file[]",
                        "conditional",
                        "当 input_type=files 时必填：批量上传 PDF、DOCX 或 TXT 文件，最多20个"
                ],
                [
                        "max_concurrency",
                        "integer",
                        "optional",
                        "批量任务并发数，默认3"
                ],
                [
                        "continue_on_error",
                        "boolean",
                        "optional",
                        "单条任务失败时是否继续处理其他任务，默认true"
                ]
        ],
        "payload": {
                "input_type": "text",
                "title": "MOGONET integrates multi-omics data using graph convolutional networks allowing patient classification and biomarker identification",
                "abstract": "To fully utilize the advances in omics technologies and achieve a more comprehensive understanding of human diseases, novel computational methods are required for integrative analysis of multiple types of omics data. Here, we present a novel multi-omics integrative method named Multi-Omics Graph cOnvolutional NETworks (MOGONET) for biomedical classification. MOGONET jointly explores omics-specific learning and cross-omics correlation learning for effective multi-omics data classification. We demonstrate that MOGONET outperforms other state-of-the-art supervised multi-omics integrative analysis approaches in different biomedical classification applications using mRNA expression data, DNA methylation data, and microRNA expression data. Furthermore, MOGONET can identify important biomarkers from different omics data types related to the investigated biomedical problems.",
                "keywords": [
                        "multi-omics data integration",
                        "graph convolutional networks",
                        "patient classification",
                        "biomarker identification",
                        "cross-omics correlation"
                ]
        },
        "demoClassificationInput": {
                "title": "MOGONET integrates multi-omics data using graph convolutional networks allowing patient classification and biomarker identification",
                "abstract": "To fully utilize the advances in omics technologies and achieve a more comprehensive understanding of human diseases, novel computational methods are required for integrative analysis of multiple types of omics data. Here, we present a novel multi-omics integrative method named Multi-Omics Graph cOnvolutional NETworks (MOGONET) for biomedical classification. MOGONET jointly explores omics-specific learning and cross-omics correlation learning for effective multi-omics data classification. We demonstrate that MOGONET outperforms other state-of-the-art supervised multi-omics integrative analysis approaches in different biomedical classification applications using mRNA expression data, DNA methylation data, and microRNA expression data. Furthermore, MOGONET can identify important biomarkers from different omics data types related to the investigated biomedical problems.",
                "keywords": [
                        "multi-omics data integration",
                        "graph convolutional networks",
                        "patient classification",
                        "biomarker identification",
                        "cross-omics correlation"
                ]
        },
        "demoBatchClassificationInputs": [
                {
                        "id": "text1",
                        "title": "MOGONET integrates multi-omics data using graph convolutional networks allowing patient classification and biomarker identification",
                        "abstract": "To fully utilize the advances in omics technologies and achieve a more comprehensive understanding of human diseases, novel computational methods are required for integrative analysis of multiple types of omics data. Here, we present a novel multi-omics integrative method named Multi-Omics Graph cOnvolutional NETworks (MOGONET) for biomedical classification. MOGONET jointly explores omics-specific learning and cross-omics correlation learning for effective multi-omics data classification. We demonstrate that MOGONET outperforms other state-of-the-art supervised multi-omics integrative analysis approaches in different biomedical classification applications using mRNA expression data, DNA methylation data, and microRNA expression data. Furthermore, MOGONET can identify important biomarkers from different omics data types related to the investigated biomedical problems.",
                        "keywords": [
                                "multi-omics data integration",
                                "graph convolutional networks",
                                "patient classification",
                                "biomarker identification",
                                "cross-omics correlation"
                        ]
                },
                {
                        "id": "text2",
                        "title": "HGTS-Former: A Hypergraph-Based Transformer Backbone for Multivariate Time Series Analysis",
                        "abstract": "Multivariate time series analysis remains challenging because of high dimensionality, dynamic temporal patterns, and complex interactions among variables. This paper proposes HGTS-Former, a hypergraph-based Transformer backbone for multivariate time series analysis. The method normalizes and embeds patches into tokens, applies multi-head self-attention, constructs hierarchical hypergraphs to aggregate temporal patterns and cross-variable relations, and converts hyperedge features into node representations. Experiments on multiple representative time series tasks and public datasets validate the effectiveness of the proposed model.",
                        "keywords": [
                                "multivariate time series",
                                "hypergraph neural network",
                                "Transformer",
                                "multi-head self-attention",
                                "cross-variable relations"
                        ]
                },
                {
                        "id": "text3",
                        "title": "FAST-MAD: Resource-Aware Federated Multivariate Time Series Anomaly Detection",
                        "abstract": "Time series anomaly detection aims to identify samples that deviate from normal distributions and is important in many real-world applications. Existing methods are mostly centralized and domain-specific, making them difficult to generalize across decentralized institutions with privacy constraints. This paper proposes FAST-MAD, a resource-aware framework for federated multivariate time series anomaly detection. It combines multi-resolution transformation, frequency-oriented patching, inter-series interaction, modularized model separation, sharded federated training, and decomposed client-server alignment. Experiments demonstrate effective anomaly detection under heterogeneous data distributions and constrained computational resources.",
                        "keywords": [
                                "time series anomaly detection",
                                "federated learning",
                                "multi-resolution transformation",
                                "data heterogeneity",
                                "resource-aware learning"
                        ]
                }
        ],
        "demoBatchClassificationResults": [
                {
                        "id": "text1",
                        "title": "MOGONET integrates multi-omics data using graph convolutional networks allowing patient classification and biomarker identification",
                        "abstract": "To fully utilize the advances in omics technologies and achieve a more comprehensive understanding of human diseases, novel computational methods are required for integrative analysis of multiple types of omics data. Here, we present a novel multi-omics integrative method named Multi-Omics Graph cOnvolutional NETworks (MOGONET) for biomedical classification. MOGONET jointly explores omics-specific learning and cross-omics correlation learning for effective multi-omics data classification. We demonstrate that MOGONET outperforms other state-of-the-art supervised multi-omics integrative analysis approaches in different biomedical classification applications using mRNA expression data, DNA methylation data, and microRNA expression data. Furthermore, MOGONET can identify important biomarkers from different omics data types related to the investigated biomedical problems.",
                        "keywords": [
                                "multi-omics data integration",
                                "graph convolutional networks",
                                "patient classification",
                                "biomarker identification",
                                "cross-omics correlation"
                        ],
                        "classifications": [
                                {
                                        "order": 1,
                                        "role": "main",
                                        "clc_code": "Q811.4",
                                        "label": "生物信息论",
                                        "path": "生物科学 > 生物工程学 > 生物工程基础理论 > 生物信息论",
                                        "confidence": 0.95,
                                        "evidence": [
                                                "The study integrates mRNA expression, DNA methylation, and microRNA expression data.",
                                                "Its central application is biomedical patient classification and biomarker identification."
                                        ]
                                },
                                {
                                        "order": 2,
                                        "role": "secondary",
                                        "clc_code": "TP181",
                                        "label": "自动识别与检测",
                                        "path": "工业技术 > 自动化技术、计算机技术 > 自动化基础理论 > 自动识别与检测",
                                        "confidence": 0.89,
                                        "evidence": [
                                                "The proposed method uses graph convolutional networks for supervised classification.",
                                                "The technical contribution includes representation learning and automated classification."
                                        ]
                                }
                        ],
                        "domain_labels": [
                                {
                                        "label": "生物医学信息学",
                                        "confidence": 0.98,
                                        "role": "primary"
                                }
                        ]
                },
                {
                        "id": "text2",
                        "title": "HGTS-Former: A Hypergraph-Based Transformer Backbone for Multivariate Time Series Analysis",
                        "abstract": "Multivariate time series analysis remains challenging because of high dimensionality, dynamic temporal patterns, and complex interactions among variables. This paper proposes HGTS-Former, a hypergraph-based Transformer backbone for multivariate time series analysis. The method normalizes and embeds patches into tokens, applies multi-head self-attention, constructs hierarchical hypergraphs to aggregate temporal patterns and cross-variable relations, and converts hyperedge features into node representations. Experiments on multiple representative time series tasks and public datasets validate the effectiveness of the proposed model.",
                        "keywords": [
                                "multivariate time series",
                                "hypergraph neural network",
                                "Transformer",
                                "multi-head self-attention",
                                "cross-variable relations"
                        ],
                        "classifications": [
                                {
                                        "order": 1,
                                        "role": "main",
                                        "clc_code": "TP181",
                                        "label": "自动识别与检测",
                                        "path": "工业技术 > 自动化技术、计算机技术 > 自动化基础理论 > 自动识别与检测",
                                        "confidence": 0.96,
                                        "evidence": [
                                                "The core contribution is a Transformer and hypergraph learning model.",
                                                "The work focuses on automated multivariate time-series representation and analysis."
                                        ]
                                }
                        ],
                        "domain_labels": [
                                {
                                        "label": "时间序列分析",
                                        "confidence": 0.97,
                                        "role": "primary"
                                }
                        ]
                },
                {
                        "id": "text3",
                        "title": "FAST-MAD: Resource-Aware Federated Multivariate Time Series Anomaly Detection",
                        "abstract": "Time series anomaly detection aims to identify samples that deviate from normal distributions and is important in many real-world applications. Existing methods are mostly centralized and domain-specific, making them difficult to generalize across decentralized institutions with privacy constraints. This paper proposes FAST-MAD, a resource-aware framework for federated multivariate time series anomaly detection. It combines multi-resolution transformation, frequency-oriented patching, inter-series interaction, modularized model separation, sharded federated training, and decomposed client-server alignment. Experiments demonstrate effective anomaly detection under heterogeneous data distributions and constrained computational resources.",
                        "keywords": [
                                "time series anomaly detection",
                                "federated learning",
                                "multi-resolution transformation",
                                "data heterogeneity",
                                "resource-aware learning"
                        ],
                        "classifications": [
                                {
                                        "order": 1,
                                        "role": "main",
                                        "clc_code": "TP181",
                                        "label": "自动识别与检测",
                                        "path": "工业技术 > 自动化技术、计算机技术 > 自动化基础理论 > 自动识别与检测",
                                        "confidence": 0.94,
                                        "evidence": [
                                                "The primary task is automatic anomaly detection in multivariate time series.",
                                                "Federated learning is used as the training architecture rather than a separate research domain."
                                        ]
                                }
                        ],
                        "domain_labels": [
                                {
                                        "label": "时间序列分析",
                                        "confidence": 0.96,
                                        "role": "primary"
                                }
                        ]
                }
        ],
        "demoTextResult": {
                "code": 0,
                "message": "success",
                "data": {
                        "tool": "英文科技文献分类",
                        "input_type": "text",
                        "document": {
                                "title": "MOGONET integrates multi-omics data using graph convolutional networks allowing patient classification and biomarker identification",
                                "abstract": "To fully utilize the advances in omics technologies and achieve a more comprehensive understanding of human diseases, novel computational methods are required for integrative analysis of multiple types of omics data. Here, we present a novel multi-omics integrative method named Multi-Omics Graph cOnvolutional NETworks (MOGONET) for biomedical classification. MOGONET jointly explores omics-specific learning and cross-omics correlation learning for effective multi-omics data classification. We demonstrate that MOGONET outperforms other state-of-the-art supervised multi-omics integrative analysis approaches in different biomedical classification applications using mRNA expression data, DNA methylation data, and microRNA expression data. Furthermore, MOGONET can identify important biomarkers from different omics data types related to the investigated biomedical problems.",
                                "keywords": [
                                        "multi-omics data integration",
                                        "graph convolutional networks",
                                        "patient classification",
                                        "biomarker identification",
                                        "cross-omics correlation"
                                ],
                                "language": "en"
                        },
                        "is_interdisciplinary": true,
                        "classification_count": 2,
                        "classifications": [
                                {
                                        "order": 1,
                                        "role": "main",
                                        "clc_code": "Q811.4",
                                        "label": "生物信息论",
                                        "path": "生物科学 > 生物工程学 > 生物工程基础理论 > 生物信息论",
                                        "confidence": 0.95,
                                        "evidence": [
                                                "The study integrates mRNA expression, DNA methylation, and microRNA expression data.",
                                                "Its central application is biomedical patient classification and biomarker identification."
                                        ]
                                },
                                {
                                        "order": 2,
                                        "role": "secondary",
                                        "clc_code": "TP181",
                                        "label": "自动识别与检测",
                                        "path": "工业技术 > 自动化技术、计算机技术 > 自动化基础理论 > 自动识别与检测",
                                        "confidence": 0.89,
                                        "evidence": [
                                                "The proposed method uses graph convolutional networks for supervised classification.",
                                                "The technical contribution includes representation learning and automated classification."
                                        ]
                                }
                        ],
                        "domain_labels": [
                                {
                                        "label": "生物医学信息学",
                                        "confidence": 0.98,
                                        "role": "primary"
                                }
                        ]
                },
                "meta": {
                        "request_id": "req_classify_en_text_202607190001",
                        "elapsed_ms": 980
                }
        },
        "demoBatchTextResult": {
                "code": 0,
                "message": "batch_completed",
                "data": {
                        "batch_id": "batch_classify_en_text_202607190001",
                        "input_type": "texts",
                        "total": 3,
                        "success_count": 3,
                        "failed_count": 0,
                        "results": [
                                {
                                        "index": 1,
                                        "input_id": "text1",
                                        "status": "success",
                                        "code": 0,
                                        "result": {
                                                "tool": "英文科技文献分类",
                                                "input_type": "text",
                                                "document": {
                                                        "title": "MOGONET integrates multi-omics data using graph convolutional networks allowing patient classification and biomarker identification",
                                                        "abstract": "To fully utilize the advances in omics technologies and achieve a more comprehensive understanding of human diseases, novel computational methods are required for integrative analysis of multiple types of omics data. Here, we present a novel multi-omics integrative method named Multi-Omics Graph cOnvolutional NETworks (MOGONET) for biomedical classification. MOGONET jointly explores omics-specific learning and cross-omics correlation learning for effective multi-omics data classification. We demonstrate that MOGONET outperforms other state-of-the-art supervised multi-omics integrative analysis approaches in different biomedical classification applications using mRNA expression data, DNA methylation data, and microRNA expression data. Furthermore, MOGONET can identify important biomarkers from different omics data types related to the investigated biomedical problems.",
                                                        "keywords": [
                                                                "multi-omics data integration",
                                                                "graph convolutional networks",
                                                                "patient classification",
                                                                "biomarker identification",
                                                                "cross-omics correlation"
                                                        ],
                                                        "language": "en"
                                                },
                                                "is_interdisciplinary": true,
                                                "classification_count": 2,
                                                "classifications": [
                                                        {
                                                                "order": 1,
                                                                "role": "main",
                                                                "clc_code": "Q811.4",
                                                                "label": "生物信息论",
                                                                "path": "生物科学 > 生物工程学 > 生物工程基础理论 > 生物信息论",
                                                                "confidence": 0.95,
                                                                "evidence": [
                                                                        "The study integrates mRNA expression, DNA methylation, and microRNA expression data.",
                                                                        "Its central application is biomedical patient classification and biomarker identification."
                                                                ]
                                                        },
                                                        {
                                                                "order": 2,
                                                                "role": "secondary",
                                                                "clc_code": "TP181",
                                                                "label": "自动识别与检测",
                                                                "path": "工业技术 > 自动化技术、计算机技术 > 自动化基础理论 > 自动识别与检测",
                                                                "confidence": 0.89,
                                                                "evidence": [
                                                                        "The proposed method uses graph convolutional networks for supervised classification.",
                                                                        "The technical contribution includes representation learning and automated classification."
                                                                ]
                                                        }
                                                ],
                                                "domain_labels": [
                                                        {
                                                                "label": "生物医学信息学",
                                                                "confidence": 0.98,
                                                                "role": "primary"
                                                        }
                                                ]
                                        }
                                },
                                {
                                        "index": 2,
                                        "input_id": "text2",
                                        "status": "success",
                                        "code": 0,
                                        "result": {
                                                "tool": "英文科技文献分类",
                                                "input_type": "text",
                                                "document": {
                                                        "title": "HGTS-Former: A Hypergraph-Based Transformer Backbone for Multivariate Time Series Analysis",
                                                        "abstract": "Multivariate time series analysis remains challenging because of high dimensionality, dynamic temporal patterns, and complex interactions among variables. This paper proposes HGTS-Former, a hypergraph-based Transformer backbone for multivariate time series analysis. The method normalizes and embeds patches into tokens, applies multi-head self-attention, constructs hierarchical hypergraphs to aggregate temporal patterns and cross-variable relations, and converts hyperedge features into node representations. Experiments on multiple representative time series tasks and public datasets validate the effectiveness of the proposed model.",
                                                        "keywords": [
                                                                "multivariate time series",
                                                                "hypergraph neural network",
                                                                "Transformer",
                                                                "multi-head self-attention",
                                                                "cross-variable relations"
                                                        ],
                                                        "language": "en"
                                                },
                                                "is_interdisciplinary": false,
                                                "classification_count": 1,
                                                "classifications": [
                                                        {
                                                                "order": 1,
                                                                "role": "main",
                                                                "clc_code": "TP181",
                                                                "label": "自动识别与检测",
                                                                "path": "工业技术 > 自动化技术、计算机技术 > 自动化基础理论 > 自动识别与检测",
                                                                "confidence": 0.96,
                                                                "evidence": [
                                                                        "The core contribution is a Transformer and hypergraph learning model.",
                                                                        "The work focuses on automated multivariate time-series representation and analysis."
                                                                ]
                                                        }
                                                ],
                                                "domain_labels": [
                                                        {
                                                                "label": "时间序列分析",
                                                                "confidence": 0.97,
                                                                "role": "primary"
                                                        }
                                                ]
                                        }
                                },
                                {
                                        "index": 3,
                                        "input_id": "text3",
                                        "status": "success",
                                        "code": 0,
                                        "result": {
                                                "tool": "英文科技文献分类",
                                                "input_type": "text",
                                                "document": {
                                                        "title": "FAST-MAD: Resource-Aware Federated Multivariate Time Series Anomaly Detection",
                                                        "abstract": "Time series anomaly detection aims to identify samples that deviate from normal distributions and is important in many real-world applications. Existing methods are mostly centralized and domain-specific, making them difficult to generalize across decentralized institutions with privacy constraints. This paper proposes FAST-MAD, a resource-aware framework for federated multivariate time series anomaly detection. It combines multi-resolution transformation, frequency-oriented patching, inter-series interaction, modularized model separation, sharded federated training, and decomposed client-server alignment. Experiments demonstrate effective anomaly detection under heterogeneous data distributions and constrained computational resources.",
                                                        "keywords": [
                                                                "time series anomaly detection",
                                                                "federated learning",
                                                                "multi-resolution transformation",
                                                                "data heterogeneity",
                                                                "resource-aware learning"
                                                        ],
                                                        "language": "en"
                                                },
                                                "is_interdisciplinary": false,
                                                "classification_count": 1,
                                                "classifications": [
                                                        {
                                                                "order": 1,
                                                                "role": "main",
                                                                "clc_code": "TP181",
                                                                "label": "自动识别与检测",
                                                                "path": "工业技术 > 自动化技术、计算机技术 > 自动化基础理论 > 自动识别与检测",
                                                                "confidence": 0.94,
                                                                "evidence": [
                                                                        "The primary task is automatic anomaly detection in multivariate time series.",
                                                                        "Federated learning is used as the training architecture rather than a separate research domain."
                                                                ]
                                                        }
                                                ],
                                                "domain_labels": [
                                                        {
                                                                "label": "时间序列分析",
                                                                "confidence": 0.96,
                                                                "role": "primary"
                                                        }
                                                ]
                                        }
                                }
                        ],
                        "literature_distribution_analysis_report": {
                                "document_count": 3,
                                "classified_document_count": 3,
                                "clc_category_count": 2,
                                "domain_label_count": 2,
                                "by_clc_category": [
                                        {
                                                "clc_code": "TP181",
                                                "category_name": "自动识别与检测",
                                                "classification_path": "工业技术 > 自动化技术、计算机技术 > 自动化基础理论 > 自动识别与检测",
                                                "document_count": 3,
                                                "document_percentage": 100.0,
                                                "average_confidence": 0.93
                                        },
                                        {
                                                "clc_code": "Q811.4",
                                                "category_name": "生物信息论",
                                                "classification_path": "生物科学 > 生物工程学 > 生物工程基础理论 > 生物信息论",
                                                "document_count": 1,
                                                "document_percentage": 33.33,
                                                "average_confidence": 0.95
                                        }
                                ],
                                "by_domain_label": [
                                        {
                                                "label": "时间序列分析",
                                                "document_count": 2,
                                                "document_percentage": 66.67,
                                                "average_confidence": 0.965
                                        },
                                        {
                                                "label": "生物医学信息学",
                                                "document_count": 1,
                                                "document_percentage": 33.33,
                                                "average_confidence": 0.98
                                        }
                                ],
                                "domain_label_scope": "primary_only"
                        }
                },
                "meta": {
                        "max_concurrency": 3,
                        "elapsed_ms": 2314
                }
        },
        "demoFileResult": {
                "code": 0,
                "message": "success",
                "data": {
                        "tool": "英文科技文献分类",
                        "input_type": "file",
                        "document": {
                                "title": "MOGONET integrates multi-omics data using graph convolutional networks allowing patient classification and biomarker identification",
                                "abstract": "To fully utilize the advances in omics technologies and achieve a more comprehensive understanding of human diseases, novel computational methods are required for integrative analysis of multiple types of omics data. Here, we present a novel multi-omics integrative method named Multi-Omics Graph cOnvolutional NETworks (MOGONET) for biomedical classification. MOGONET jointly explores omics-specific learning and cross-omics correlation learning for effective multi-omics data classification. We demonstrate that MOGONET outperforms other state-of-the-art supervised multi-omics integrative analysis approaches in different biomedical classification applications using mRNA expression data, DNA methylation data, and microRNA expression data. Furthermore, MOGONET can identify important biomarkers from different omics data types related to the investigated biomedical problems.",
                                "keywords": [
                                        "multi-omics data integration",
                                        "graph convolutional networks",
                                        "patient classification",
                                        "biomarker identification",
                                        "cross-omics correlation"
                                ],
                                "language": "en",
                                "file_type": "PDF",
                                "metadata_extraction_status": "success"
                        },
                        "is_interdisciplinary": true,
                        "classification_count": 2,
                        "classifications": [
                                {
                                        "order": 1,
                                        "role": "main",
                                        "clc_code": "Q811.4",
                                        "label": "生物信息论",
                                        "path": "生物科学 > 生物工程学 > 生物工程基础理论 > 生物信息论",
                                        "confidence": 0.95,
                                        "evidence": [
                                                "The study integrates mRNA expression, DNA methylation, and microRNA expression data.",
                                                "Its central application is biomedical patient classification and biomarker identification."
                                        ]
                                },
                                {
                                        "order": 2,
                                        "role": "secondary",
                                        "clc_code": "TP181",
                                        "label": "自动识别与检测",
                                        "path": "工业技术 > 自动化技术、计算机技术 > 自动化基础理论 > 自动识别与检测",
                                        "confidence": 0.89,
                                        "evidence": [
                                                "The proposed method uses graph convolutional networks for supervised classification.",
                                                "The technical contribution includes representation learning and automated classification."
                                        ]
                                }
                        ],
                        "domain_labels": [
                                {
                                        "label": "生物医学信息学",
                                        "confidence": 0.98,
                                        "role": "primary"
                                }
                        ]
                },
                "meta": {
                        "request_id": "req_classify_en_file_202607190001",
                        "elapsed_ms": 1530
                }
        },
        "demoBatchFileResult": {
                "code": 0,
                "message": "batch_completed",
                "data": {
                        "batch_id": "batch_classify_en_file_202607190001",
                        "input_type": "files",
                        "total": 2,
                        "success_count": 2,
                        "failed_count": 0,
                        "results": [
                                {
                                        "index": 1,
                                        "file_name": "MOGONET.pdf",
                                        "status": "success",
                                        "code": 0,
                                        "result": {
                                                "tool": "英文科技文献分类",
                                                "input_type": "file",
                                                "document": {
                                                        "title": "MOGONET integrates multi-omics data using graph convolutional networks allowing patient classification and biomarker identification",
                                                        "abstract": "To fully utilize the advances in omics technologies and achieve a more comprehensive understanding of human diseases, novel computational methods are required for integrative analysis of multiple types of omics data. Here, we present a novel multi-omics integrative method named Multi-Omics Graph cOnvolutional NETworks (MOGONET) for biomedical classification. MOGONET jointly explores omics-specific learning and cross-omics correlation learning for effective multi-omics data classification. We demonstrate that MOGONET outperforms other state-of-the-art supervised multi-omics integrative analysis approaches in different biomedical classification applications using mRNA expression data, DNA methylation data, and microRNA expression data. Furthermore, MOGONET can identify important biomarkers from different omics data types related to the investigated biomedical problems.",
                                                        "keywords": [
                                                                "multi-omics data integration",
                                                                "graph convolutional networks",
                                                                "patient classification",
                                                                "biomarker identification",
                                                                "cross-omics correlation"
                                                        ],
                                                        "language": "en",
                                                        "file_type": "PDF",
                                                        "metadata_extraction_status": "success"
                                                },
                                                "is_interdisciplinary": true,
                                                "classification_count": 2,
                                                "classifications": [
                                                        {
                                                                "order": 1,
                                                                "role": "main",
                                                                "clc_code": "Q811.4",
                                                                "label": "生物信息论",
                                                                "path": "生物科学 > 生物工程学 > 生物工程基础理论 > 生物信息论",
                                                                "confidence": 0.95,
                                                                "evidence": [
                                                                        "The study integrates mRNA expression, DNA methylation, and microRNA expression data.",
                                                                        "Its central application is biomedical patient classification and biomarker identification."
                                                                ]
                                                        },
                                                        {
                                                                "order": 2,
                                                                "role": "secondary",
                                                                "clc_code": "TP181",
                                                                "label": "自动识别与检测",
                                                                "path": "工业技术 > 自动化技术、计算机技术 > 自动化基础理论 > 自动识别与检测",
                                                                "confidence": 0.89,
                                                                "evidence": [
                                                                        "The proposed method uses graph convolutional networks for supervised classification.",
                                                                        "The technical contribution includes representation learning and automated classification."
                                                                ]
                                                        }
                                                ],
                                                "domain_labels": [
                                                        {
                                                                "label": "生物医学信息学",
                                                                "confidence": 0.98,
                                                                "role": "primary"
                                                        }
                                                ]
                                        }
                                },
                                {
                                        "index": 2,
                                        "file_name": "HGTS-Former.txt",
                                        "status": "success",
                                        "code": 0,
                                        "result": {
                                                "tool": "英文科技文献分类",
                                                "input_type": "file",
                                                "document": {
                                                        "title": "HGTS-Former: A Hypergraph-Based Transformer Backbone for Multivariate Time Series Analysis",
                                                        "abstract": "Multivariate time series analysis remains challenging because of high dimensionality, dynamic temporal patterns, and complex interactions among variables. This paper proposes HGTS-Former, a hypergraph-based Transformer backbone for multivariate time series analysis. The method normalizes and embeds patches into tokens, applies multi-head self-attention, constructs hierarchical hypergraphs to aggregate temporal patterns and cross-variable relations, and converts hyperedge features into node representations. Experiments on multiple representative time series tasks and public datasets validate the effectiveness of the proposed model.",
                                                        "keywords": [
                                                                "multivariate time series",
                                                                "hypergraph neural network",
                                                                "Transformer",
                                                                "multi-head self-attention",
                                                                "cross-variable relations"
                                                        ],
                                                        "language": "en",
                                                        "file_type": "TXT",
                                                        "metadata_extraction_status": "success"
                                                },
                                                "is_interdisciplinary": false,
                                                "classification_count": 1,
                                                "classifications": [
                                                        {
                                                                "order": 1,
                                                                "role": "main",
                                                                "clc_code": "TP181",
                                                                "label": "自动识别与检测",
                                                                "path": "工业技术 > 自动化技术、计算机技术 > 自动化基础理论 > 自动识别与检测",
                                                                "confidence": 0.96,
                                                                "evidence": [
                                                                        "The core contribution is a Transformer and hypergraph learning model.",
                                                                        "The work focuses on automated multivariate time-series representation and analysis."
                                                                ]
                                                        }
                                                ],
                                                "domain_labels": [
                                                        {
                                                                "label": "时间序列分析",
                                                                "confidence": 0.97,
                                                                "role": "primary"
                                                        }
                                                ]
                                        }
                                }
                        ],
                        "literature_distribution_analysis_report": {
                                "document_count": 2,
                                "classified_document_count": 2,
                                "clc_category_count": 2,
                                "domain_label_count": 2,
                                "by_clc_category": [
                                        {
                                                "clc_code": "TP181",
                                                "category_name": "自动识别与检测",
                                                "classification_path": "工业技术 > 自动化技术、计算机技术 > 自动化基础理论 > 自动识别与检测",
                                                "document_count": 2,
                                                "document_percentage": 100.0,
                                                "average_confidence": 0.925
                                        },
                                        {
                                                "clc_code": "Q811.4",
                                                "category_name": "生物信息论",
                                                "classification_path": "生物科学 > 生物工程学 > 生物工程基础理论 > 生物信息论",
                                                "document_count": 1,
                                                "document_percentage": 50.0,
                                                "average_confidence": 0.95
                                        }
                                ],
                                "by_domain_label": [
                                        {
                                                "label": "时间序列分析",
                                                "document_count": 1,
                                                "document_percentage": 50.0,
                                                "average_confidence": 0.97
                                        },
                                        {
                                                "label": "生物医学信息学",
                                                "document_count": 1,
                                                "document_percentage": 50.0,
                                                "average_confidence": 0.98
                                        }
                                ],
                                "domain_label_scope": "primary_only"
                        }
                },
                "meta": {
                        "max_concurrency": 3,
                        "elapsed_ms": 3072
                }
        },
        "response": {
                "code": 0,
                "message": "batch_completed",
                "data": {
                        "batch_id": "batch_classify_en_file_202607190001",
                        "input_type": "files",
                        "total": 2,
                        "success_count": 2,
                        "failed_count": 0,
                        "results": [
                                {
                                        "index": 1,
                                        "file_name": "MOGONET.pdf",
                                        "status": "success",
                                        "code": 0,
                                        "result": {
                                                "tool": "英文科技文献分类",
                                                "input_type": "file",
                                                "document": {
                                                        "title": "MOGONET integrates multi-omics data using graph convolutional networks allowing patient classification and biomarker identification",
                                                        "abstract": "To fully utilize the advances in omics technologies and achieve a more comprehensive understanding of human diseases, novel computational methods are required for integrative analysis of multiple types of omics data. Here, we present a novel multi-omics integrative method named Multi-Omics Graph cOnvolutional NETworks (MOGONET) for biomedical classification. MOGONET jointly explores omics-specific learning and cross-omics correlation learning for effective multi-omics data classification. We demonstrate that MOGONET outperforms other state-of-the-art supervised multi-omics integrative analysis approaches in different biomedical classification applications using mRNA expression data, DNA methylation data, and microRNA expression data. Furthermore, MOGONET can identify important biomarkers from different omics data types related to the investigated biomedical problems.",
                                                        "keywords": [
                                                                "multi-omics data integration",
                                                                "graph convolutional networks",
                                                                "patient classification",
                                                                "biomarker identification",
                                                                "cross-omics correlation"
                                                        ],
                                                        "language": "en",
                                                        "file_type": "PDF",
                                                        "metadata_extraction_status": "success"
                                                },
                                                "is_interdisciplinary": true,
                                                "classification_count": 2,
                                                "classifications": [
                                                        {
                                                                "order": 1,
                                                                "role": "main",
                                                                "clc_code": "Q811.4",
                                                                "label": "生物信息论",
                                                                "path": "生物科学 > 生物工程学 > 生物工程基础理论 > 生物信息论",
                                                                "confidence": 0.95,
                                                                "evidence": [
                                                                        "The study integrates mRNA expression, DNA methylation, and microRNA expression data.",
                                                                        "Its central application is biomedical patient classification and biomarker identification."
                                                                ]
                                                        },
                                                        {
                                                                "order": 2,
                                                                "role": "secondary",
                                                                "clc_code": "TP181",
                                                                "label": "自动识别与检测",
                                                                "path": "工业技术 > 自动化技术、计算机技术 > 自动化基础理论 > 自动识别与检测",
                                                                "confidence": 0.89,
                                                                "evidence": [
                                                                        "The proposed method uses graph convolutional networks for supervised classification.",
                                                                        "The technical contribution includes representation learning and automated classification."
                                                                ]
                                                        }
                                                ],
                                                "domain_labels": [
                                                        {
                                                                "label": "生物医学信息学",
                                                                "confidence": 0.98,
                                                                "role": "primary"
                                                        }
                                                ]
                                        }
                                },
                                {
                                        "index": 2,
                                        "file_name": "HGTS-Former.txt",
                                        "status": "success",
                                        "code": 0,
                                        "result": {
                                                "tool": "英文科技文献分类",
                                                "input_type": "file",
                                                "document": {
                                                        "title": "HGTS-Former: A Hypergraph-Based Transformer Backbone for Multivariate Time Series Analysis",
                                                        "abstract": "Multivariate time series analysis remains challenging because of high dimensionality, dynamic temporal patterns, and complex interactions among variables. This paper proposes HGTS-Former, a hypergraph-based Transformer backbone for multivariate time series analysis. The method normalizes and embeds patches into tokens, applies multi-head self-attention, constructs hierarchical hypergraphs to aggregate temporal patterns and cross-variable relations, and converts hyperedge features into node representations. Experiments on multiple representative time series tasks and public datasets validate the effectiveness of the proposed model.",
                                                        "keywords": [
                                                                "multivariate time series",
                                                                "hypergraph neural network",
                                                                "Transformer",
                                                                "multi-head self-attention",
                                                                "cross-variable relations"
                                                        ],
                                                        "language": "en",
                                                        "file_type": "TXT",
                                                        "metadata_extraction_status": "success"
                                                },
                                                "is_interdisciplinary": false,
                                                "classification_count": 1,
                                                "classifications": [
                                                        {
                                                                "order": 1,
                                                                "role": "main",
                                                                "clc_code": "TP181",
                                                                "label": "自动识别与检测",
                                                                "path": "工业技术 > 自动化技术、计算机技术 > 自动化基础理论 > 自动识别与检测",
                                                                "confidence": 0.96,
                                                                "evidence": [
                                                                        "The core contribution is a Transformer and hypergraph learning model.",
                                                                        "The work focuses on automated multivariate time-series representation and analysis."
                                                                ]
                                                        }
                                                ],
                                                "domain_labels": [
                                                        {
                                                                "label": "时间序列分析",
                                                                "confidence": 0.97,
                                                                "role": "primary"
                                                        }
                                                ]
                                        }
                                }
                        ],
                        "literature_distribution_analysis_report": {
                                "document_count": 2,
                                "classified_document_count": 2,
                                "clc_category_count": 2,
                                "domain_label_count": 2,
                                "by_clc_category": [
                                        {
                                                "clc_code": "TP181",
                                                "category_name": "自动识别与检测",
                                                "classification_path": "工业技术 > 自动化技术、计算机技术 > 自动化基础理论 > 自动识别与检测",
                                                "document_count": 2,
                                                "document_percentage": 100.0,
                                                "average_confidence": 0.925
                                        },
                                        {
                                                "clc_code": "Q811.4",
                                                "category_name": "生物信息论",
                                                "classification_path": "生物科学 > 生物工程学 > 生物工程基础理论 > 生物信息论",
                                                "document_count": 1,
                                                "document_percentage": 50.0,
                                                "average_confidence": 0.95
                                        }
                                ],
                                "by_domain_label": [
                                        {
                                                "label": "时间序列分析",
                                                "document_count": 1,
                                                "document_percentage": 50.0,
                                                "average_confidence": 0.97
                                        },
                                        {
                                                "label": "生物医学信息学",
                                                "document_count": 1,
                                                "document_percentage": 50.0,
                                                "average_confidence": 0.98
                                        }
                                ],
                                "domain_label_scope": "primary_only"
                        }
                },
                "meta": {
                        "max_concurrency": 3,
                        "elapsed_ms": 3072
                }
        },
        "hasLiteratureDistributionReport": true,
        "literatureDistributionModes": [
                "batch-text",
                "batch"
        ],
        "outputClassificationConfidence": false,
        "domainLabelPolicy": {
                "type": "primary_only",
                "max_labels_per_document": 1,
                "description": "每篇文献仅输出一个主领域标签；模型方法、算法结构和任务关键词不作为领域标签重复统计。"
        }
},
      "domain-classify": {
        "group": "自动分类工具",
        "title": "专业领域科技文献分类",
        "description": "用户先选择专业领域，再在该领域分类体系内进行多层级细分。输出严格包括多层级领域分类结果、分类置信度、领域标签和数据分布报告。",
        "features": "专业领域必选、领域匹配校验、一级二级三级分类、分类置信度计算、领域标签生成、10篇批量文本演示、二级类别统计、三级类别统计、单文本与批量文本、单文件与批量文件",
        "scenarios": "医学专题文献组织、材料科技分类、能源技术情报整理、领域知识库建设",
        "endpoint": "/api/v1/classify/domain/text",
        "textEndpoint": "/api/v1/classify/domain/text",
        "batchTextEndpoint": "/api/v1/classify/domain/texts",
        "fileEndpoint": "/api/v1/classify/domain/file",
        "batchFileEndpoint": "/api/v1/classify/domain/files",
        "languageCode": "auto",
        "languageName": "中英文",
        "documentType": "classification",
        "classificationScope": "domain",
        "requiresDomain": true,
        "documentTarget": "科技文献标题、摘要和关键词",
        "inputModes": [
                "text",
                "batch-text",
                "file",
                "batch"
        ],
        "modeLabels": {
                "text": "单文本",
                "batch-text": "批量文本",
                "file": "单文件",
                "batch": "批量文件"
        },
        "supportsFileUpload": true,
        "supportsBatchUpload": true,
        "acceptedFiles": [
                ".pdf",
                ".docx",
                ".txt"
        ],
        "maxFileSizeMB": 50,
        "maxBatchFiles": 20,
        "maxBatchTexts": 20,
        "domainOptions": [
                {
                        "code": "biomedical_informatics",
                        "name": "生物医学信息学"
                },
                {
                        "code": "medical_imaging",
                        "name": "医学影像"
                },
                {
                        "code": "materials_science",
                        "name": "材料科学"
                },
                {
                        "code": "new_energy",
                        "name": "新能源"
                },
                {
                        "code": "agricultural_science",
                        "name": "农业科技"
                },
                {
                        "code": "intelligent_manufacturing",
                        "name": "智能制造"
                },
                {
                        "code": "environmental_science",
                        "name": "环境科学"
                }
        ],
        "demoDomain": {
                "code": "biomedical_informatics",
                "name": "生物医学信息学"
        },
        "sampleFileName": "MOGONET_domain_classification.pdf",
        "sampleFileSize": "1.26 MB",
        "batchSampleFileNames": [
                "MOGONET_domain_classification.pdf",
                "Federated_Medical_Imaging_Classification.txt"
        ],
        "demoFileSizeBytes": 1322087,
        "demoFileSha256": "6f6f55bc4c5556fdbdad09d2d51ca05bd8da9adb8e992d5fb0b85cac0f28cda5",
        "demoFileFnv1a32": "15a27ddf",
        "demoFileFixtures": [
                {
                        "file_name": "MOGONET_domain_classification.pdf",
                        "size_bytes": 1322087,
                        "sha256": "6f6f55bc4c5556fdbdad09d2d51ca05bd8da9adb8e992d5fb0b85cac0f28cda5",
                        "fnv1a32": "15a27ddf",
                        "result": {
                                "code": 0,
                                "message": "success",
                                "data": {
                                        "tool": "专业领域科技文献分类",
                                        "input_type": "file",
                                        "document": {
                                                "title": "MOGONET integrates multi-omics data using graph convolutional networks allowing patient classification and biomarker identification",
                                                "abstract": "To fully utilize the advances in omics technologies and achieve a more comprehensive understanding of human diseases, novel computational methods are required for integrative analysis of multiple types of omics data. Here, we present a novel multi-omics integrative method named Multi-Omics Graph cOnvolutional NETworks (MOGONET) for biomedical classification. MOGONET jointly explores omics-specific learning and cross-omics correlation learning for effective multi-omics data classification. We demonstrate that MOGONET outperforms other state-of-the-art supervised multi-omics integrative analysis approaches in different biomedical classification applications using mRNA expression data, DNA methylation data, and microRNA expression data. Furthermore, MOGONET can identify important biomarkers from different omics data types related to the investigated biomedical problems.",
                                                "keywords": [
                                                        "multi-omics data integration",
                                                        "graph convolutional networks",
                                                        "patient classification",
                                                        "biomarker identification",
                                                        "cross-omics correlation"
                                                ],
                                                "language": "en",
                                                "file_type": "PDF",
                                                "metadata_extraction_status": "success"
                                        },
                                        "multilevel_classification_results": [
                                                {
                                                        "order": 1,
                                                        "role": "main",
                                                        "level_1": "生物医学信息学",
                                                        "level_2": "多组学数据分析",
                                                        "level_3": "多组学整合分类",
                                                        "classification_path": [
                                                                "生物医学信息学",
                                                                "多组学数据分析",
                                                                "多组学整合分类"
                                                        ],
                                                        "confidence": 0.97,
                                                        "evidence": [
                                                                "整合mRNA表达、DNA甲基化和miRNA表达数据",
                                                                "面向患者、肿瘤等级和癌症亚型分类"
                                                        ]
                                                },
                                                {
                                                        "order": 2,
                                                        "role": "secondary",
                                                        "level_1": "生物医学信息学",
                                                        "level_2": "生物标志物分析",
                                                        "level_3": "疾病相关生物标志物识别",
                                                        "classification_path": [
                                                                "生物医学信息学",
                                                                "生物标志物分析",
                                                                "疾病相关生物标志物识别"
                                                        ],
                                                        "confidence": 0.93,
                                                        "evidence": [
                                                                "识别不同组学数据中的重要特征",
                                                                "分析与具体疾病相关的潜在生物标志物"
                                                        ]
                                                }
                                        ],
                                        "classification_confidence": {
                                                "overall": 0.96,
                                                "level_1": 0.99,
                                                "level_2": 0.97,
                                                "level_3": 0.95
                                        },
                                        "domain_labels": [
                                                {
                                                        "label": "多组学数据分析",
                                                        "confidence": 0.98
                                                },
                                                {
                                                        "label": "患者分类",
                                                        "confidence": 0.96
                                                },
                                                {
                                                        "label": "生物标志物识别",
                                                        "confidence": 0.93
                                                },
                                                {
                                                        "label": "图神经网络",
                                                        "confidence": 0.89
                                                }
                                        ],
                                        "data_distribution_report": {
                                                "document_count": 1,
                                                "classified_document_count": 1,
                                                "classification_assignment_count": 2,
                                                "by_level_1": [
                                                        {
                                                                "category": "生物医学信息学",
                                                                "document_count": 1,
                                                                "percentage": 100.0
                                                        }
                                                ],
                                                "by_level_2": [
                                                        {
                                                                "category": "多组学数据分析",
                                                                "assignment_count": 1
                                                        },
                                                        {
                                                                "category": "生物标志物分析",
                                                                "assignment_count": 1
                                                        }
                                                ],
                                                "by_level_3": [
                                                        {
                                                                "category": "多组学整合分类",
                                                                "assignment_count": 1
                                                        },
                                                        {
                                                                "category": "疾病相关生物标志物识别",
                                                                "assignment_count": 1
                                                        }
                                                ]
                                        }
                                },
                                "meta": {
                                        "request_id": "req_domain_classify_file_202607190003",
                                        "selected_domain": {
                                                "code": "biomedical_informatics",
                                                "name": "生物医学信息学"
                                        },
                                        "elapsed_ms": 1770
                                }
                        }
                },
                {
                        "file_name": "Federated_Medical_Imaging_Classification.txt",
                        "size_bytes": 798,
                        "sha256": "f31aba4e320cb861933ff91ee245803a24b3799e343de4b7674596a85776961d",
                        "fnv1a32": "ab759b29",
                        "result": {
                                "code": 0,
                                "message": "success",
                                "data": {
                                        "tool": "专业领域科技文献分类",
                                        "input_type": "file",
                                        "document": {
                                                "title": "Privacy-Preserving Federated Learning for Multi-Center Medical Image Classification",
                                                "abstract": "Multi-center medical image analysis can improve model generalization, but privacy regulations and heterogeneous data distributions prevent centralized training. This study develops a federated learning framework that combines dynamic client weighting, prototype alignment, and consistency regularization for cross-institutional medical image classification. Experiments involving four medical centers show improved diagnostic classification accuracy and reduced performance variation among institutions while raw patient images remain local.",
                                                "keywords": [
                                                        "federated learning",
                                                        "medical image classification",
                                                        "privacy preservation",
                                                        "prototype alignment",
                                                        "multi-center learning"
                                                ],
                                                "language": "en"
                                        },
                                        "multilevel_classification_results": [
                                                {
                                                        "order": 1,
                                                        "role": "main",
                                                        "level_1": "生物医学信息学",
                                                        "level_2": "医学影像信息学",
                                                        "level_3": "多中心医学影像协同分类",
                                                        "classification_path": [
                                                                "生物医学信息学",
                                                                "医学影像信息学",
                                                                "多中心医学影像协同分类"
                                                        ],
                                                        "confidence": 0.96,
                                                        "evidence": [
                                                                "核心任务为多中心医学影像分类",
                                                                "采用联邦学习实现跨机构协同建模"
                                                        ]
                                                }
                                        ],
                                        "classification_confidence": {
                                                "overall": 0.95,
                                                "level_1": 0.98,
                                                "level_2": 0.96,
                                                "level_3": 0.95
                                        },
                                        "domain_labels": [
                                                {
                                                        "label": "医学影像分类",
                                                        "confidence": 0.97
                                                },
                                                {
                                                        "label": "联邦学习",
                                                        "confidence": 0.94
                                                },
                                                {
                                                        "label": "隐私保护",
                                                        "confidence": 0.92
                                                }
                                        ],
                                        "data_distribution_report": {
                                                "document_count": 1,
                                                "classified_document_count": 1,
                                                "classification_assignment_count": 1,
                                                "by_level_1": [
                                                        {
                                                                "category": "生物医学信息学",
                                                                "document_count": 1,
                                                                "percentage": 100.0
                                                        }
                                                ],
                                                "by_level_2": [
                                                        {
                                                                "category": "医学影像信息学",
                                                                "assignment_count": 1
                                                        }
                                                ],
                                                "by_level_3": [
                                                        {
                                                                "category": "多中心医学影像协同分类",
                                                                "assignment_count": 1
                                                        }
                                                ]
                                        }
                                },
                                "meta": {
                                        "request_id": "req_domain_classify_file_202607190004",
                                        "selected_domain": {
                                                "code": "biomedical_informatics",
                                                "name": "生物医学信息学"
                                        },
                                        "elapsed_ms": 1770
                                }
                        }
                }
        ],
        "fileProcessingHint": "上传后自动提取文献标题、摘要和关键词，校验与所选专业领域的匹配度，并完成领域内细分",
        "batchProcessingHint": "同一批次使用统一专业领域；系统逐文件校验领域匹配情况并返回领域内部分类结果。",
        "params": [
                [
                        "domain",
                        "string",
                        "required",
                        "专业领域代码，决定使用的领域分类规则与训练数据"
                ],
                [
                        "input_type",
                        "string",
                        "required",
                        "输入方式，取值为 text、texts、file 或 files"
                ],
                [
                        "title",
                        "string",
                        "conditional",
                        "当 input_type=text 时必填：科技文献标题"
                ],
                [
                        "abstract",
                        "string",
                        "conditional",
                        "当 input_type=text 时必填：科技文献摘要"
                ],
                [
                        "keywords",
                        "string[]",
                        "conditional",
                        "当 input_type=text 时必填：关键词列表"
                ],
                [
                        "texts",
                        "object[]",
                        "conditional",
                        "当 input_type=texts 时必填：每条包含 id、title、abstract 和 keywords"
                ],
                [
                        "file",
                        "file",
                        "conditional",
                        "当 input_type=file 时必填：一个科技文献文件"
                ],
                [
                        "files",
                        "file[]",
                        "conditional",
                        "当 input_type=files 时必填：同一领域的多个文献文件"
                ],
                [
                        "max_concurrency",
                        "integer",
                        "optional",
                        "批量任务并发数，默认3"
                ],
                [
                        "continue_on_error",
                        "boolean",
                        "optional",
                        "单条任务失败后是否继续处理，默认true"
                ]
        ],
        "payload": {
                "domain": "biomedical_informatics",
                "input_type": "text",
                "title": "MOGONET integrates multi-omics data using graph convolutional networks allowing patient classification and biomarker identification",
                "abstract": "To fully utilize the advances in omics technologies and achieve a more comprehensive understanding of human diseases, novel computational methods are required for integrative analysis of multiple types of omics data. Here, we present a novel multi-omics integrative method named Multi-Omics Graph cOnvolutional NETworks (MOGONET) for biomedical classification. MOGONET jointly explores omics-specific learning and cross-omics correlation learning for effective multi-omics data classification. We demonstrate that MOGONET outperforms other state-of-the-art supervised multi-omics integrative analysis approaches in different biomedical classification applications using mRNA expression data, DNA methylation data, and microRNA expression data. Furthermore, MOGONET can identify important biomarkers from different omics data types related to the investigated biomedical problems.",
                "keywords": [
                        "multi-omics data integration",
                        "graph convolutional networks",
                        "patient classification",
                        "biomarker identification",
                        "cross-omics correlation"
                ]
        },
        "demoClassificationInput": {
                "title": "MOGONET integrates multi-omics data using graph convolutional networks allowing patient classification and biomarker identification",
                "abstract": "To fully utilize the advances in omics technologies and achieve a more comprehensive understanding of human diseases, novel computational methods are required for integrative analysis of multiple types of omics data. Here, we present a novel multi-omics integrative method named Multi-Omics Graph cOnvolutional NETworks (MOGONET) for biomedical classification. MOGONET jointly explores omics-specific learning and cross-omics correlation learning for effective multi-omics data classification. We demonstrate that MOGONET outperforms other state-of-the-art supervised multi-omics integrative analysis approaches in different biomedical classification applications using mRNA expression data, DNA methylation data, and microRNA expression data. Furthermore, MOGONET can identify important biomarkers from different omics data types related to the investigated biomedical problems.",
                "keywords": [
                        "multi-omics data integration",
                        "graph convolutional networks",
                        "patient classification",
                        "biomarker identification",
                        "cross-omics correlation"
                ]
        },
        "demoBatchClassificationInputs": [
                {
                        "id": "text1",
                        "title": "MOGONET integrates multi-omics data using graph convolutional networks allowing patient classification and biomarker identification",
                        "abstract": "This study proposes MOGONET for integrative analysis of mRNA expression, DNA methylation, and microRNA expression data. The method combines omics-specific graph convolutional networks with cross-omics correlation learning to improve patient classification and biomarker identification.",
                        "keywords": [
                                "multi-omics integration",
                                "graph convolutional network",
                                "patient classification",
                                "biomarker identification"
                        ]
                },
                {
                        "id": "text2",
                        "title": "A Transformer Framework for Cross-Omics Cancer Subtype Classification",
                        "abstract": "A cross-omics Transformer is developed to align gene expression, DNA methylation, and copy-number variation features for cancer subtype classification. Experiments on multi-center cohorts show that joint representation learning improves classification accuracy and robustness.",
                        "keywords": [
                                "cross-omics learning",
                                "Transformer",
                                "cancer subtype classification",
                                "multi-omics representation"
                        ]
                },
                {
                        "id": "text3",
                        "title": "Multi-Omics Biomarker Discovery for Early Alzheimer’s Disease Screening",
                        "abstract": "The study integrates transcriptomic, proteomic, and metabolomic profiles to identify biomarkers for early Alzheimer’s disease screening. A sparse feature selection model ranks candidate markers and validates their predictive value across independent cohorts.",
                        "keywords": [
                                "biomarker discovery",
                                "Alzheimer's disease",
                                "multi-omics",
                                "feature selection"
                        ]
                },
                {
                        "id": "text4",
                        "title": "Deep Learning-Based Classification of Pulmonary Nodules in Chest CT",
                        "abstract": "A three-dimensional convolutional neural network is proposed to classify benign and malignant pulmonary nodules from chest CT scans. Multi-scale feature fusion and attention-guided pooling improve diagnostic classification performance on two public datasets.",
                        "keywords": [
                                "chest CT",
                                "pulmonary nodule",
                                "medical image classification",
                                "deep learning"
                        ]
                },
                {
                        "id": "text5",
                        "title": "Boundary-Aware Network for Multi-Organ Segmentation in Abdominal CT",
                        "abstract": "This work introduces a boundary-aware segmentation network for delineating multiple abdominal organs in CT images. The model combines hierarchical features, contour supervision, and uncertainty weighting to improve segmentation accuracy for small and low-contrast organs.",
                        "keywords": [
                                "medical image segmentation",
                                "abdominal CT",
                                "boundary supervision",
                                "multi-organ segmentation"
                        ]
                },
                {
                        "id": "text6",
                        "title": "Weakly Supervised Lesion Detection in Digital Pathology Images",
                        "abstract": "A weakly supervised detection method is proposed for locating tumor lesions in gigapixel pathology images. The method uses multiple-instance learning and regional consistency constraints to identify suspicious tissue areas using only slide-level diagnostic labels.",
                        "keywords": [
                                "lesion detection",
                                "digital pathology",
                                "weak supervision",
                                "multiple-instance learning"
                        ]
                },
                {
                        "id": "text7",
                        "title": "Knowledge Graph-Based Clinical Decision Support for Rare Disease Diagnosis",
                        "abstract": "A clinical knowledge graph integrating symptoms, diseases, genes, examinations, and treatments is constructed for rare disease diagnosis. Graph reasoning ranks diagnostic candidates and provides traceable evidence paths to support clinicians in differential diagnosis.",
                        "keywords": [
                                "clinical decision support",
                                "rare disease diagnosis",
                                "knowledge graph",
                                "graph reasoning"
                        ]
                },
                {
                        "id": "text8",
                        "title": "Early Sepsis Risk Prediction from Longitudinal Electronic Health Records",
                        "abstract": "A temporal prediction model is developed to estimate sepsis risk six hours before clinical onset using longitudinal electronic health records. The model combines irregular time-series encoding, missing-value modeling, and calibrated risk estimation to support early clinical intervention.",
                        "keywords": [
                                "sepsis",
                                "risk prediction",
                                "electronic health records",
                                "temporal modeling"
                        ]
                },
                {
                        "id": "text9",
                        "title": "Construction of a Biomedical Knowledge Graph for Drug Repurposing",
                        "abstract": "This study constructs a biomedical knowledge graph from drugs, diseases, genes, pathways, and clinical trials. Entity normalization and relation fusion are used to integrate heterogeneous evidence, enabling graph-based candidate ranking for drug repurposing.",
                        "keywords": [
                                "biomedical knowledge graph",
                                "drug repurposing",
                                "entity normalization",
                                "relation fusion"
                        ]
                },
                {
                        "id": "text10",
                        "title": "Biomedical Entity and Relation Extraction from Clinical Research Articles",
                        "abstract": "A joint information extraction model identifies diseases, drugs, genes, and treatment relations from clinical research articles. Domain-adaptive language modeling and span-level interaction improve entity recognition and relation extraction under limited annotated data.",
                        "keywords": [
                                "biomedical entity recognition",
                                "relation extraction",
                                "clinical text mining",
                                "domain adaptation"
                        ]
                }
        ],
        "demoBatchClassificationResults": [
                {
                        "id": "text1",
                        "title": "MOGONET integrates multi-omics data using graph convolutional networks allowing patient classification and biomarker identification",
                        "abstract": "This study proposes MOGONET for integrative analysis of mRNA expression, DNA methylation, and microRNA expression data. The method combines omics-specific graph convolutional networks with cross-omics correlation learning to improve patient classification and biomarker identification.",
                        "keywords": [
                                "multi-omics integration",
                                "graph convolutional network",
                                "patient classification",
                                "biomarker identification"
                        ],
                        "language": "en",
                        "multilevel_classification_results": [
                                {
                                        "order": 1,
                                        "role": "main",
                                        "level_1": "生物医学信息学",
                                        "level_2": "多组学数据分析",
                                        "level_3": "多组学整合分类",
                                        "classification_path": [
                                                "生物医学信息学",
                                                "多组学数据分析",
                                                "多组学整合分类"
                                        ],
                                        "confidence": 0.97,
                                        "evidence": [
                                                "文献核心研究任务与“多组学整合分类”直接对应",
                                                "研究对象和技术内容属于“多组学数据分析”"
                                        ]
                                }
                        ],
                        "classification_confidence": {
                                "overall": 0.97,
                                "level_1": 0.99,
                                "level_2": 0.98,
                                "level_3": 0.97
                        },
                        "domain_labels": [
                                {
                                        "label": "多组学数据分析",
                                        "confidence": 0.97
                                },
                                {
                                        "label": "患者分类",
                                        "confidence": 0.94
                                },
                                {
                                        "label": "图神经网络",
                                        "confidence": 0.91
                                }
                        ],
                        "data_distribution_report": {
                                "document_count": 1,
                                "classified_document_count": 1,
                                "classification_assignment_count": 1,
                                "by_level_2": [
                                        {
                                                "category": "多组学数据分析",
                                                "document_count": 1,
                                                "percentage": 100.0
                                        }
                                ],
                                "by_level_3": [
                                        {
                                                "category": "多组学整合分类",
                                                "document_count": 1,
                                                "percentage": 100.0
                                        }
                                ]
                        }
                },
                {
                        "id": "text2",
                        "title": "A Transformer Framework for Cross-Omics Cancer Subtype Classification",
                        "abstract": "A cross-omics Transformer is developed to align gene expression, DNA methylation, and copy-number variation features for cancer subtype classification. Experiments on multi-center cohorts show that joint representation learning improves classification accuracy and robustness.",
                        "keywords": [
                                "cross-omics learning",
                                "Transformer",
                                "cancer subtype classification",
                                "multi-omics representation"
                        ],
                        "language": "en",
                        "multilevel_classification_results": [
                                {
                                        "order": 1,
                                        "role": "main",
                                        "level_1": "生物医学信息学",
                                        "level_2": "多组学数据分析",
                                        "level_3": "多组学整合分类",
                                        "classification_path": [
                                                "生物医学信息学",
                                                "多组学数据分析",
                                                "多组学整合分类"
                                        ],
                                        "confidence": 0.95,
                                        "evidence": [
                                                "文献核心研究任务与“多组学整合分类”直接对应",
                                                "研究对象和技术内容属于“多组学数据分析”"
                                        ]
                                }
                        ],
                        "classification_confidence": {
                                "overall": 0.95,
                                "level_1": 0.98,
                                "level_2": 0.96,
                                "level_3": 0.95
                        },
                        "domain_labels": [
                                {
                                        "label": "跨组学学习",
                                        "confidence": 0.95
                                },
                                {
                                        "label": "癌症亚型分类",
                                        "confidence": 0.92
                                },
                                {
                                        "label": "Transformer",
                                        "confidence": 0.89
                                }
                        ],
                        "data_distribution_report": {
                                "document_count": 1,
                                "classified_document_count": 1,
                                "classification_assignment_count": 1,
                                "by_level_2": [
                                        {
                                                "category": "多组学数据分析",
                                                "document_count": 1,
                                                "percentage": 100.0
                                        }
                                ],
                                "by_level_3": [
                                        {
                                                "category": "多组学整合分类",
                                                "document_count": 1,
                                                "percentage": 100.0
                                        }
                                ]
                        }
                },
                {
                        "id": "text3",
                        "title": "Multi-Omics Biomarker Discovery for Early Alzheimer’s Disease Screening",
                        "abstract": "The study integrates transcriptomic, proteomic, and metabolomic profiles to identify biomarkers for early Alzheimer’s disease screening. A sparse feature selection model ranks candidate markers and validates their predictive value across independent cohorts.",
                        "keywords": [
                                "biomarker discovery",
                                "Alzheimer's disease",
                                "multi-omics",
                                "feature selection"
                        ],
                        "language": "en",
                        "multilevel_classification_results": [
                                {
                                        "order": 1,
                                        "role": "main",
                                        "level_1": "生物医学信息学",
                                        "level_2": "多组学数据分析",
                                        "level_3": "生物标志物识别",
                                        "classification_path": [
                                                "生物医学信息学",
                                                "多组学数据分析",
                                                "生物标志物识别"
                                        ],
                                        "confidence": 0.94,
                                        "evidence": [
                                                "文献核心研究任务与“生物标志物识别”直接对应",
                                                "研究对象和技术内容属于“多组学数据分析”"
                                        ]
                                }
                        ],
                        "classification_confidence": {
                                "overall": 0.94,
                                "level_1": 0.97,
                                "level_2": 0.95,
                                "level_3": 0.94
                        },
                        "domain_labels": [
                                {
                                        "label": "生物标志物识别",
                                        "confidence": 0.94
                                },
                                {
                                        "label": "阿尔茨海默病",
                                        "confidence": 0.91
                                },
                                {
                                        "label": "特征选择",
                                        "confidence": 0.88
                                }
                        ],
                        "data_distribution_report": {
                                "document_count": 1,
                                "classified_document_count": 1,
                                "classification_assignment_count": 1,
                                "by_level_2": [
                                        {
                                                "category": "多组学数据分析",
                                                "document_count": 1,
                                                "percentage": 100.0
                                        }
                                ],
                                "by_level_3": [
                                        {
                                                "category": "生物标志物识别",
                                                "document_count": 1,
                                                "percentage": 100.0
                                        }
                                ]
                        }
                },
                {
                        "id": "text4",
                        "title": "Deep Learning-Based Classification of Pulmonary Nodules in Chest CT",
                        "abstract": "A three-dimensional convolutional neural network is proposed to classify benign and malignant pulmonary nodules from chest CT scans. Multi-scale feature fusion and attention-guided pooling improve diagnostic classification performance on two public datasets.",
                        "keywords": [
                                "chest CT",
                                "pulmonary nodule",
                                "medical image classification",
                                "deep learning"
                        ],
                        "language": "en",
                        "multilevel_classification_results": [
                                {
                                        "order": 1,
                                        "role": "main",
                                        "level_1": "生物医学信息学",
                                        "level_2": "医学影像信息学",
                                        "level_3": "医学图像分类",
                                        "classification_path": [
                                                "生物医学信息学",
                                                "医学影像信息学",
                                                "医学图像分类"
                                        ],
                                        "confidence": 0.96,
                                        "evidence": [
                                                "文献核心研究任务与“医学图像分类”直接对应",
                                                "研究对象和技术内容属于“医学影像信息学”"
                                        ]
                                }
                        ],
                        "classification_confidence": {
                                "overall": 0.96,
                                "level_1": 0.99,
                                "level_2": 0.97,
                                "level_3": 0.96
                        },
                        "domain_labels": [
                                {
                                        "label": "医学图像分类",
                                        "confidence": 0.96
                                },
                                {
                                        "label": "肺结节",
                                        "confidence": 0.93
                                },
                                {
                                        "label": "CT影像",
                                        "confidence": 0.9
                                }
                        ],
                        "data_distribution_report": {
                                "document_count": 1,
                                "classified_document_count": 1,
                                "classification_assignment_count": 1,
                                "by_level_2": [
                                        {
                                                "category": "医学影像信息学",
                                                "document_count": 1,
                                                "percentage": 100.0
                                        }
                                ],
                                "by_level_3": [
                                        {
                                                "category": "医学图像分类",
                                                "document_count": 1,
                                                "percentage": 100.0
                                        }
                                ]
                        }
                },
                {
                        "id": "text5",
                        "title": "Boundary-Aware Network for Multi-Organ Segmentation in Abdominal CT",
                        "abstract": "This work introduces a boundary-aware segmentation network for delineating multiple abdominal organs in CT images. The model combines hierarchical features, contour supervision, and uncertainty weighting to improve segmentation accuracy for small and low-contrast organs.",
                        "keywords": [
                                "medical image segmentation",
                                "abdominal CT",
                                "boundary supervision",
                                "multi-organ segmentation"
                        ],
                        "language": "en",
                        "multilevel_classification_results": [
                                {
                                        "order": 1,
                                        "role": "main",
                                        "level_1": "生物医学信息学",
                                        "level_2": "医学影像信息学",
                                        "level_3": "医学图像分割",
                                        "classification_path": [
                                                "生物医学信息学",
                                                "医学影像信息学",
                                                "医学图像分割"
                                        ],
                                        "confidence": 0.95,
                                        "evidence": [
                                                "文献核心研究任务与“医学图像分割”直接对应",
                                                "研究对象和技术内容属于“医学影像信息学”"
                                        ]
                                }
                        ],
                        "classification_confidence": {
                                "overall": 0.95,
                                "level_1": 0.98,
                                "level_2": 0.96,
                                "level_3": 0.95
                        },
                        "domain_labels": [
                                {
                                        "label": "医学图像分割",
                                        "confidence": 0.95
                                },
                                {
                                        "label": "腹部CT",
                                        "confidence": 0.92
                                },
                                {
                                        "label": "边界监督",
                                        "confidence": 0.89
                                }
                        ],
                        "data_distribution_report": {
                                "document_count": 1,
                                "classified_document_count": 1,
                                "classification_assignment_count": 1,
                                "by_level_2": [
                                        {
                                                "category": "医学影像信息学",
                                                "document_count": 1,
                                                "percentage": 100.0
                                        }
                                ],
                                "by_level_3": [
                                        {
                                                "category": "医学图像分割",
                                                "document_count": 1,
                                                "percentage": 100.0
                                        }
                                ]
                        }
                },
                {
                        "id": "text6",
                        "title": "Weakly Supervised Lesion Detection in Digital Pathology Images",
                        "abstract": "A weakly supervised detection method is proposed for locating tumor lesions in gigapixel pathology images. The method uses multiple-instance learning and regional consistency constraints to identify suspicious tissue areas using only slide-level diagnostic labels.",
                        "keywords": [
                                "lesion detection",
                                "digital pathology",
                                "weak supervision",
                                "multiple-instance learning"
                        ],
                        "language": "en",
                        "multilevel_classification_results": [
                                {
                                        "order": 1,
                                        "role": "main",
                                        "level_1": "生物医学信息学",
                                        "level_2": "医学影像信息学",
                                        "level_3": "病灶检测",
                                        "classification_path": [
                                                "生物医学信息学",
                                                "医学影像信息学",
                                                "病灶检测"
                                        ],
                                        "confidence": 0.93,
                                        "evidence": [
                                                "文献核心研究任务与“病灶检测”直接对应",
                                                "研究对象和技术内容属于“医学影像信息学”"
                                        ]
                                }
                        ],
                        "classification_confidence": {
                                "overall": 0.93,
                                "level_1": 0.9600000000000001,
                                "level_2": 0.9400000000000001,
                                "level_3": 0.93
                        },
                        "domain_labels": [
                                {
                                        "label": "病灶检测",
                                        "confidence": 0.93
                                },
                                {
                                        "label": "数字病理",
                                        "confidence": 0.9
                                },
                                {
                                        "label": "弱监督学习",
                                        "confidence": 0.87
                                }
                        ],
                        "data_distribution_report": {
                                "document_count": 1,
                                "classified_document_count": 1,
                                "classification_assignment_count": 1,
                                "by_level_2": [
                                        {
                                                "category": "医学影像信息学",
                                                "document_count": 1,
                                                "percentage": 100.0
                                        }
                                ],
                                "by_level_3": [
                                        {
                                                "category": "病灶检测",
                                                "document_count": 1,
                                                "percentage": 100.0
                                        }
                                ]
                        }
                },
                {
                        "id": "text7",
                        "title": "Knowledge Graph-Based Clinical Decision Support for Rare Disease Diagnosis",
                        "abstract": "A clinical knowledge graph integrating symptoms, diseases, genes, examinations, and treatments is constructed for rare disease diagnosis. Graph reasoning ranks diagnostic candidates and provides traceable evidence paths to support clinicians in differential diagnosis.",
                        "keywords": [
                                "clinical decision support",
                                "rare disease diagnosis",
                                "knowledge graph",
                                "graph reasoning"
                        ],
                        "language": "en",
                        "multilevel_classification_results": [
                                {
                                        "order": 1,
                                        "role": "main",
                                        "level_1": "生物医学信息学",
                                        "level_2": "临床决策支持",
                                        "level_3": "辅助诊断",
                                        "classification_path": [
                                                "生物医学信息学",
                                                "临床决策支持",
                                                "辅助诊断"
                                        ],
                                        "confidence": 0.95,
                                        "evidence": [
                                                "文献核心研究任务与“辅助诊断”直接对应",
                                                "研究对象和技术内容属于“临床决策支持”"
                                        ]
                                }
                        ],
                        "classification_confidence": {
                                "overall": 0.95,
                                "level_1": 0.98,
                                "level_2": 0.96,
                                "level_3": 0.95
                        },
                        "domain_labels": [
                                {
                                        "label": "辅助诊断",
                                        "confidence": 0.95
                                },
                                {
                                        "label": "罕见病",
                                        "confidence": 0.92
                                },
                                {
                                        "label": "临床知识图谱",
                                        "confidence": 0.89
                                }
                        ],
                        "data_distribution_report": {
                                "document_count": 1,
                                "classified_document_count": 1,
                                "classification_assignment_count": 1,
                                "by_level_2": [
                                        {
                                                "category": "临床决策支持",
                                                "document_count": 1,
                                                "percentage": 100.0
                                        }
                                ],
                                "by_level_3": [
                                        {
                                                "category": "辅助诊断",
                                                "document_count": 1,
                                                "percentage": 100.0
                                        }
                                ]
                        }
                },
                {
                        "id": "text8",
                        "title": "Early Sepsis Risk Prediction from Longitudinal Electronic Health Records",
                        "abstract": "A temporal prediction model is developed to estimate sepsis risk six hours before clinical onset using longitudinal electronic health records. The model combines irregular time-series encoding, missing-value modeling, and calibrated risk estimation to support early clinical intervention.",
                        "keywords": [
                                "sepsis",
                                "risk prediction",
                                "electronic health records",
                                "temporal modeling"
                        ],
                        "language": "en",
                        "multilevel_classification_results": [
                                {
                                        "order": 1,
                                        "role": "main",
                                        "level_1": "生物医学信息学",
                                        "level_2": "临床决策支持",
                                        "level_3": "临床风险预测",
                                        "classification_path": [
                                                "生物医学信息学",
                                                "临床决策支持",
                                                "临床风险预测"
                                        ],
                                        "confidence": 0.94,
                                        "evidence": [
                                                "文献核心研究任务与“临床风险预测”直接对应",
                                                "研究对象和技术内容属于“临床决策支持”"
                                        ]
                                }
                        ],
                        "classification_confidence": {
                                "overall": 0.94,
                                "level_1": 0.97,
                                "level_2": 0.95,
                                "level_3": 0.94
                        },
                        "domain_labels": [
                                {
                                        "label": "临床风险预测",
                                        "confidence": 0.94
                                },
                                {
                                        "label": "脓毒症",
                                        "confidence": 0.91
                                },
                                {
                                        "label": "电子健康记录",
                                        "confidence": 0.88
                                }
                        ],
                        "data_distribution_report": {
                                "document_count": 1,
                                "classified_document_count": 1,
                                "classification_assignment_count": 1,
                                "by_level_2": [
                                        {
                                                "category": "临床决策支持",
                                                "document_count": 1,
                                                "percentage": 100.0
                                        }
                                ],
                                "by_level_3": [
                                        {
                                                "category": "临床风险预测",
                                                "document_count": 1,
                                                "percentage": 100.0
                                        }
                                ]
                        }
                },
                {
                        "id": "text9",
                        "title": "Construction of a Biomedical Knowledge Graph for Drug Repurposing",
                        "abstract": "This study constructs a biomedical knowledge graph from drugs, diseases, genes, pathways, and clinical trials. Entity normalization and relation fusion are used to integrate heterogeneous evidence, enabling graph-based candidate ranking for drug repurposing.",
                        "keywords": [
                                "biomedical knowledge graph",
                                "drug repurposing",
                                "entity normalization",
                                "relation fusion"
                        ],
                        "language": "en",
                        "multilevel_classification_results": [
                                {
                                        "order": 1,
                                        "role": "main",
                                        "level_1": "生物医学信息学",
                                        "level_2": "医学知识组织",
                                        "level_3": "医学知识图谱构建",
                                        "classification_path": [
                                                "生物医学信息学",
                                                "医学知识组织",
                                                "医学知识图谱构建"
                                        ],
                                        "confidence": 0.96,
                                        "evidence": [
                                                "文献核心研究任务与“医学知识图谱构建”直接对应",
                                                "研究对象和技术内容属于“医学知识组织”"
                                        ]
                                }
                        ],
                        "classification_confidence": {
                                "overall": 0.96,
                                "level_1": 0.99,
                                "level_2": 0.97,
                                "level_3": 0.96
                        },
                        "domain_labels": [
                                {
                                        "label": "医学知识图谱",
                                        "confidence": 0.96
                                },
                                {
                                        "label": "药物重定位",
                                        "confidence": 0.93
                                },
                                {
                                        "label": "异构数据融合",
                                        "confidence": 0.9
                                }
                        ],
                        "data_distribution_report": {
                                "document_count": 1,
                                "classified_document_count": 1,
                                "classification_assignment_count": 1,
                                "by_level_2": [
                                        {
                                                "category": "医学知识组织",
                                                "document_count": 1,
                                                "percentage": 100.0
                                        }
                                ],
                                "by_level_3": [
                                        {
                                                "category": "医学知识图谱构建",
                                                "document_count": 1,
                                                "percentage": 100.0
                                        }
                                ]
                        }
                },
                {
                        "id": "text10",
                        "title": "Biomedical Entity and Relation Extraction from Clinical Research Articles",
                        "abstract": "A joint information extraction model identifies diseases, drugs, genes, and treatment relations from clinical research articles. Domain-adaptive language modeling and span-level interaction improve entity recognition and relation extraction under limited annotated data.",
                        "keywords": [
                                "biomedical entity recognition",
                                "relation extraction",
                                "clinical text mining",
                                "domain adaptation"
                        ],
                        "language": "en",
                        "multilevel_classification_results": [
                                {
                                        "order": 1,
                                        "role": "main",
                                        "level_1": "生物医学信息学",
                                        "level_2": "医学知识组织",
                                        "level_3": "生物医学实体关系抽取",
                                        "classification_path": [
                                                "生物医学信息学",
                                                "医学知识组织",
                                                "生物医学实体关系抽取"
                                        ],
                                        "confidence": 0.93,
                                        "evidence": [
                                                "文献核心研究任务与“生物医学实体关系抽取”直接对应",
                                                "研究对象和技术内容属于“医学知识组织”"
                                        ]
                                }
                        ],
                        "classification_confidence": {
                                "overall": 0.93,
                                "level_1": 0.9600000000000001,
                                "level_2": 0.9400000000000001,
                                "level_3": 0.93
                        },
                        "domain_labels": [
                                {
                                        "label": "生物医学实体识别",
                                        "confidence": 0.93
                                },
                                {
                                        "label": "关系抽取",
                                        "confidence": 0.9
                                },
                                {
                                        "label": "临床文本挖掘",
                                        "confidence": 0.87
                                }
                        ],
                        "data_distribution_report": {
                                "document_count": 1,
                                "classified_document_count": 1,
                                "classification_assignment_count": 1,
                                "by_level_2": [
                                        {
                                                "category": "医学知识组织",
                                                "document_count": 1,
                                                "percentage": 100.0
                                        }
                                ],
                                "by_level_3": [
                                        {
                                                "category": "生物医学实体关系抽取",
                                                "document_count": 1,
                                                "percentage": 100.0
                                        }
                                ]
                        }
                }
        ],
        "demoTextResult": {
                "code": 0,
                "message": "success",
                "data": {
                        "tool": "专业领域科技文献分类",
                        "input_type": "text",
                        "document": {
                                "title": "MOGONET integrates multi-omics data using graph convolutional networks allowing patient classification and biomarker identification",
                                "abstract": "To fully utilize the advances in omics technologies and achieve a more comprehensive understanding of human diseases, novel computational methods are required for integrative analysis of multiple types of omics data. Here, we present a novel multi-omics integrative method named Multi-Omics Graph cOnvolutional NETworks (MOGONET) for biomedical classification. MOGONET jointly explores omics-specific learning and cross-omics correlation learning for effective multi-omics data classification. We demonstrate that MOGONET outperforms other state-of-the-art supervised multi-omics integrative analysis approaches in different biomedical classification applications using mRNA expression data, DNA methylation data, and microRNA expression data. Furthermore, MOGONET can identify important biomarkers from different omics data types related to the investigated biomedical problems.",
                                "keywords": [
                                        "multi-omics data integration",
                                        "graph convolutional networks",
                                        "patient classification",
                                        "biomarker identification",
                                        "cross-omics correlation"
                                ],
                                "language": "en"
                        },
                        "multilevel_classification_results": [
                                {
                                        "order": 1,
                                        "role": "main",
                                        "level_1": "生物医学信息学",
                                        "level_2": "多组学数据分析",
                                        "level_3": "多组学整合分类",
                                        "classification_path": [
                                                "生物医学信息学",
                                                "多组学数据分析",
                                                "多组学整合分类"
                                        ],
                                        "confidence": 0.97,
                                        "evidence": [
                                                "整合mRNA表达、DNA甲基化和miRNA表达数据",
                                                "面向患者、肿瘤等级和癌症亚型分类"
                                        ]
                                },
                                {
                                        "order": 2,
                                        "role": "secondary",
                                        "level_1": "生物医学信息学",
                                        "level_2": "生物标志物分析",
                                        "level_3": "疾病相关生物标志物识别",
                                        "classification_path": [
                                                "生物医学信息学",
                                                "生物标志物分析",
                                                "疾病相关生物标志物识别"
                                        ],
                                        "confidence": 0.93,
                                        "evidence": [
                                                "识别不同组学数据中的重要特征",
                                                "分析与具体疾病相关的潜在生物标志物"
                                        ]
                                }
                        ],
                        "classification_confidence": {
                                "overall": 0.96,
                                "level_1": 0.99,
                                "level_2": 0.97,
                                "level_3": 0.95
                        },
                        "domain_labels": [
                                {
                                        "label": "多组学数据分析",
                                        "confidence": 0.98
                                },
                                {
                                        "label": "患者分类",
                                        "confidence": 0.96
                                },
                                {
                                        "label": "生物标志物识别",
                                        "confidence": 0.93
                                },
                                {
                                        "label": "图神经网络",
                                        "confidence": 0.89
                                }
                        ],
                        "data_distribution_report": {
                                "document_count": 1,
                                "classified_document_count": 1,
                                "classification_assignment_count": 2,
                                "by_level_1": [
                                        {
                                                "category": "生物医学信息学",
                                                "document_count": 1,
                                                "percentage": 100.0
                                        }
                                ],
                                "by_level_2": [
                                        {
                                                "category": "多组学数据分析",
                                                "assignment_count": 1
                                        },
                                        {
                                                "category": "生物标志物分析",
                                                "assignment_count": 1
                                        }
                                ],
                                "by_level_3": [
                                        {
                                                "category": "多组学整合分类",
                                                "assignment_count": 1
                                        },
                                        {
                                                "category": "疾病相关生物标志物识别",
                                                "assignment_count": 1
                                        }
                                ]
                        }
                },
                "meta": {
                        "request_id": "req_domain_classify_text_202607190002",
                        "selected_domain": {
                                "code": "biomedical_informatics",
                                "name": "生物医学信息学"
                        },
                        "elapsed_ms": 1190
                }
        },
        "demoBatchTextResult": {
                "code": 0,
                "message": "batch_completed",
                "data": {
                        "batch_id": "batch_domain_classify_text_202607190010",
                        "input_type": "texts",
                        "total": 10,
                        "success_count": 10,
                        "failed_count": 0,
                        "results": [
                                {
                                        "index": 1,
                                        "input_id": "text1",
                                        "status": "success",
                                        "code": 0,
                                        "result": {
                                                "tool": "专业领域科技文献分类",
                                                "input_type": "text",
                                                "document": {
                                                        "title": "MOGONET integrates multi-omics data using graph convolutional networks allowing patient classification and biomarker identification",
                                                        "abstract": "This study proposes MOGONET for integrative analysis of mRNA expression, DNA methylation, and microRNA expression data. The method combines omics-specific graph convolutional networks with cross-omics correlation learning to improve patient classification and biomarker identification.",
                                                        "keywords": [
                                                                "multi-omics integration",
                                                                "graph convolutional network",
                                                                "patient classification",
                                                                "biomarker identification"
                                                        ],
                                                        "language": "en"
                                                },
                                                "multilevel_classification_results": [
                                                        {
                                                                "order": 1,
                                                                "role": "main",
                                                                "level_1": "生物医学信息学",
                                                                "level_2": "多组学数据分析",
                                                                "level_3": "多组学整合分类",
                                                                "classification_path": [
                                                                        "生物医学信息学",
                                                                        "多组学数据分析",
                                                                        "多组学整合分类"
                                                                ],
                                                                "confidence": 0.97,
                                                                "evidence": [
                                                                        "文献核心研究任务与“多组学整合分类”直接对应",
                                                                        "研究对象和技术内容属于“多组学数据分析”"
                                                                ]
                                                        }
                                                ],
                                                "classification_confidence": {
                                                        "overall": 0.97,
                                                        "level_1": 0.99,
                                                        "level_2": 0.98,
                                                        "level_3": 0.97
                                                },
                                                "domain_labels": [
                                                        {
                                                                "label": "多组学数据分析",
                                                                "confidence": 0.97
                                                        },
                                                        {
                                                                "label": "患者分类",
                                                                "confidence": 0.94
                                                        },
                                                        {
                                                                "label": "图神经网络",
                                                                "confidence": 0.91
                                                        }
                                                ],
                                                "data_distribution_report": {
                                                        "document_count": 1,
                                                        "classified_document_count": 1,
                                                        "classification_assignment_count": 1,
                                                        "by_level_2": [
                                                                {
                                                                        "category": "多组学数据分析",
                                                                        "document_count": 1,
                                                                        "percentage": 100.0
                                                                }
                                                        ],
                                                        "by_level_3": [
                                                                {
                                                                        "category": "多组学整合分类",
                                                                        "document_count": 1,
                                                                        "percentage": 100.0
                                                                }
                                                        ]
                                                }
                                        }
                                },
                                {
                                        "index": 2,
                                        "input_id": "text2",
                                        "status": "success",
                                        "code": 0,
                                        "result": {
                                                "tool": "专业领域科技文献分类",
                                                "input_type": "text",
                                                "document": {
                                                        "title": "A Transformer Framework for Cross-Omics Cancer Subtype Classification",
                                                        "abstract": "A cross-omics Transformer is developed to align gene expression, DNA methylation, and copy-number variation features for cancer subtype classification. Experiments on multi-center cohorts show that joint representation learning improves classification accuracy and robustness.",
                                                        "keywords": [
                                                                "cross-omics learning",
                                                                "Transformer",
                                                                "cancer subtype classification",
                                                                "multi-omics representation"
                                                        ],
                                                        "language": "en"
                                                },
                                                "multilevel_classification_results": [
                                                        {
                                                                "order": 1,
                                                                "role": "main",
                                                                "level_1": "生物医学信息学",
                                                                "level_2": "多组学数据分析",
                                                                "level_3": "多组学整合分类",
                                                                "classification_path": [
                                                                        "生物医学信息学",
                                                                        "多组学数据分析",
                                                                        "多组学整合分类"
                                                                ],
                                                                "confidence": 0.95,
                                                                "evidence": [
                                                                        "文献核心研究任务与“多组学整合分类”直接对应",
                                                                        "研究对象和技术内容属于“多组学数据分析”"
                                                                ]
                                                        }
                                                ],
                                                "classification_confidence": {
                                                        "overall": 0.95,
                                                        "level_1": 0.98,
                                                        "level_2": 0.96,
                                                        "level_3": 0.95
                                                },
                                                "domain_labels": [
                                                        {
                                                                "label": "跨组学学习",
                                                                "confidence": 0.95
                                                        },
                                                        {
                                                                "label": "癌症亚型分类",
                                                                "confidence": 0.92
                                                        },
                                                        {
                                                                "label": "Transformer",
                                                                "confidence": 0.89
                                                        }
                                                ],
                                                "data_distribution_report": {
                                                        "document_count": 1,
                                                        "classified_document_count": 1,
                                                        "classification_assignment_count": 1,
                                                        "by_level_2": [
                                                                {
                                                                        "category": "多组学数据分析",
                                                                        "document_count": 1,
                                                                        "percentage": 100.0
                                                                }
                                                        ],
                                                        "by_level_3": [
                                                                {
                                                                        "category": "多组学整合分类",
                                                                        "document_count": 1,
                                                                        "percentage": 100.0
                                                                }
                                                        ]
                                                }
                                        }
                                },
                                {
                                        "index": 3,
                                        "input_id": "text3",
                                        "status": "success",
                                        "code": 0,
                                        "result": {
                                                "tool": "专业领域科技文献分类",
                                                "input_type": "text",
                                                "document": {
                                                        "title": "Multi-Omics Biomarker Discovery for Early Alzheimer’s Disease Screening",
                                                        "abstract": "The study integrates transcriptomic, proteomic, and metabolomic profiles to identify biomarkers for early Alzheimer’s disease screening. A sparse feature selection model ranks candidate markers and validates their predictive value across independent cohorts.",
                                                        "keywords": [
                                                                "biomarker discovery",
                                                                "Alzheimer's disease",
                                                                "multi-omics",
                                                                "feature selection"
                                                        ],
                                                        "language": "en"
                                                },
                                                "multilevel_classification_results": [
                                                        {
                                                                "order": 1,
                                                                "role": "main",
                                                                "level_1": "生物医学信息学",
                                                                "level_2": "多组学数据分析",
                                                                "level_3": "生物标志物识别",
                                                                "classification_path": [
                                                                        "生物医学信息学",
                                                                        "多组学数据分析",
                                                                        "生物标志物识别"
                                                                ],
                                                                "confidence": 0.94,
                                                                "evidence": [
                                                                        "文献核心研究任务与“生物标志物识别”直接对应",
                                                                        "研究对象和技术内容属于“多组学数据分析”"
                                                                ]
                                                        }
                                                ],
                                                "classification_confidence": {
                                                        "overall": 0.94,
                                                        "level_1": 0.97,
                                                        "level_2": 0.95,
                                                        "level_3": 0.94
                                                },
                                                "domain_labels": [
                                                        {
                                                                "label": "生物标志物识别",
                                                                "confidence": 0.94
                                                        },
                                                        {
                                                                "label": "阿尔茨海默病",
                                                                "confidence": 0.91
                                                        },
                                                        {
                                                                "label": "特征选择",
                                                                "confidence": 0.88
                                                        }
                                                ],
                                                "data_distribution_report": {
                                                        "document_count": 1,
                                                        "classified_document_count": 1,
                                                        "classification_assignment_count": 1,
                                                        "by_level_2": [
                                                                {
                                                                        "category": "多组学数据分析",
                                                                        "document_count": 1,
                                                                        "percentage": 100.0
                                                                }
                                                        ],
                                                        "by_level_3": [
                                                                {
                                                                        "category": "生物标志物识别",
                                                                        "document_count": 1,
                                                                        "percentage": 100.0
                                                                }
                                                        ]
                                                }
                                        }
                                },
                                {
                                        "index": 4,
                                        "input_id": "text4",
                                        "status": "success",
                                        "code": 0,
                                        "result": {
                                                "tool": "专业领域科技文献分类",
                                                "input_type": "text",
                                                "document": {
                                                        "title": "Deep Learning-Based Classification of Pulmonary Nodules in Chest CT",
                                                        "abstract": "A three-dimensional convolutional neural network is proposed to classify benign and malignant pulmonary nodules from chest CT scans. Multi-scale feature fusion and attention-guided pooling improve diagnostic classification performance on two public datasets.",
                                                        "keywords": [
                                                                "chest CT",
                                                                "pulmonary nodule",
                                                                "medical image classification",
                                                                "deep learning"
                                                        ],
                                                        "language": "en"
                                                },
                                                "multilevel_classification_results": [
                                                        {
                                                                "order": 1,
                                                                "role": "main",
                                                                "level_1": "生物医学信息学",
                                                                "level_2": "医学影像信息学",
                                                                "level_3": "医学图像分类",
                                                                "classification_path": [
                                                                        "生物医学信息学",
                                                                        "医学影像信息学",
                                                                        "医学图像分类"
                                                                ],
                                                                "confidence": 0.96,
                                                                "evidence": [
                                                                        "文献核心研究任务与“医学图像分类”直接对应",
                                                                        "研究对象和技术内容属于“医学影像信息学”"
                                                                ]
                                                        }
                                                ],
                                                "classification_confidence": {
                                                        "overall": 0.96,
                                                        "level_1": 0.99,
                                                        "level_2": 0.97,
                                                        "level_3": 0.96
                                                },
                                                "domain_labels": [
                                                        {
                                                                "label": "医学图像分类",
                                                                "confidence": 0.96
                                                        },
                                                        {
                                                                "label": "肺结节",
                                                                "confidence": 0.93
                                                        },
                                                        {
                                                                "label": "CT影像",
                                                                "confidence": 0.9
                                                        }
                                                ],
                                                "data_distribution_report": {
                                                        "document_count": 1,
                                                        "classified_document_count": 1,
                                                        "classification_assignment_count": 1,
                                                        "by_level_2": [
                                                                {
                                                                        "category": "医学影像信息学",
                                                                        "document_count": 1,
                                                                        "percentage": 100.0
                                                                }
                                                        ],
                                                        "by_level_3": [
                                                                {
                                                                        "category": "医学图像分类",
                                                                        "document_count": 1,
                                                                        "percentage": 100.0
                                                                }
                                                        ]
                                                }
                                        }
                                },
                                {
                                        "index": 5,
                                        "input_id": "text5",
                                        "status": "success",
                                        "code": 0,
                                        "result": {
                                                "tool": "专业领域科技文献分类",
                                                "input_type": "text",
                                                "document": {
                                                        "title": "Boundary-Aware Network for Multi-Organ Segmentation in Abdominal CT",
                                                        "abstract": "This work introduces a boundary-aware segmentation network for delineating multiple abdominal organs in CT images. The model combines hierarchical features, contour supervision, and uncertainty weighting to improve segmentation accuracy for small and low-contrast organs.",
                                                        "keywords": [
                                                                "medical image segmentation",
                                                                "abdominal CT",
                                                                "boundary supervision",
                                                                "multi-organ segmentation"
                                                        ],
                                                        "language": "en"
                                                },
                                                "multilevel_classification_results": [
                                                        {
                                                                "order": 1,
                                                                "role": "main",
                                                                "level_1": "生物医学信息学",
                                                                "level_2": "医学影像信息学",
                                                                "level_3": "医学图像分割",
                                                                "classification_path": [
                                                                        "生物医学信息学",
                                                                        "医学影像信息学",
                                                                        "医学图像分割"
                                                                ],
                                                                "confidence": 0.95,
                                                                "evidence": [
                                                                        "文献核心研究任务与“医学图像分割”直接对应",
                                                                        "研究对象和技术内容属于“医学影像信息学”"
                                                                ]
                                                        }
                                                ],
                                                "classification_confidence": {
                                                        "overall": 0.95,
                                                        "level_1": 0.98,
                                                        "level_2": 0.96,
                                                        "level_3": 0.95
                                                },
                                                "domain_labels": [
                                                        {
                                                                "label": "医学图像分割",
                                                                "confidence": 0.95
                                                        },
                                                        {
                                                                "label": "腹部CT",
                                                                "confidence": 0.92
                                                        },
                                                        {
                                                                "label": "边界监督",
                                                                "confidence": 0.89
                                                        }
                                                ],
                                                "data_distribution_report": {
                                                        "document_count": 1,
                                                        "classified_document_count": 1,
                                                        "classification_assignment_count": 1,
                                                        "by_level_2": [
                                                                {
                                                                        "category": "医学影像信息学",
                                                                        "document_count": 1,
                                                                        "percentage": 100.0
                                                                }
                                                        ],
                                                        "by_level_3": [
                                                                {
                                                                        "category": "医学图像分割",
                                                                        "document_count": 1,
                                                                        "percentage": 100.0
                                                                }
                                                        ]
                                                }
                                        }
                                },
                                {
                                        "index": 6,
                                        "input_id": "text6",
                                        "status": "success",
                                        "code": 0,
                                        "result": {
                                                "tool": "专业领域科技文献分类",
                                                "input_type": "text",
                                                "document": {
                                                        "title": "Weakly Supervised Lesion Detection in Digital Pathology Images",
                                                        "abstract": "A weakly supervised detection method is proposed for locating tumor lesions in gigapixel pathology images. The method uses multiple-instance learning and regional consistency constraints to identify suspicious tissue areas using only slide-level diagnostic labels.",
                                                        "keywords": [
                                                                "lesion detection",
                                                                "digital pathology",
                                                                "weak supervision",
                                                                "multiple-instance learning"
                                                        ],
                                                        "language": "en"
                                                },
                                                "multilevel_classification_results": [
                                                        {
                                                                "order": 1,
                                                                "role": "main",
                                                                "level_1": "生物医学信息学",
                                                                "level_2": "医学影像信息学",
                                                                "level_3": "病灶检测",
                                                                "classification_path": [
                                                                        "生物医学信息学",
                                                                        "医学影像信息学",
                                                                        "病灶检测"
                                                                ],
                                                                "confidence": 0.93,
                                                                "evidence": [
                                                                        "文献核心研究任务与“病灶检测”直接对应",
                                                                        "研究对象和技术内容属于“医学影像信息学”"
                                                                ]
                                                        }
                                                ],
                                                "classification_confidence": {
                                                        "overall": 0.93,
                                                        "level_1": 0.9600000000000001,
                                                        "level_2": 0.9400000000000001,
                                                        "level_3": 0.93
                                                },
                                                "domain_labels": [
                                                        {
                                                                "label": "病灶检测",
                                                                "confidence": 0.93
                                                        },
                                                        {
                                                                "label": "数字病理",
                                                                "confidence": 0.9
                                                        },
                                                        {
                                                                "label": "弱监督学习",
                                                                "confidence": 0.87
                                                        }
                                                ],
                                                "data_distribution_report": {
                                                        "document_count": 1,
                                                        "classified_document_count": 1,
                                                        "classification_assignment_count": 1,
                                                        "by_level_2": [
                                                                {
                                                                        "category": "医学影像信息学",
                                                                        "document_count": 1,
                                                                        "percentage": 100.0
                                                                }
                                                        ],
                                                        "by_level_3": [
                                                                {
                                                                        "category": "病灶检测",
                                                                        "document_count": 1,
                                                                        "percentage": 100.0
                                                                }
                                                        ]
                                                }
                                        }
                                },
                                {
                                        "index": 7,
                                        "input_id": "text7",
                                        "status": "success",
                                        "code": 0,
                                        "result": {
                                                "tool": "专业领域科技文献分类",
                                                "input_type": "text",
                                                "document": {
                                                        "title": "Knowledge Graph-Based Clinical Decision Support for Rare Disease Diagnosis",
                                                        "abstract": "A clinical knowledge graph integrating symptoms, diseases, genes, examinations, and treatments is constructed for rare disease diagnosis. Graph reasoning ranks diagnostic candidates and provides traceable evidence paths to support clinicians in differential diagnosis.",
                                                        "keywords": [
                                                                "clinical decision support",
                                                                "rare disease diagnosis",
                                                                "knowledge graph",
                                                                "graph reasoning"
                                                        ],
                                                        "language": "en"
                                                },
                                                "multilevel_classification_results": [
                                                        {
                                                                "order": 1,
                                                                "role": "main",
                                                                "level_1": "生物医学信息学",
                                                                "level_2": "临床决策支持",
                                                                "level_3": "辅助诊断",
                                                                "classification_path": [
                                                                        "生物医学信息学",
                                                                        "临床决策支持",
                                                                        "辅助诊断"
                                                                ],
                                                                "confidence": 0.95,
                                                                "evidence": [
                                                                        "文献核心研究任务与“辅助诊断”直接对应",
                                                                        "研究对象和技术内容属于“临床决策支持”"
                                                                ]
                                                        }
                                                ],
                                                "classification_confidence": {
                                                        "overall": 0.95,
                                                        "level_1": 0.98,
                                                        "level_2": 0.96,
                                                        "level_3": 0.95
                                                },
                                                "domain_labels": [
                                                        {
                                                                "label": "辅助诊断",
                                                                "confidence": 0.95
                                                        },
                                                        {
                                                                "label": "罕见病",
                                                                "confidence": 0.92
                                                        },
                                                        {
                                                                "label": "临床知识图谱",
                                                                "confidence": 0.89
                                                        }
                                                ],
                                                "data_distribution_report": {
                                                        "document_count": 1,
                                                        "classified_document_count": 1,
                                                        "classification_assignment_count": 1,
                                                        "by_level_2": [
                                                                {
                                                                        "category": "临床决策支持",
                                                                        "document_count": 1,
                                                                        "percentage": 100.0
                                                                }
                                                        ],
                                                        "by_level_3": [
                                                                {
                                                                        "category": "辅助诊断",
                                                                        "document_count": 1,
                                                                        "percentage": 100.0
                                                                }
                                                        ]
                                                }
                                        }
                                },
                                {
                                        "index": 8,
                                        "input_id": "text8",
                                        "status": "success",
                                        "code": 0,
                                        "result": {
                                                "tool": "专业领域科技文献分类",
                                                "input_type": "text",
                                                "document": {
                                                        "title": "Early Sepsis Risk Prediction from Longitudinal Electronic Health Records",
                                                        "abstract": "A temporal prediction model is developed to estimate sepsis risk six hours before clinical onset using longitudinal electronic health records. The model combines irregular time-series encoding, missing-value modeling, and calibrated risk estimation to support early clinical intervention.",
                                                        "keywords": [
                                                                "sepsis",
                                                                "risk prediction",
                                                                "electronic health records",
                                                                "temporal modeling"
                                                        ],
                                                        "language": "en"
                                                },
                                                "multilevel_classification_results": [
                                                        {
                                                                "order": 1,
                                                                "role": "main",
                                                                "level_1": "生物医学信息学",
                                                                "level_2": "临床决策支持",
                                                                "level_3": "临床风险预测",
                                                                "classification_path": [
                                                                        "生物医学信息学",
                                                                        "临床决策支持",
                                                                        "临床风险预测"
                                                                ],
                                                                "confidence": 0.94,
                                                                "evidence": [
                                                                        "文献核心研究任务与“临床风险预测”直接对应",
                                                                        "研究对象和技术内容属于“临床决策支持”"
                                                                ]
                                                        }
                                                ],
                                                "classification_confidence": {
                                                        "overall": 0.94,
                                                        "level_1": 0.97,
                                                        "level_2": 0.95,
                                                        "level_3": 0.94
                                                },
                                                "domain_labels": [
                                                        {
                                                                "label": "临床风险预测",
                                                                "confidence": 0.94
                                                        },
                                                        {
                                                                "label": "脓毒症",
                                                                "confidence": 0.91
                                                        },
                                                        {
                                                                "label": "电子健康记录",
                                                                "confidence": 0.88
                                                        }
                                                ],
                                                "data_distribution_report": {
                                                        "document_count": 1,
                                                        "classified_document_count": 1,
                                                        "classification_assignment_count": 1,
                                                        "by_level_2": [
                                                                {
                                                                        "category": "临床决策支持",
                                                                        "document_count": 1,
                                                                        "percentage": 100.0
                                                                }
                                                        ],
                                                        "by_level_3": [
                                                                {
                                                                        "category": "临床风险预测",
                                                                        "document_count": 1,
                                                                        "percentage": 100.0
                                                                }
                                                        ]
                                                }
                                        }
                                },
                                {
                                        "index": 9,
                                        "input_id": "text9",
                                        "status": "success",
                                        "code": 0,
                                        "result": {
                                                "tool": "专业领域科技文献分类",
                                                "input_type": "text",
                                                "document": {
                                                        "title": "Construction of a Biomedical Knowledge Graph for Drug Repurposing",
                                                        "abstract": "This study constructs a biomedical knowledge graph from drugs, diseases, genes, pathways, and clinical trials. Entity normalization and relation fusion are used to integrate heterogeneous evidence, enabling graph-based candidate ranking for drug repurposing.",
                                                        "keywords": [
                                                                "biomedical knowledge graph",
                                                                "drug repurposing",
                                                                "entity normalization",
                                                                "relation fusion"
                                                        ],
                                                        "language": "en"
                                                },
                                                "multilevel_classification_results": [
                                                        {
                                                                "order": 1,
                                                                "role": "main",
                                                                "level_1": "生物医学信息学",
                                                                "level_2": "医学知识组织",
                                                                "level_3": "医学知识图谱构建",
                                                                "classification_path": [
                                                                        "生物医学信息学",
                                                                        "医学知识组织",
                                                                        "医学知识图谱构建"
                                                                ],
                                                                "confidence": 0.96,
                                                                "evidence": [
                                                                        "文献核心研究任务与“医学知识图谱构建”直接对应",
                                                                        "研究对象和技术内容属于“医学知识组织”"
                                                                ]
                                                        }
                                                ],
                                                "classification_confidence": {
                                                        "overall": 0.96,
                                                        "level_1": 0.99,
                                                        "level_2": 0.97,
                                                        "level_3": 0.96
                                                },
                                                "domain_labels": [
                                                        {
                                                                "label": "医学知识图谱",
                                                                "confidence": 0.96
                                                        },
                                                        {
                                                                "label": "药物重定位",
                                                                "confidence": 0.93
                                                        },
                                                        {
                                                                "label": "异构数据融合",
                                                                "confidence": 0.9
                                                        }
                                                ],
                                                "data_distribution_report": {
                                                        "document_count": 1,
                                                        "classified_document_count": 1,
                                                        "classification_assignment_count": 1,
                                                        "by_level_2": [
                                                                {
                                                                        "category": "医学知识组织",
                                                                        "document_count": 1,
                                                                        "percentage": 100.0
                                                                }
                                                        ],
                                                        "by_level_3": [
                                                                {
                                                                        "category": "医学知识图谱构建",
                                                                        "document_count": 1,
                                                                        "percentage": 100.0
                                                                }
                                                        ]
                                                }
                                        }
                                },
                                {
                                        "index": 10,
                                        "input_id": "text10",
                                        "status": "success",
                                        "code": 0,
                                        "result": {
                                                "tool": "专业领域科技文献分类",
                                                "input_type": "text",
                                                "document": {
                                                        "title": "Biomedical Entity and Relation Extraction from Clinical Research Articles",
                                                        "abstract": "A joint information extraction model identifies diseases, drugs, genes, and treatment relations from clinical research articles. Domain-adaptive language modeling and span-level interaction improve entity recognition and relation extraction under limited annotated data.",
                                                        "keywords": [
                                                                "biomedical entity recognition",
                                                                "relation extraction",
                                                                "clinical text mining",
                                                                "domain adaptation"
                                                        ],
                                                        "language": "en"
                                                },
                                                "multilevel_classification_results": [
                                                        {
                                                                "order": 1,
                                                                "role": "main",
                                                                "level_1": "生物医学信息学",
                                                                "level_2": "医学知识组织",
                                                                "level_3": "生物医学实体关系抽取",
                                                                "classification_path": [
                                                                        "生物医学信息学",
                                                                        "医学知识组织",
                                                                        "生物医学实体关系抽取"
                                                                ],
                                                                "confidence": 0.93,
                                                                "evidence": [
                                                                        "文献核心研究任务与“生物医学实体关系抽取”直接对应",
                                                                        "研究对象和技术内容属于“医学知识组织”"
                                                                ]
                                                        }
                                                ],
                                                "classification_confidence": {
                                                        "overall": 0.93,
                                                        "level_1": 0.9600000000000001,
                                                        "level_2": 0.9400000000000001,
                                                        "level_3": 0.93
                                                },
                                                "domain_labels": [
                                                        {
                                                                "label": "生物医学实体识别",
                                                                "confidence": 0.93
                                                        },
                                                        {
                                                                "label": "关系抽取",
                                                                "confidence": 0.9
                                                        },
                                                        {
                                                                "label": "临床文本挖掘",
                                                                "confidence": 0.87
                                                        }
                                                ],
                                                "data_distribution_report": {
                                                        "document_count": 1,
                                                        "classified_document_count": 1,
                                                        "classification_assignment_count": 1,
                                                        "by_level_2": [
                                                                {
                                                                        "category": "医学知识组织",
                                                                        "document_count": 1,
                                                                        "percentage": 100.0
                                                                }
                                                        ],
                                                        "by_level_3": [
                                                                {
                                                                        "category": "生物医学实体关系抽取",
                                                                        "document_count": 1,
                                                                        "percentage": 100.0
                                                                }
                                                        ]
                                                }
                                        }
                                }
                        ],
                        "data_distribution_report": {
                                "document_count": 10,
                                "classified_document_count": 10,
                                "classification_assignment_count": 10,
                                "by_level_2": [
                                        {
                                                "category": "多组学数据分析",
                                                "document_count": 3,
                                                "percentage": 30.0
                                        },
                                        {
                                                "category": "医学影像信息学",
                                                "document_count": 3,
                                                "percentage": 30.0
                                        },
                                        {
                                                "category": "临床决策支持",
                                                "document_count": 2,
                                                "percentage": 20.0
                                        },
                                        {
                                                "category": "医学知识组织",
                                                "document_count": 2,
                                                "percentage": 20.0
                                        }
                                ],
                                "by_level_3": [
                                        {
                                                "parent_category": "多组学数据分析",
                                                "category": "多组学整合分类",
                                                "document_count": 2,
                                                "percentage": 20.0
                                        },
                                        {
                                                "parent_category": "多组学数据分析",
                                                "category": "生物标志物识别",
                                                "document_count": 1,
                                                "percentage": 10.0
                                        },
                                        {
                                                "parent_category": "医学影像信息学",
                                                "category": "医学图像分类",
                                                "document_count": 1,
                                                "percentage": 10.0
                                        },
                                        {
                                                "parent_category": "医学影像信息学",
                                                "category": "医学图像分割",
                                                "document_count": 1,
                                                "percentage": 10.0
                                        },
                                        {
                                                "parent_category": "医学影像信息学",
                                                "category": "病灶检测",
                                                "document_count": 1,
                                                "percentage": 10.0
                                        },
                                        {
                                                "parent_category": "临床决策支持",
                                                "category": "辅助诊断",
                                                "document_count": 1,
                                                "percentage": 10.0
                                        },
                                        {
                                                "parent_category": "临床决策支持",
                                                "category": "临床风险预测",
                                                "document_count": 1,
                                                "percentage": 10.0
                                        },
                                        {
                                                "parent_category": "医学知识组织",
                                                "category": "医学知识图谱构建",
                                                "document_count": 1,
                                                "percentage": 10.0
                                        },
                                        {
                                                "parent_category": "医学知识组织",
                                                "category": "生物医学实体关系抽取",
                                                "document_count": 1,
                                                "percentage": 10.0
                                        }
                                ]
                        }
                },
                "meta": {
                        "selected_domain": {
                                "code": "biomedical_informatics",
                                "name": "生物医学信息学"
                        },
                        "max_concurrency": 3,
                        "elapsed_ms": 6840
                }
        },
        "demoFileResult": {
                "code": 0,
                "message": "success",
                "data": {
                        "tool": "专业领域科技文献分类",
                        "input_type": "file",
                        "document": {
                                "title": "MOGONET integrates multi-omics data using graph convolutional networks allowing patient classification and biomarker identification",
                                "abstract": "To fully utilize the advances in omics technologies and achieve a more comprehensive understanding of human diseases, novel computational methods are required for integrative analysis of multiple types of omics data. Here, we present a novel multi-omics integrative method named Multi-Omics Graph cOnvolutional NETworks (MOGONET) for biomedical classification. MOGONET jointly explores omics-specific learning and cross-omics correlation learning for effective multi-omics data classification. We demonstrate that MOGONET outperforms other state-of-the-art supervised multi-omics integrative analysis approaches in different biomedical classification applications using mRNA expression data, DNA methylation data, and microRNA expression data. Furthermore, MOGONET can identify important biomarkers from different omics data types related to the investigated biomedical problems.",
                                "keywords": [
                                        "multi-omics data integration",
                                        "graph convolutional networks",
                                        "patient classification",
                                        "biomarker identification",
                                        "cross-omics correlation"
                                ],
                                "language": "en",
                                "file_type": "PDF",
                                "metadata_extraction_status": "success"
                        },
                        "multilevel_classification_results": [
                                {
                                        "order": 1,
                                        "role": "main",
                                        "level_1": "生物医学信息学",
                                        "level_2": "多组学数据分析",
                                        "level_3": "多组学整合分类",
                                        "classification_path": [
                                                "生物医学信息学",
                                                "多组学数据分析",
                                                "多组学整合分类"
                                        ],
                                        "confidence": 0.97,
                                        "evidence": [
                                                "整合mRNA表达、DNA甲基化和miRNA表达数据",
                                                "面向患者、肿瘤等级和癌症亚型分类"
                                        ]
                                },
                                {
                                        "order": 2,
                                        "role": "secondary",
                                        "level_1": "生物医学信息学",
                                        "level_2": "生物标志物分析",
                                        "level_3": "疾病相关生物标志物识别",
                                        "classification_path": [
                                                "生物医学信息学",
                                                "生物标志物分析",
                                                "疾病相关生物标志物识别"
                                        ],
                                        "confidence": 0.93,
                                        "evidence": [
                                                "识别不同组学数据中的重要特征",
                                                "分析与具体疾病相关的潜在生物标志物"
                                        ]
                                }
                        ],
                        "classification_confidence": {
                                "overall": 0.96,
                                "level_1": 0.99,
                                "level_2": 0.97,
                                "level_3": 0.95
                        },
                        "domain_labels": [
                                {
                                        "label": "多组学数据分析",
                                        "confidence": 0.98
                                },
                                {
                                        "label": "患者分类",
                                        "confidence": 0.96
                                },
                                {
                                        "label": "生物标志物识别",
                                        "confidence": 0.93
                                },
                                {
                                        "label": "图神经网络",
                                        "confidence": 0.89
                                }
                        ],
                        "data_distribution_report": {
                                "document_count": 1,
                                "classified_document_count": 1,
                                "classification_assignment_count": 2,
                                "by_level_1": [
                                        {
                                                "category": "生物医学信息学",
                                                "document_count": 1,
                                                "percentage": 100.0
                                        }
                                ],
                                "by_level_2": [
                                        {
                                                "category": "多组学数据分析",
                                                "assignment_count": 1
                                        },
                                        {
                                                "category": "生物标志物分析",
                                                "assignment_count": 1
                                        }
                                ],
                                "by_level_3": [
                                        {
                                                "category": "多组学整合分类",
                                                "assignment_count": 1
                                        },
                                        {
                                                "category": "疾病相关生物标志物识别",
                                                "assignment_count": 1
                                        }
                                ]
                        }
                },
                "meta": {
                        "request_id": "req_domain_classify_file_202607190003",
                        "selected_domain": {
                                "code": "biomedical_informatics",
                                "name": "生物医学信息学"
                        },
                        "elapsed_ms": 1770
                }
        },
        "demoBatchFileResult": {
                "code": 0,
                "message": "batch_completed",
                "data": {
                        "batch_id": "batch_domain_classify_file_202607190002",
                        "input_type": "files",
                        "total": 2,
                        "success_count": 2,
                        "failed_count": 0,
                        "results": [
                                {
                                        "index": 1,
                                        "file_name": "MOGONET_domain_classification.pdf",
                                        "status": "success",
                                        "code": 0,
                                        "result": {
                                                "tool": "专业领域科技文献分类",
                                                "input_type": "file",
                                                "document": {
                                                        "title": "MOGONET integrates multi-omics data using graph convolutional networks allowing patient classification and biomarker identification",
                                                        "abstract": "To fully utilize the advances in omics technologies and achieve a more comprehensive understanding of human diseases, novel computational methods are required for integrative analysis of multiple types of omics data. Here, we present a novel multi-omics integrative method named Multi-Omics Graph cOnvolutional NETworks (MOGONET) for biomedical classification. MOGONET jointly explores omics-specific learning and cross-omics correlation learning for effective multi-omics data classification. We demonstrate that MOGONET outperforms other state-of-the-art supervised multi-omics integrative analysis approaches in different biomedical classification applications using mRNA expression data, DNA methylation data, and microRNA expression data. Furthermore, MOGONET can identify important biomarkers from different omics data types related to the investigated biomedical problems.",
                                                        "keywords": [
                                                                "multi-omics data integration",
                                                                "graph convolutional networks",
                                                                "patient classification",
                                                                "biomarker identification",
                                                                "cross-omics correlation"
                                                        ],
                                                        "language": "en"
                                                },
                                                "multilevel_classification_results": [
                                                        {
                                                                "order": 1,
                                                                "role": "main",
                                                                "level_1": "生物医学信息学",
                                                                "level_2": "多组学数据分析",
                                                                "level_3": "多组学整合分类",
                                                                "classification_path": [
                                                                        "生物医学信息学",
                                                                        "多组学数据分析",
                                                                        "多组学整合分类"
                                                                ],
                                                                "confidence": 0.97,
                                                                "evidence": [
                                                                        "整合mRNA表达、DNA甲基化和miRNA表达数据",
                                                                        "面向患者、肿瘤等级和癌症亚型分类"
                                                                ]
                                                        },
                                                        {
                                                                "order": 2,
                                                                "role": "secondary",
                                                                "level_1": "生物医学信息学",
                                                                "level_2": "生物标志物分析",
                                                                "level_3": "疾病相关生物标志物识别",
                                                                "classification_path": [
                                                                        "生物医学信息学",
                                                                        "生物标志物分析",
                                                                        "疾病相关生物标志物识别"
                                                                ],
                                                                "confidence": 0.93,
                                                                "evidence": [
                                                                        "识别不同组学数据中的重要特征",
                                                                        "分析与具体疾病相关的潜在生物标志物"
                                                                ]
                                                        }
                                                ],
                                                "classification_confidence": {
                                                        "overall": 0.96,
                                                        "level_1": 0.99,
                                                        "level_2": 0.97,
                                                        "level_3": 0.95
                                                },
                                                "domain_labels": [
                                                        {
                                                                "label": "多组学数据分析",
                                                                "confidence": 0.98
                                                        },
                                                        {
                                                                "label": "患者分类",
                                                                "confidence": 0.96
                                                        },
                                                        {
                                                                "label": "生物标志物识别",
                                                                "confidence": 0.93
                                                        },
                                                        {
                                                                "label": "图神经网络",
                                                                "confidence": 0.89
                                                        }
                                                ],
                                                "data_distribution_report": {
                                                        "document_count": 1,
                                                        "classified_document_count": 1,
                                                        "classification_assignment_count": 2,
                                                        "by_level_1": [
                                                                {
                                                                        "category": "生物医学信息学",
                                                                        "document_count": 1,
                                                                        "percentage": 100.0
                                                                }
                                                        ],
                                                        "by_level_2": [
                                                                {
                                                                        "category": "多组学数据分析",
                                                                        "assignment_count": 1
                                                                },
                                                                {
                                                                        "category": "生物标志物分析",
                                                                        "assignment_count": 1
                                                                }
                                                        ],
                                                        "by_level_3": [
                                                                {
                                                                        "category": "多组学整合分类",
                                                                        "assignment_count": 1
                                                                },
                                                                {
                                                                        "category": "疾病相关生物标志物识别",
                                                                        "assignment_count": 1
                                                                }
                                                        ]
                                                }
                                        }
                                },
                                {
                                        "index": 2,
                                        "file_name": "Federated_Medical_Imaging_Classification.txt",
                                        "status": "success",
                                        "code": 0,
                                        "result": {
                                                "tool": "专业领域科技文献分类",
                                                "input_type": "file",
                                                "document": {
                                                        "title": "Privacy-Preserving Federated Learning for Multi-Center Medical Image Classification",
                                                        "abstract": "Multi-center medical image analysis can improve model generalization, but privacy regulations and heterogeneous data distributions prevent centralized training. This study develops a federated learning framework that combines dynamic client weighting, prototype alignment, and consistency regularization for cross-institutional medical image classification. Experiments involving four medical centers show improved diagnostic classification accuracy and reduced performance variation among institutions while raw patient images remain local.",
                                                        "keywords": [
                                                                "federated learning",
                                                                "medical image classification",
                                                                "privacy preservation",
                                                                "prototype alignment",
                                                                "multi-center learning"
                                                        ],
                                                        "language": "en"
                                                },
                                                "multilevel_classification_results": [
                                                        {
                                                                "order": 1,
                                                                "role": "main",
                                                                "level_1": "生物医学信息学",
                                                                "level_2": "医学影像信息学",
                                                                "level_3": "多中心医学影像协同分类",
                                                                "classification_path": [
                                                                        "生物医学信息学",
                                                                        "医学影像信息学",
                                                                        "多中心医学影像协同分类"
                                                                ],
                                                                "confidence": 0.96,
                                                                "evidence": [
                                                                        "核心任务为多中心医学影像分类",
                                                                        "采用联邦学习实现跨机构协同建模"
                                                                ]
                                                        }
                                                ],
                                                "classification_confidence": {
                                                        "overall": 0.95,
                                                        "level_1": 0.98,
                                                        "level_2": 0.96,
                                                        "level_3": 0.95
                                                },
                                                "domain_labels": [
                                                        {
                                                                "label": "医学影像分类",
                                                                "confidence": 0.97
                                                        },
                                                        {
                                                                "label": "联邦学习",
                                                                "confidence": 0.94
                                                        },
                                                        {
                                                                "label": "隐私保护",
                                                                "confidence": 0.92
                                                        }
                                                ],
                                                "data_distribution_report": {
                                                        "document_count": 1,
                                                        "classified_document_count": 1,
                                                        "classification_assignment_count": 1,
                                                        "by_level_1": [
                                                                {
                                                                        "category": "生物医学信息学",
                                                                        "document_count": 1,
                                                                        "percentage": 100.0
                                                                }
                                                        ],
                                                        "by_level_2": [
                                                                {
                                                                        "category": "医学影像信息学",
                                                                        "assignment_count": 1
                                                                }
                                                        ],
                                                        "by_level_3": [
                                                                {
                                                                        "category": "多中心医学影像协同分类",
                                                                        "assignment_count": 1
                                                                }
                                                        ]
                                                }
                                        }
                                }
                        ],
                        "data_distribution_report": {
                                "document_count": 2,
                                "classified_document_count": 2,
                                "classification_assignment_count": 3,
                                "by_level_1": [
                                        {
                                                "category": "生物医学信息学",
                                                "document_count": 2,
                                                "percentage": 100.0
                                        }
                                ],
                                "by_level_2": [
                                        {
                                                "category": "多组学数据分析",
                                                "assignment_count": 1
                                        },
                                        {
                                                "category": "生物标志物分析",
                                                "assignment_count": 1
                                        },
                                        {
                                                "category": "医学影像信息学",
                                                "assignment_count": 1
                                        }
                                ],
                                "by_level_3": [
                                        {
                                                "category": "多组学整合分类",
                                                "assignment_count": 1
                                        },
                                        {
                                                "category": "疾病相关生物标志物识别",
                                                "assignment_count": 1
                                        },
                                        {
                                                "category": "多中心医学影像协同分类",
                                                "assignment_count": 1
                                        }
                                ],
                                "by_domain_label": [
                                        {
                                                "label": "多组学数据分析",
                                                "document_count": 1
                                        },
                                        {
                                                "label": "患者分类",
                                                "document_count": 1
                                        },
                                        {
                                                "label": "生物标志物识别",
                                                "document_count": 1
                                        },
                                        {
                                                "label": "图神经网络",
                                                "document_count": 1
                                        },
                                        {
                                                "label": "医学影像分类",
                                                "document_count": 1
                                        },
                                        {
                                                "label": "联邦学习",
                                                "document_count": 1
                                        },
                                        {
                                                "label": "隐私保护",
                                                "document_count": 1
                                        }
                                ]
                        }
                },
                "meta": {
                        "selected_domain": {
                                "code": "biomedical_informatics",
                                "name": "生物医学信息学"
                        },
                        "max_concurrency": 3,
                        "elapsed_ms": 3460
                }
        },
        "response": {
                "code": 0,
                "message": "batch_completed",
                "data": {
                        "batch_id": "batch_domain_classify_file_202607190002",
                        "input_type": "files",
                        "total": 2,
                        "success_count": 2,
                        "failed_count": 0,
                        "results": [
                                {
                                        "index": 1,
                                        "file_name": "MOGONET_domain_classification.pdf",
                                        "status": "success",
                                        "code": 0,
                                        "result": {
                                                "tool": "专业领域科技文献分类",
                                                "input_type": "file",
                                                "document": {
                                                        "title": "MOGONET integrates multi-omics data using graph convolutional networks allowing patient classification and biomarker identification",
                                                        "abstract": "To fully utilize the advances in omics technologies and achieve a more comprehensive understanding of human diseases, novel computational methods are required for integrative analysis of multiple types of omics data. Here, we present a novel multi-omics integrative method named Multi-Omics Graph cOnvolutional NETworks (MOGONET) for biomedical classification. MOGONET jointly explores omics-specific learning and cross-omics correlation learning for effective multi-omics data classification. We demonstrate that MOGONET outperforms other state-of-the-art supervised multi-omics integrative analysis approaches in different biomedical classification applications using mRNA expression data, DNA methylation data, and microRNA expression data. Furthermore, MOGONET can identify important biomarkers from different omics data types related to the investigated biomedical problems.",
                                                        "keywords": [
                                                                "multi-omics data integration",
                                                                "graph convolutional networks",
                                                                "patient classification",
                                                                "biomarker identification",
                                                                "cross-omics correlation"
                                                        ],
                                                        "language": "en"
                                                },
                                                "multilevel_classification_results": [
                                                        {
                                                                "order": 1,
                                                                "role": "main",
                                                                "level_1": "生物医学信息学",
                                                                "level_2": "多组学数据分析",
                                                                "level_3": "多组学整合分类",
                                                                "classification_path": [
                                                                        "生物医学信息学",
                                                                        "多组学数据分析",
                                                                        "多组学整合分类"
                                                                ],
                                                                "confidence": 0.97,
                                                                "evidence": [
                                                                        "整合mRNA表达、DNA甲基化和miRNA表达数据",
                                                                        "面向患者、肿瘤等级和癌症亚型分类"
                                                                ]
                                                        },
                                                        {
                                                                "order": 2,
                                                                "role": "secondary",
                                                                "level_1": "生物医学信息学",
                                                                "level_2": "生物标志物分析",
                                                                "level_3": "疾病相关生物标志物识别",
                                                                "classification_path": [
                                                                        "生物医学信息学",
                                                                        "生物标志物分析",
                                                                        "疾病相关生物标志物识别"
                                                                ],
                                                                "confidence": 0.93,
                                                                "evidence": [
                                                                        "识别不同组学数据中的重要特征",
                                                                        "分析与具体疾病相关的潜在生物标志物"
                                                                ]
                                                        }
                                                ],
                                                "classification_confidence": {
                                                        "overall": 0.96,
                                                        "level_1": 0.99,
                                                        "level_2": 0.97,
                                                        "level_3": 0.95
                                                },
                                                "domain_labels": [
                                                        {
                                                                "label": "多组学数据分析",
                                                                "confidence": 0.98
                                                        },
                                                        {
                                                                "label": "患者分类",
                                                                "confidence": 0.96
                                                        },
                                                        {
                                                                "label": "生物标志物识别",
                                                                "confidence": 0.93
                                                        },
                                                        {
                                                                "label": "图神经网络",
                                                                "confidence": 0.89
                                                        }
                                                ],
                                                "data_distribution_report": {
                                                        "document_count": 1,
                                                        "classified_document_count": 1,
                                                        "classification_assignment_count": 2,
                                                        "by_level_1": [
                                                                {
                                                                        "category": "生物医学信息学",
                                                                        "document_count": 1,
                                                                        "percentage": 100.0
                                                                }
                                                        ],
                                                        "by_level_2": [
                                                                {
                                                                        "category": "多组学数据分析",
                                                                        "assignment_count": 1
                                                                },
                                                                {
                                                                        "category": "生物标志物分析",
                                                                        "assignment_count": 1
                                                                }
                                                        ],
                                                        "by_level_3": [
                                                                {
                                                                        "category": "多组学整合分类",
                                                                        "assignment_count": 1
                                                                },
                                                                {
                                                                        "category": "疾病相关生物标志物识别",
                                                                        "assignment_count": 1
                                                                }
                                                        ]
                                                }
                                        }
                                },
                                {
                                        "index": 2,
                                        "file_name": "Federated_Medical_Imaging_Classification.txt",
                                        "status": "success",
                                        "code": 0,
                                        "result": {
                                                "tool": "专业领域科技文献分类",
                                                "input_type": "file",
                                                "document": {
                                                        "title": "Privacy-Preserving Federated Learning for Multi-Center Medical Image Classification",
                                                        "abstract": "Multi-center medical image analysis can improve model generalization, but privacy regulations and heterogeneous data distributions prevent centralized training. This study develops a federated learning framework that combines dynamic client weighting, prototype alignment, and consistency regularization for cross-institutional medical image classification. Experiments involving four medical centers show improved diagnostic classification accuracy and reduced performance variation among institutions while raw patient images remain local.",
                                                        "keywords": [
                                                                "federated learning",
                                                                "medical image classification",
                                                                "privacy preservation",
                                                                "prototype alignment",
                                                                "multi-center learning"
                                                        ],
                                                        "language": "en"
                                                },
                                                "multilevel_classification_results": [
                                                        {
                                                                "order": 1,
                                                                "role": "main",
                                                                "level_1": "生物医学信息学",
                                                                "level_2": "医学影像信息学",
                                                                "level_3": "多中心医学影像协同分类",
                                                                "classification_path": [
                                                                        "生物医学信息学",
                                                                        "医学影像信息学",
                                                                        "多中心医学影像协同分类"
                                                                ],
                                                                "confidence": 0.96,
                                                                "evidence": [
                                                                        "核心任务为多中心医学影像分类",
                                                                        "采用联邦学习实现跨机构协同建模"
                                                                ]
                                                        }
                                                ],
                                                "classification_confidence": {
                                                        "overall": 0.95,
                                                        "level_1": 0.98,
                                                        "level_2": 0.96,
                                                        "level_3": 0.95
                                                },
                                                "domain_labels": [
                                                        {
                                                                "label": "医学影像分类",
                                                                "confidence": 0.97
                                                        },
                                                        {
                                                                "label": "联邦学习",
                                                                "confidence": 0.94
                                                        },
                                                        {
                                                                "label": "隐私保护",
                                                                "confidence": 0.92
                                                        }
                                                ],
                                                "data_distribution_report": {
                                                        "document_count": 1,
                                                        "classified_document_count": 1,
                                                        "classification_assignment_count": 1,
                                                        "by_level_1": [
                                                                {
                                                                        "category": "生物医学信息学",
                                                                        "document_count": 1,
                                                                        "percentage": 100.0
                                                                }
                                                        ],
                                                        "by_level_2": [
                                                                {
                                                                        "category": "医学影像信息学",
                                                                        "assignment_count": 1
                                                                }
                                                        ],
                                                        "by_level_3": [
                                                                {
                                                                        "category": "多中心医学影像协同分类",
                                                                        "assignment_count": 1
                                                                }
                                                        ]
                                                }
                                        }
                                }
                        ],
                        "data_distribution_report": {
                                "document_count": 2,
                                "classified_document_count": 2,
                                "classification_assignment_count": 3,
                                "by_level_1": [
                                        {
                                                "category": "生物医学信息学",
                                                "document_count": 2,
                                                "percentage": 100.0
                                        }
                                ],
                                "by_level_2": [
                                        {
                                                "category": "多组学数据分析",
                                                "assignment_count": 1
                                        },
                                        {
                                                "category": "生物标志物分析",
                                                "assignment_count": 1
                                        },
                                        {
                                                "category": "医学影像信息学",
                                                "assignment_count": 1
                                        }
                                ],
                                "by_level_3": [
                                        {
                                                "category": "多组学整合分类",
                                                "assignment_count": 1
                                        },
                                        {
                                                "category": "疾病相关生物标志物识别",
                                                "assignment_count": 1
                                        },
                                        {
                                                "category": "多中心医学影像协同分类",
                                                "assignment_count": 1
                                        }
                                ],
                                "by_domain_label": [
                                        {
                                                "label": "多组学数据分析",
                                                "document_count": 1
                                        },
                                        {
                                                "label": "患者分类",
                                                "document_count": 1
                                        },
                                        {
                                                "label": "生物标志物识别",
                                                "document_count": 1
                                        },
                                        {
                                                "label": "图神经网络",
                                                "document_count": 1
                                        },
                                        {
                                                "label": "医学影像分类",
                                                "document_count": 1
                                        },
                                        {
                                                "label": "联邦学习",
                                                "document_count": 1
                                        },
                                        {
                                                "label": "隐私保护",
                                                "document_count": 1
                                        }
                                ]
                        }
                },
                "meta": {
                        "selected_domain": {
                                "code": "biomedical_informatics",
                                "name": "生物医学信息学"
                        },
                        "max_concurrency": 3,
                        "elapsed_ms": 3460
                }
        }
},
      "zh-keyword": {"group":"关键词识别工具","title":"中文科技文献关键词识别","documentType":"keyword","languageCode":"zh","languageName":"中文","description":"面向医学、工程、材料科学等多领域中文科技语料，从科技文献摘要中提取核心关键词或关键短语。支持单文本、批量文本、单文件和批量文件；文件模式仅解析并使用摘要。系统自动识别文献领域，并在算法内部自适应调用领域术语资源与动态词权模型，无需用户上传或维护词典。","features":"单文本与批量文本、单文件与批量文件、摘要自动定位、领域自动识别、自适应术语资源、动态词权计算、术语边界识别、5—8个关键词自适应输出、置信度排序、原文位置保留","scenarios":"中文论文关键词补全、批量文献标引、领域术语抽取、本地化情报分析、专题研究","endpoint":"/api/v1/keywords/zh/text","textEndpoint":"/api/v1/keywords/zh/text","batchTextEndpoint":"/api/v1/keywords/zh/texts","fileEndpoint":"/api/v1/keywords/zh/file","batchFileEndpoint":"/api/v1/keywords/zh/files","inputModes":["text","batch-text","file","batch"],"supportsFileUpload":true,"supportsBatchUpload":true,"acceptedFiles":[".pdf",".docx",".txt"],"maxFileSizeMB":50,"maxBatchFiles":20,"maxBatchTexts":20,"documentTarget":"中文科技文献摘要","fileProcessingHint":"上传后自动解析文档并定位摘要，仅使用摘要内容进行关键词识别","batchProcessingHint":"逐文件解析摘要并返回结构化关键词列表；标题、作者关键词和正文不参与识别","params":[["input_type","string","required","输入方式，取值为 text、texts、file 或 files"],["abstract","string","conditional","当 input_type=text 时必填：中文科技文献摘要"],["texts","object[]","conditional","当 input_type=texts 时必填：每条包含 id 和 abstract，最多20条"],["file","file","conditional","当 input_type=file 时必填：PDF、DOCX 或 TXT 文件"],["files","file[]","conditional","当 input_type=files 时必填：最多20个文件"],["min_keywords","integer","optional","最少关键词数量，默认5"],["max_keywords","integer","optional","最多关键词数量，默认8"],["preserve_order","boolean","optional","是否尽量保持摘要出现顺序，默认true"],["max_concurrency","integer","optional","批量任务并发数，默认3"],["continue_on_error","boolean","optional","单条失败时是否继续处理，默认true"]],"payload":{"input_type":"text","abstract":"复杂工业表面中的裂纹、划痕与孔洞通常具有尺度差异大、边缘模糊和背景纹理干扰强等特点，导致传统视觉检测方法容易出现漏检和误检。本文提出一种融合多尺度特征金字塔、局部注意力增强和难样本重加权的工业表面微小缺陷检测方法，在不同分辨率下提取全局结构与局部细节，并通过跨层特征融合提升微小缺陷表征能力。多个公开工业缺陷数据集上的实验结果表明，该方法在检测准确率、召回率和小目标识别性能方面均优于对比模型，可为智能制造质量检测提供技术支撑。","min_keywords":5,"max_keywords":8,"preserve_order":true},"demoText":"复杂工业表面中的裂纹、划痕与孔洞通常具有尺度差异大、边缘模糊和背景纹理干扰强等特点，导致传统视觉检测方法容易出现漏检和误检。本文提出一种融合多尺度特征金字塔、局部注意力增强和难样本重加权的工业表面微小缺陷检测方法，在不同分辨率下提取全局结构与局部细节，并通过跨层特征融合提升微小缺陷表征能力。多个公开工业缺陷数据集上的实验结果表明，该方法在检测准确率、召回率和小目标识别性能方面均优于对比模型，可为智能制造质量检测提供技术支撑。","demoBatchTexts":[{"id":"text1","text":"复杂工业表面中的裂纹、划痕与孔洞通常具有尺度差异大、边缘模糊和背景纹理干扰强等特点，导致传统视觉检测方法容易出现漏检和误检。本文提出一种融合多尺度特征金字塔、局部注意力增强和难样本重加权的工业表面微小缺陷检测方法，在不同分辨率下提取全局结构与局部细节，并通过跨层特征融合提升微小缺陷表征能力。多个公开工业缺陷数据集上的实验结果表明，该方法在检测准确率、召回率和小目标识别性能方面均优于对比模型，可为智能制造质量检测提供技术支撑。"},{"id":"text2","text":"城市地表覆盖类型存在光谱混叠、空间结构复杂和跨区域分布差异显著等问题，单一遥感数据难以实现稳定的精细分类。本文联合高分辨率光学影像、合成孔径雷达数据和地形辅助信息，构建多源遥感特征协同编码网络，通过跨模态对齐和区域上下文建模增强建筑、道路、植被与水体的区分能力。多城市实验结果表明，该方法能够提高地表覆盖分类精度和边界区域识别质量，为城市空间监测与土地利用调查提供可靠支持。"},{"id":"text3","text":"硅基负极材料具有较高理论比容量，但在充放电过程中容易发生显著体积膨胀，造成电极结构破坏和循环性能衰减。本文设计一种碳包覆多孔硅复合结构，通过纳米孔隙缓冲体积变化，并利用导电碳网络改善电子传输。电化学测试结果表明，该复合负极在高倍率条件下仍保持较高比容量和稳定循环性能，为高能量密度锂离子电池负极材料设计提供了新的技术路径。"}],"demoBatchResults":[{"id":"text1","text":"复杂工业表面中的裂纹、划痕与孔洞通常具有尺度差异大、边缘模糊和背景纹理干扰强等特点，导致传统视觉检测方法容易出现漏检和误检。本文提出一种融合多尺度特征金字塔、局部注意力增强和难样本重加权的工业表面微小缺陷检测方法，在不同分辨率下提取全局结构与局部细节，并通过跨层特征融合提升微小缺陷表征能力。多个公开工业缺陷数据集上的实验结果表明，该方法在检测准确率、召回率和小目标识别性能方面均优于对比模型，可为智能制造质量检测提供技术支撑。","keyword_count":7,"keywords":[{"rank":1,"keyword":"工业表面缺陷","confidence":0.97,"source_position":{"start":-1,"end":-1},"adaptive_resource_match":true},{"rank":2,"keyword":"微小缺陷检测","confidence":0.95,"source_position":{"start":98,"end":104},"adaptive_resource_match":true},{"rank":3,"keyword":"多尺度特征金字塔","confidence":0.93,"source_position":{"start":70,"end":78},"adaptive_resource_match":false},{"rank":4,"keyword":"局部注意力增强","confidence":0.91,"source_position":{"start":79,"end":86},"adaptive_resource_match":false},{"rank":5,"keyword":"难样本重加权","confidence":0.89,"source_position":{"start":87,"end":93},"adaptive_resource_match":false},{"rank":6,"keyword":"跨层特征融合","confidence":0.87,"source_position":{"start":129,"end":135},"adaptive_resource_match":false},{"rank":7,"keyword":"智能制造质量检测","confidence":0.84,"source_position":{"start":199,"end":207},"adaptive_resource_match":true}]},{"id":"text2","text":"城市地表覆盖类型存在光谱混叠、空间结构复杂和跨区域分布差异显著等问题，单一遥感数据难以实现稳定的精细分类。本文联合高分辨率光学影像、合成孔径雷达数据和地形辅助信息，构建多源遥感特征协同编码网络，通过跨模态对齐和区域上下文建模增强建筑、道路、植被与水体的区分能力。多城市实验结果表明，该方法能够提高地表覆盖分类精度和边界区域识别质量，为城市空间监测与土地利用调查提供可靠支持。","keyword_count":7,"keywords":[{"rank":1,"keyword":"城市地表覆盖","confidence":0.97,"source_position":{"start":0,"end":6},"adaptive_resource_match":true},{"rank":2,"keyword":"多源遥感","confidence":0.95,"source_position":{"start":84,"end":88},"adaptive_resource_match":true},{"rank":3,"keyword":"高分辨率光学影像","confidence":0.93,"source_position":{"start":57,"end":65},"adaptive_resource_match":false},{"rank":4,"keyword":"合成孔径雷达","confidence":0.92,"source_position":{"start":66,"end":72},"adaptive_resource_match":true},{"rank":5,"keyword":"跨模态对齐","confidence":0.9,"source_position":{"start":99,"end":104},"adaptive_resource_match":false},{"rank":6,"keyword":"区域上下文建模","confidence":0.88,"source_position":{"start":105,"end":112},"adaptive_resource_match":false},{"rank":7,"keyword":"城市空间监测","confidence":0.86,"source_position":{"start":167,"end":173},"adaptive_resource_match":true}]},{"id":"text3","text":"硅基负极材料具有较高理论比容量，但在充放电过程中容易发生显著体积膨胀，造成电极结构破坏和循环性能衰减。本文设计一种碳包覆多孔硅复合结构，通过纳米孔隙缓冲体积变化，并利用导电碳网络改善电子传输。电化学测试结果表明，该复合负极在高倍率条件下仍保持较高比容量和稳定循环性能，为高能量密度锂离子电池负极材料设计提供了新的技术路径。","keyword_count":7,"keywords":[{"rank":1,"keyword":"硅基负极材料","confidence":0.98,"source_position":{"start":0,"end":6},"adaptive_resource_match":true},{"rank":2,"keyword":"体积膨胀","confidence":0.94,"source_position":{"start":30,"end":34},"adaptive_resource_match":true},{"rank":3,"keyword":"碳包覆多孔硅","confidence":0.93,"source_position":{"start":57,"end":63},"adaptive_resource_match":false},{"rank":4,"keyword":"纳米孔隙","confidence":0.9,"source_position":{"start":70,"end":74},"adaptive_resource_match":false},{"rank":5,"keyword":"导电碳网络","confidence":0.89,"source_position":{"start":84,"end":89},"adaptive_resource_match":false},{"rank":6,"keyword":"循环性能","confidence":0.87,"source_position":{"start":44,"end":48},"adaptive_resource_match":true},{"rank":7,"keyword":"锂离子电池","confidence":0.86,"source_position":{"start":140,"end":145},"adaptive_resource_match":true}]}],"demoTextResult":{"code":200,"message":"success","data":{"tool":"中文科技文献关键词识别","input_type":"text","document":{"abstract":"复杂工业表面中的裂纹、划痕与孔洞通常具有尺度差异大、边缘模糊和背景纹理干扰强等特点，导致传统视觉检测方法容易出现漏检和误检。本文提出一种融合多尺度特征金字塔、局部注意力增强和难样本重加权的工业表面微小缺陷检测方法，在不同分辨率下提取全局结构与局部细节，并通过跨层特征融合提升微小缺陷表征能力。多个公开工业缺陷数据集上的实验结果表明，该方法在检测准确率、召回率和小目标识别性能方面均优于对比模型，可为智能制造质量检测提供技术支撑。","language":"zh","abstract_complete":true},"keyword_count":7,"keywords":[{"rank":1,"keyword":"工业表面缺陷","confidence":0.97,"source_position":{"start":-1,"end":-1},"adaptive_resource_match":true},{"rank":2,"keyword":"微小缺陷检测","confidence":0.95,"source_position":{"start":98,"end":104},"adaptive_resource_match":true},{"rank":3,"keyword":"多尺度特征金字塔","confidence":0.93,"source_position":{"start":70,"end":78},"adaptive_resource_match":false},{"rank":4,"keyword":"局部注意力增强","confidence":0.91,"source_position":{"start":79,"end":86},"adaptive_resource_match":false},{"rank":5,"keyword":"难样本重加权","confidence":0.89,"source_position":{"start":87,"end":93},"adaptive_resource_match":false},{"rank":6,"keyword":"跨层特征融合","confidence":0.87,"source_position":{"start":129,"end":135},"adaptive_resource_match":false},{"rank":7,"keyword":"智能制造质量检测","confidence":0.84,"source_position":{"start":199,"end":207},"adaptive_resource_match":true}]},"meta":{"adaptive_domain_resource_used":true,"adaptive_resource_term_count":9,"min_keywords":5,"max_keywords":8,"preserve_order":true,"weighting_method":"adaptive_domain_resource_dynamic_weighting","request_id":"req_keywords_zh_text_202607190001","elapsed_ms":742}},"demoBatchTextResult":{"code":200,"message":"batch_completed","data":{"batch_id":"batch_keywords_zh_text_202607190001","input_type":"texts","total":3,"success_count":3,"failed_count":0,"results":[{"index":1,"input_id":"text1","status":"success","code":200,"result":{"tool":"中文科技文献关键词识别","input_type":"text","document":{"abstract":"复杂工业表面中的裂纹、划痕与孔洞通常具有尺度差异大、边缘模糊和背景纹理干扰强等特点，导致传统视觉检测方法容易出现漏检和误检。本文提出一种融合多尺度特征金字塔、局部注意力增强和难样本重加权的工业表面微小缺陷检测方法，在不同分辨率下提取全局结构与局部细节，并通过跨层特征融合提升微小缺陷表征能力。多个公开工业缺陷数据集上的实验结果表明，该方法在检测准确率、召回率和小目标识别性能方面均优于对比模型，可为智能制造质量检测提供技术支撑。","language":"zh","abstract_complete":true},"keyword_count":7,"keywords":[{"rank":1,"keyword":"工业表面缺陷","confidence":0.97,"source_position":{"start":-1,"end":-1},"adaptive_resource_match":true},{"rank":2,"keyword":"微小缺陷检测","confidence":0.95,"source_position":{"start":98,"end":104},"adaptive_resource_match":true},{"rank":3,"keyword":"多尺度特征金字塔","confidence":0.93,"source_position":{"start":70,"end":78},"adaptive_resource_match":false},{"rank":4,"keyword":"局部注意力增强","confidence":0.91,"source_position":{"start":79,"end":86},"adaptive_resource_match":false},{"rank":5,"keyword":"难样本重加权","confidence":0.89,"source_position":{"start":87,"end":93},"adaptive_resource_match":false},{"rank":6,"keyword":"跨层特征融合","confidence":0.87,"source_position":{"start":129,"end":135},"adaptive_resource_match":false},{"rank":7,"keyword":"智能制造质量检测","confidence":0.84,"source_position":{"start":199,"end":207},"adaptive_resource_match":true}]}},{"index":2,"input_id":"text2","status":"success","code":200,"result":{"tool":"中文科技文献关键词识别","input_type":"text","document":{"abstract":"城市地表覆盖类型存在光谱混叠、空间结构复杂和跨区域分布差异显著等问题，单一遥感数据难以实现稳定的精细分类。本文联合高分辨率光学影像、合成孔径雷达数据和地形辅助信息，构建多源遥感特征协同编码网络，通过跨模态对齐和区域上下文建模增强建筑、道路、植被与水体的区分能力。多城市实验结果表明，该方法能够提高地表覆盖分类精度和边界区域识别质量，为城市空间监测与土地利用调查提供可靠支持。","language":"zh","abstract_complete":true},"keyword_count":7,"keywords":[{"rank":1,"keyword":"城市地表覆盖","confidence":0.97,"source_position":{"start":0,"end":6},"adaptive_resource_match":true},{"rank":2,"keyword":"多源遥感","confidence":0.95,"source_position":{"start":84,"end":88},"adaptive_resource_match":true},{"rank":3,"keyword":"高分辨率光学影像","confidence":0.93,"source_position":{"start":57,"end":65},"adaptive_resource_match":false},{"rank":4,"keyword":"合成孔径雷达","confidence":0.92,"source_position":{"start":66,"end":72},"adaptive_resource_match":true},{"rank":5,"keyword":"跨模态对齐","confidence":0.9,"source_position":{"start":99,"end":104},"adaptive_resource_match":false},{"rank":6,"keyword":"区域上下文建模","confidence":0.88,"source_position":{"start":105,"end":112},"adaptive_resource_match":false},{"rank":7,"keyword":"城市空间监测","confidence":0.86,"source_position":{"start":167,"end":173},"adaptive_resource_match":true}]}},{"index":3,"input_id":"text3","status":"success","code":200,"result":{"tool":"中文科技文献关键词识别","input_type":"text","document":{"abstract":"硅基负极材料具有较高理论比容量，但在充放电过程中容易发生显著体积膨胀，造成电极结构破坏和循环性能衰减。本文设计一种碳包覆多孔硅复合结构，通过纳米孔隙缓冲体积变化，并利用导电碳网络改善电子传输。电化学测试结果表明，该复合负极在高倍率条件下仍保持较高比容量和稳定循环性能，为高能量密度锂离子电池负极材料设计提供了新的技术路径。","language":"zh","abstract_complete":true},"keyword_count":7,"keywords":[{"rank":1,"keyword":"硅基负极材料","confidence":0.98,"source_position":{"start":0,"end":6},"adaptive_resource_match":true},{"rank":2,"keyword":"体积膨胀","confidence":0.94,"source_position":{"start":30,"end":34},"adaptive_resource_match":true},{"rank":3,"keyword":"碳包覆多孔硅","confidence":0.93,"source_position":{"start":57,"end":63},"adaptive_resource_match":false},{"rank":4,"keyword":"纳米孔隙","confidence":0.9,"source_position":{"start":70,"end":74},"adaptive_resource_match":false},{"rank":5,"keyword":"导电碳网络","confidence":0.89,"source_position":{"start":84,"end":89},"adaptive_resource_match":false},{"rank":6,"keyword":"循环性能","confidence":0.87,"source_position":{"start":44,"end":48},"adaptive_resource_match":true},{"rank":7,"keyword":"锂离子电池","confidence":0.86,"source_position":{"start":140,"end":145},"adaptive_resource_match":true}]}}]},"meta":{"adaptive_domain_resource_used":true,"adaptive_resource_term_count":9,"min_keywords":5,"max_keywords":8,"preserve_order":true,"max_concurrency":3,"elapsed_ms":1684}},"demoFileResult":{"code":200,"message":"success","data":{"tool":"中文科技文献关键词识别","input_type":"file","document":{"abstract":"复杂工业表面中的裂纹、划痕与孔洞通常具有尺度差异大、边缘模糊和背景纹理干扰强等特点，导致传统视觉检测方法容易出现漏检和误检。本文提出一种融合多尺度特征金字塔、局部注意力增强和难样本重加权的工业表面微小缺陷检测方法，在不同分辨率下提取全局结构与局部细节，并通过跨层特征融合提升微小缺陷表征能力。多个公开工业缺陷数据集上的实验结果表明，该方法在检测准确率、召回率和小目标识别性能方面均优于对比模型，可为智能制造质量检测提供技术支撑。","language":"zh","abstract_complete":true},"keyword_count":7,"keywords":[{"rank":1,"keyword":"工业表面缺陷","confidence":0.97,"source_position":{"start":-1,"end":-1},"adaptive_resource_match":true},{"rank":2,"keyword":"微小缺陷检测","confidence":0.95,"source_position":{"start":98,"end":104},"adaptive_resource_match":true},{"rank":3,"keyword":"多尺度特征金字塔","confidence":0.93,"source_position":{"start":70,"end":78},"adaptive_resource_match":false},{"rank":4,"keyword":"局部注意力增强","confidence":0.91,"source_position":{"start":79,"end":86},"adaptive_resource_match":false},{"rank":5,"keyword":"难样本重加权","confidence":0.89,"source_position":{"start":87,"end":93},"adaptive_resource_match":false},{"rank":6,"keyword":"跨层特征融合","confidence":0.87,"source_position":{"start":129,"end":135},"adaptive_resource_match":false},{"rank":7,"keyword":"智能制造质量检测","confidence":0.84,"source_position":{"start":199,"end":207},"adaptive_resource_match":true}],"input":{"input_type":"file","file_name":"中文关键词识别_工业表面缺陷摘要.txt","file_format":"TXT","file_size":"642 B","document_parse_status":"success","abstract_location_status":"success"}},"meta":{"adaptive_domain_resource_used":true,"adaptive_resource_term_count":9,"min_keywords":5,"max_keywords":8,"preserve_order":true,"weighting_method":"adaptive_domain_resource_dynamic_weighting","request_id":"req_keywords_zh_file_text1_202607190001","elapsed_ms":742}},"demoBatchFileResult":{"code":200,"message":"batch_completed","data":{"batch_id":"batch_keywords_zh_file_202607190001","input_type":"files","total":3,"success_count":3,"failed_count":0,"results":[{"index":1,"file_name":"中文关键词识别_工业表面缺陷摘要.txt","status":"success","code":200,"result":{"tool":"中文科技文献关键词识别","input_type":"file","document":{"abstract":"复杂工业表面中的裂纹、划痕与孔洞通常具有尺度差异大、边缘模糊和背景纹理干扰强等特点，导致传统视觉检测方法容易出现漏检和误检。本文提出一种融合多尺度特征金字塔、局部注意力增强和难样本重加权的工业表面微小缺陷检测方法，在不同分辨率下提取全局结构与局部细节，并通过跨层特征融合提升微小缺陷表征能力。多个公开工业缺陷数据集上的实验结果表明，该方法在检测准确率、召回率和小目标识别性能方面均优于对比模型，可为智能制造质量检测提供技术支撑。","language":"zh","abstract_complete":true},"keyword_count":7,"keywords":[{"rank":1,"keyword":"工业表面缺陷","confidence":0.97,"source_position":{"start":-1,"end":-1},"adaptive_resource_match":true},{"rank":2,"keyword":"微小缺陷检测","confidence":0.95,"source_position":{"start":98,"end":104},"adaptive_resource_match":true},{"rank":3,"keyword":"多尺度特征金字塔","confidence":0.93,"source_position":{"start":70,"end":78},"adaptive_resource_match":false},{"rank":4,"keyword":"局部注意力增强","confidence":0.91,"source_position":{"start":79,"end":86},"adaptive_resource_match":false},{"rank":5,"keyword":"难样本重加权","confidence":0.89,"source_position":{"start":87,"end":93},"adaptive_resource_match":false},{"rank":6,"keyword":"跨层特征融合","confidence":0.87,"source_position":{"start":129,"end":135},"adaptive_resource_match":false},{"rank":7,"keyword":"智能制造质量检测","confidence":0.84,"source_position":{"start":199,"end":207},"adaptive_resource_match":true}]}},{"index":2,"file_name":"中文关键词识别_城市遥感摘要.txt","status":"success","code":200,"result":{"tool":"中文科技文献关键词识别","input_type":"file","document":{"abstract":"城市地表覆盖类型存在光谱混叠、空间结构复杂和跨区域分布差异显著等问题，单一遥感数据难以实现稳定的精细分类。本文联合高分辨率光学影像、合成孔径雷达数据和地形辅助信息，构建多源遥感特征协同编码网络，通过跨模态对齐和区域上下文建模增强建筑、道路、植被与水体的区分能力。多城市实验结果表明，该方法能够提高地表覆盖分类精度和边界区域识别质量，为城市空间监测与土地利用调查提供可靠支持。","language":"zh","abstract_complete":true},"keyword_count":7,"keywords":[{"rank":1,"keyword":"城市地表覆盖","confidence":0.97,"source_position":{"start":0,"end":6},"adaptive_resource_match":true},{"rank":2,"keyword":"多源遥感","confidence":0.95,"source_position":{"start":84,"end":88},"adaptive_resource_match":true},{"rank":3,"keyword":"高分辨率光学影像","confidence":0.93,"source_position":{"start":57,"end":65},"adaptive_resource_match":false},{"rank":4,"keyword":"合成孔径雷达","confidence":0.92,"source_position":{"start":66,"end":72},"adaptive_resource_match":true},{"rank":5,"keyword":"跨模态对齐","confidence":0.9,"source_position":{"start":99,"end":104},"adaptive_resource_match":false},{"rank":6,"keyword":"区域上下文建模","confidence":0.88,"source_position":{"start":105,"end":112},"adaptive_resource_match":false},{"rank":7,"keyword":"城市空间监测","confidence":0.86,"source_position":{"start":167,"end":173},"adaptive_resource_match":true}]}},{"index":3,"file_name":"中文关键词识别_硅基负极材料摘要.txt","status":"success","code":200,"result":{"tool":"中文科技文献关键词识别","input_type":"file","document":{"abstract":"硅基负极材料具有较高理论比容量，但在充放电过程中容易发生显著体积膨胀，造成电极结构破坏和循环性能衰减。本文设计一种碳包覆多孔硅复合结构，通过纳米孔隙缓冲体积变化，并利用导电碳网络改善电子传输。电化学测试结果表明，该复合负极在高倍率条件下仍保持较高比容量和稳定循环性能，为高能量密度锂离子电池负极材料设计提供了新的技术路径。","language":"zh","abstract_complete":true},"keyword_count":7,"keywords":[{"rank":1,"keyword":"硅基负极材料","confidence":0.98,"source_position":{"start":0,"end":6},"adaptive_resource_match":true},{"rank":2,"keyword":"体积膨胀","confidence":0.94,"source_position":{"start":30,"end":34},"adaptive_resource_match":true},{"rank":3,"keyword":"碳包覆多孔硅","confidence":0.93,"source_position":{"start":57,"end":63},"adaptive_resource_match":false},{"rank":4,"keyword":"纳米孔隙","confidence":0.9,"source_position":{"start":70,"end":74},"adaptive_resource_match":false},{"rank":5,"keyword":"导电碳网络","confidence":0.89,"source_position":{"start":84,"end":89},"adaptive_resource_match":false},{"rank":6,"keyword":"循环性能","confidence":0.87,"source_position":{"start":44,"end":48},"adaptive_resource_match":true},{"rank":7,"keyword":"锂离子电池","confidence":0.86,"source_position":{"start":140,"end":145},"adaptive_resource_match":true}]}}]},"meta":{"adaptive_domain_resource_used":true,"adaptive_resource_term_count":9,"min_keywords":5,"max_keywords":8,"preserve_order":true,"max_concurrency":3,"elapsed_ms":2416}},"response":{"code":200,"message":"batch_completed","data":{"batch_id":"batch_keywords_zh_file_202607190001","input_type":"files","total":3,"success_count":3,"failed_count":0,"results":[{"index":1,"file_name":"中文关键词识别_工业表面缺陷摘要.txt","status":"success","code":200,"result":{"tool":"中文科技文献关键词识别","input_type":"file","document":{"abstract":"复杂工业表面中的裂纹、划痕与孔洞通常具有尺度差异大、边缘模糊和背景纹理干扰强等特点，导致传统视觉检测方法容易出现漏检和误检。本文提出一种融合多尺度特征金字塔、局部注意力增强和难样本重加权的工业表面微小缺陷检测方法，在不同分辨率下提取全局结构与局部细节，并通过跨层特征融合提升微小缺陷表征能力。多个公开工业缺陷数据集上的实验结果表明，该方法在检测准确率、召回率和小目标识别性能方面均优于对比模型，可为智能制造质量检测提供技术支撑。","language":"zh","abstract_complete":true},"keyword_count":7,"keywords":[{"rank":1,"keyword":"工业表面缺陷","confidence":0.97,"source_position":{"start":-1,"end":-1},"adaptive_resource_match":true},{"rank":2,"keyword":"微小缺陷检测","confidence":0.95,"source_position":{"start":98,"end":104},"adaptive_resource_match":true},{"rank":3,"keyword":"多尺度特征金字塔","confidence":0.93,"source_position":{"start":70,"end":78},"adaptive_resource_match":false},{"rank":4,"keyword":"局部注意力增强","confidence":0.91,"source_position":{"start":79,"end":86},"adaptive_resource_match":false},{"rank":5,"keyword":"难样本重加权","confidence":0.89,"source_position":{"start":87,"end":93},"adaptive_resource_match":false},{"rank":6,"keyword":"跨层特征融合","confidence":0.87,"source_position":{"start":129,"end":135},"adaptive_resource_match":false},{"rank":7,"keyword":"智能制造质量检测","confidence":0.84,"source_position":{"start":199,"end":207},"adaptive_resource_match":true}]}},{"index":2,"file_name":"中文关键词识别_城市遥感摘要.txt","status":"success","code":200,"result":{"tool":"中文科技文献关键词识别","input_type":"file","document":{"abstract":"城市地表覆盖类型存在光谱混叠、空间结构复杂和跨区域分布差异显著等问题，单一遥感数据难以实现稳定的精细分类。本文联合高分辨率光学影像、合成孔径雷达数据和地形辅助信息，构建多源遥感特征协同编码网络，通过跨模态对齐和区域上下文建模增强建筑、道路、植被与水体的区分能力。多城市实验结果表明，该方法能够提高地表覆盖分类精度和边界区域识别质量，为城市空间监测与土地利用调查提供可靠支持。","language":"zh","abstract_complete":true},"keyword_count":7,"keywords":[{"rank":1,"keyword":"城市地表覆盖","confidence":0.97,"source_position":{"start":0,"end":6},"adaptive_resource_match":true},{"rank":2,"keyword":"多源遥感","confidence":0.95,"source_position":{"start":84,"end":88},"adaptive_resource_match":true},{"rank":3,"keyword":"高分辨率光学影像","confidence":0.93,"source_position":{"start":57,"end":65},"adaptive_resource_match":false},{"rank":4,"keyword":"合成孔径雷达","confidence":0.92,"source_position":{"start":66,"end":72},"adaptive_resource_match":true},{"rank":5,"keyword":"跨模态对齐","confidence":0.9,"source_position":{"start":99,"end":104},"adaptive_resource_match":false},{"rank":6,"keyword":"区域上下文建模","confidence":0.88,"source_position":{"start":105,"end":112},"adaptive_resource_match":false},{"rank":7,"keyword":"城市空间监测","confidence":0.86,"source_position":{"start":167,"end":173},"adaptive_resource_match":true}]}},{"index":3,"file_name":"中文关键词识别_硅基负极材料摘要.txt","status":"success","code":200,"result":{"tool":"中文科技文献关键词识别","input_type":"file","document":{"abstract":"硅基负极材料具有较高理论比容量，但在充放电过程中容易发生显著体积膨胀，造成电极结构破坏和循环性能衰减。本文设计一种碳包覆多孔硅复合结构，通过纳米孔隙缓冲体积变化，并利用导电碳网络改善电子传输。电化学测试结果表明，该复合负极在高倍率条件下仍保持较高比容量和稳定循环性能，为高能量密度锂离子电池负极材料设计提供了新的技术路径。","language":"zh","abstract_complete":true},"keyword_count":7,"keywords":[{"rank":1,"keyword":"硅基负极材料","confidence":0.98,"source_position":{"start":0,"end":6},"adaptive_resource_match":true},{"rank":2,"keyword":"体积膨胀","confidence":0.94,"source_position":{"start":30,"end":34},"adaptive_resource_match":true},{"rank":3,"keyword":"碳包覆多孔硅","confidence":0.93,"source_position":{"start":57,"end":63},"adaptive_resource_match":false},{"rank":4,"keyword":"纳米孔隙","confidence":0.9,"source_position":{"start":70,"end":74},"adaptive_resource_match":false},{"rank":5,"keyword":"导电碳网络","confidence":0.89,"source_position":{"start":84,"end":89},"adaptive_resource_match":false},{"rank":6,"keyword":"循环性能","confidence":0.87,"source_position":{"start":44,"end":48},"adaptive_resource_match":true},{"rank":7,"keyword":"锂离子电池","confidence":0.86,"source_position":{"start":140,"end":145},"adaptive_resource_match":true}]}}]},"meta":{"adaptive_domain_resource_used":true,"adaptive_resource_term_count":9,"min_keywords":5,"max_keywords":8,"preserve_order":true,"max_concurrency":3,"elapsed_ms":2416}},"sampleFileName":"中文关键词识别_工业表面缺陷摘要.txt","sampleFileSize":"642 B","demoFileSizeBytes":642,"demoFileSha256":"6174efac6da2100bfae282a2af8f09afa8fd59761bcc7cf16e58ece6015f79f6","demoFileFnv1a32":"6cf5f9b4","batchSampleFileNames":["中文关键词识别_工业表面缺陷摘要.txt","中文关键词识别_城市遥感摘要.txt","中文关键词识别_硅基负极材料摘要.txt"],"demoFileFixtures":[{"file_name":"中文关键词识别_工业表面缺陷摘要.txt","size_bytes":642,"sha256":"6174efac6da2100bfae282a2af8f09afa8fd59761bcc7cf16e58ece6015f79f6","fnv1a32":"6cf5f9b4","result":{"code":200,"message":"success","data":{"tool":"中文科技文献关键词识别","input_type":"file","document":{"abstract":"复杂工业表面中的裂纹、划痕与孔洞通常具有尺度差异大、边缘模糊和背景纹理干扰强等特点，导致传统视觉检测方法容易出现漏检和误检。本文提出一种融合多尺度特征金字塔、局部注意力增强和难样本重加权的工业表面微小缺陷检测方法，在不同分辨率下提取全局结构与局部细节，并通过跨层特征融合提升微小缺陷表征能力。多个公开工业缺陷数据集上的实验结果表明，该方法在检测准确率、召回率和小目标识别性能方面均优于对比模型，可为智能制造质量检测提供技术支撑。","language":"zh","abstract_complete":true},"keyword_count":7,"keywords":[{"rank":1,"keyword":"工业表面缺陷","confidence":0.97,"source_position":{"start":-1,"end":-1},"adaptive_resource_match":true},{"rank":2,"keyword":"微小缺陷检测","confidence":0.95,"source_position":{"start":98,"end":104},"adaptive_resource_match":true},{"rank":3,"keyword":"多尺度特征金字塔","confidence":0.93,"source_position":{"start":70,"end":78},"adaptive_resource_match":false},{"rank":4,"keyword":"局部注意力增强","confidence":0.91,"source_position":{"start":79,"end":86},"adaptive_resource_match":false},{"rank":5,"keyword":"难样本重加权","confidence":0.89,"source_position":{"start":87,"end":93},"adaptive_resource_match":false},{"rank":6,"keyword":"跨层特征融合","confidence":0.87,"source_position":{"start":129,"end":135},"adaptive_resource_match":false},{"rank":7,"keyword":"智能制造质量检测","confidence":0.84,"source_position":{"start":199,"end":207},"adaptive_resource_match":true}],"input":{"input_type":"file","file_name":"中文关键词识别_工业表面缺陷摘要.txt","file_format":"TXT","file_size":"642 B","document_parse_status":"success","abstract_location_status":"success"}},"meta":{"adaptive_domain_resource_used":true,"adaptive_resource_term_count":9,"min_keywords":5,"max_keywords":8,"preserve_order":true,"weighting_method":"adaptive_domain_resource_dynamic_weighting","request_id":"req_keywords_zh_file_text1_202607190001","elapsed_ms":742}}},{"file_name":"中文关键词识别_城市遥感摘要.txt","size_bytes":561,"sha256":"51831e810114893596b51fac07aa970c5d5b4da076d312fe39684ad669a59c03","fnv1a32":"776a2c4a","result":{"code":200,"message":"success","data":{"tool":"中文科技文献关键词识别","input_type":"file","document":{"abstract":"城市地表覆盖类型存在光谱混叠、空间结构复杂和跨区域分布差异显著等问题，单一遥感数据难以实现稳定的精细分类。本文联合高分辨率光学影像、合成孔径雷达数据和地形辅助信息，构建多源遥感特征协同编码网络，通过跨模态对齐和区域上下文建模增强建筑、道路、植被与水体的区分能力。多城市实验结果表明，该方法能够提高地表覆盖分类精度和边界区域识别质量，为城市空间监测与土地利用调查提供可靠支持。","language":"zh","abstract_complete":true},"keyword_count":7,"keywords":[{"rank":1,"keyword":"城市地表覆盖","confidence":0.97,"source_position":{"start":0,"end":6},"adaptive_resource_match":true},{"rank":2,"keyword":"多源遥感","confidence":0.95,"source_position":{"start":84,"end":88},"adaptive_resource_match":true},{"rank":3,"keyword":"高分辨率光学影像","confidence":0.93,"source_position":{"start":57,"end":65},"adaptive_resource_match":false},{"rank":4,"keyword":"合成孔径雷达","confidence":0.92,"source_position":{"start":66,"end":72},"adaptive_resource_match":true},{"rank":5,"keyword":"跨模态对齐","confidence":0.9,"source_position":{"start":99,"end":104},"adaptive_resource_match":false},{"rank":6,"keyword":"区域上下文建模","confidence":0.88,"source_position":{"start":105,"end":112},"adaptive_resource_match":false},{"rank":7,"keyword":"城市空间监测","confidence":0.86,"source_position":{"start":167,"end":173},"adaptive_resource_match":true}],"input":{"input_type":"file","file_name":"中文关键词识别_城市遥感摘要.txt","file_format":"TXT","file_size":"561 B","document_parse_status":"success","abstract_location_status":"success"}},"meta":{"adaptive_domain_resource_used":true,"adaptive_resource_term_count":9,"min_keywords":5,"max_keywords":8,"preserve_order":true,"weighting_method":"adaptive_domain_resource_dynamic_weighting","request_id":"req_keywords_zh_file_text2_202607190001","elapsed_ms":742}}},{"file_name":"中文关键词识别_硅基负极材料摘要.txt","size_bytes":483,"sha256":"7ff4a130c25cb43707f5169a3ec97b27aa31d09655f6b0510fdef8da1e792a31","fnv1a32":"9a8f40bd","result":{"code":200,"message":"success","data":{"tool":"中文科技文献关键词识别","input_type":"file","document":{"abstract":"硅基负极材料具有较高理论比容量，但在充放电过程中容易发生显著体积膨胀，造成电极结构破坏和循环性能衰减。本文设计一种碳包覆多孔硅复合结构，通过纳米孔隙缓冲体积变化，并利用导电碳网络改善电子传输。电化学测试结果表明，该复合负极在高倍率条件下仍保持较高比容量和稳定循环性能，为高能量密度锂离子电池负极材料设计提供了新的技术路径。","language":"zh","abstract_complete":true},"keyword_count":7,"keywords":[{"rank":1,"keyword":"硅基负极材料","confidence":0.98,"source_position":{"start":0,"end":6},"adaptive_resource_match":true},{"rank":2,"keyword":"体积膨胀","confidence":0.94,"source_position":{"start":30,"end":34},"adaptive_resource_match":true},{"rank":3,"keyword":"碳包覆多孔硅","confidence":0.93,"source_position":{"start":57,"end":63},"adaptive_resource_match":false},{"rank":4,"keyword":"纳米孔隙","confidence":0.9,"source_position":{"start":70,"end":74},"adaptive_resource_match":false},{"rank":5,"keyword":"导电碳网络","confidence":0.89,"source_position":{"start":84,"end":89},"adaptive_resource_match":false},{"rank":6,"keyword":"循环性能","confidence":0.87,"source_position":{"start":44,"end":48},"adaptive_resource_match":true},{"rank":7,"keyword":"锂离子电池","confidence":0.86,"source_position":{"start":140,"end":145},"adaptive_resource_match":true}],"input":{"input_type":"file","file_name":"中文关键词识别_硅基负极材料摘要.txt","file_format":"TXT","file_size":"483 B","document_parse_status":"success","abstract_location_status":"success"}},"meta":{"adaptive_domain_resource_used":true,"adaptive_resource_term_count":9,"min_keywords":5,"max_keywords":8,"preserve_order":true,"weighting_method":"adaptive_domain_resource_dynamic_weighting","request_id":"req_keywords_zh_file_text3_202607190001","elapsed_ms":742}}}],"internalTerminologyResourceMode":"adaptive"},
      "en-keyword": {"group":"关键词识别工具","title":"英文科技文献关键词识别","documentType":"keyword","languageCode":"en","languageName":"英文","description":"从英文科研文献摘要中抽取专业关键词、缩写和主题短语。系统自动识别研究领域，并在算法内部自适应调用英文领域术语资源和标准术语映射规则，完成缩写识别、术语规范化与主题一致性校验；用户无需输入领域术语库或分类标准映射表。支持单文本、批量文本、单文件和批量文件。","features":"单文本与批量文本、单文件与批量文件、英文摘要自动定位、研究领域自动识别、专业缩写识别、英文短语边界识别、自适应领域术语资源、内部标准术语映射、术语规范化、结构化关键词与主题短语输出","scenarios":"英文论文标引、国际科技文献检索、跨语言术语规范化、专题情报分析、分类标准关联","endpoint":"/api/v1/keywords/en/text","textEndpoint":"/api/v1/keywords/en/text","batchTextEndpoint":"/api/v1/keywords/en/texts","fileEndpoint":"/api/v1/keywords/en/file","batchFileEndpoint":"/api/v1/keywords/en/files","inputModes":["text","batch-text","file","batch"],"supportsFileUpload":true,"supportsBatchUpload":true,"acceptedFiles":[".pdf",".docx",".txt"],"maxFileSizeMB":50,"maxBatchFiles":20,"maxBatchTexts":20,"documentTarget":"英文科研文献摘要","fileProcessingHint":"上传后自动解析文件并定位英文摘要，仅使用摘要执行关键词与主题短语识别","batchProcessingHint":"逐文件解析英文摘要，由系统自动识别领域并调用内部术语资源，返回结构化关键词与主题短语结果","params":[["input_type","string","required","输入方式，取值为 text、texts、file 或 files"],["abstract","string","conditional","当 input_type=text 时必填：英文科研文献摘要"],["texts","object[]","conditional","当 input_type=texts 时必填：每条包含 id 和 abstract，最多20条"],["file","file","conditional","当 input_type=file 时必填：PDF、DOCX 或 TXT 文件"],["files","file[]","conditional","当 input_type=files 时必填：最多20个文件"],["min_keywords","integer","optional","最少关键词或主题短语数量，默认5"],["max_keywords","integer","optional","最多关键词或主题短语数量，默认8"],["normalize_terms","boolean","optional","是否返回规范化术语，默认true"],["preserve_order","boolean","optional","是否尽量保持摘要出现顺序，默认true"],["max_concurrency","integer","optional","批量任务并发数，默认3"],["continue_on_error","boolean","optional","单条任务失败时是否继续处理，默认true"]],"payload":{"input_type":"text","abstract":"To fully utilize advances in omics technologies and achieve a comprehensive understanding of human diseases, novel computational methods are required for integrative analysis of multiple types of omics data. We present a multi-omics integrative method named Multi-Omics Graph cOnvolutional NETworks (MOGONET) for biomedical classification. MOGONET jointly explores omics-specific learning and cross-omics correlation learning for effective multi-omics data classification. Experiments using mRNA expression data, DNA methylation data, and microRNA expression data show improved classification performance. The method can also identify important biomarkers related to the investigated biomedical problems.","min_keywords":5,"max_keywords":8,"normalize_terms":true,"preserve_order":true},"demoText":"To fully utilize advances in omics technologies and achieve a comprehensive understanding of human diseases, novel computational methods are required for integrative analysis of multiple types of omics data. We present a multi-omics integrative method named Multi-Omics Graph cOnvolutional NETworks (MOGONET) for biomedical classification. MOGONET jointly explores omics-specific learning and cross-omics correlation learning for effective multi-omics data classification. Experiments using mRNA expression data, DNA methylation data, and microRNA expression data show improved classification performance. The method can also identify important biomarkers related to the investigated biomedical problems.","demoBatchTexts":[{"id":"text1","text":"To fully utilize advances in omics technologies and achieve a comprehensive understanding of human diseases, novel computational methods are required for integrative analysis of multiple types of omics data. We present a multi-omics integrative method named Multi-Omics Graph cOnvolutional NETworks (MOGONET) for biomedical classification. MOGONET jointly explores omics-specific learning and cross-omics correlation learning for effective multi-omics data classification. Experiments using mRNA expression data, DNA methylation data, and microRNA expression data show improved classification performance. The method can also identify important biomarkers related to the investigated biomedical problems."},{"id":"text2","text":"Multivariate time series analysis remains challenging because of high dimensionality, dynamic temporal patterns, and complex interactions among variables. This paper proposes HGTS-Former, a hypergraph-based Transformer backbone for multivariate time series analysis. The method normalizes and embeds patches into tokens, applies multi-head self-attention, constructs hierarchical hypergraphs to aggregate temporal patterns and cross-variable relations, and converts hyperedge features into node representations. Experiments on representative time series tasks and public datasets validate the effectiveness of the proposed model."},{"id":"text3","text":"Time series anomaly detection aims to identify samples that deviate from normal distributions and is important in many real-world applications. Existing methods are mostly centralized and domain-specific, making them difficult to generalize across decentralized institutions with privacy constraints. This paper proposes FAST-MAD, a resource-aware framework for federated multivariate time series anomaly detection. It combines multi-resolution transformation, frequency-oriented patching, inter-series interaction, modularized model separation, sharded federated training, and decomposed client-server alignment. Experiments demonstrate effective anomaly detection under heterogeneous data distributions and constrained computational resources."}],"demoBatchResults":[{"id":"text1","text":"To fully utilize advances in omics technologies and achieve a comprehensive understanding of human diseases, novel computational methods are required for integrative analysis of multiple types of omics data. We present a multi-omics integrative method named Multi-Omics Graph cOnvolutional NETworks (MOGONET) for biomedical classification. MOGONET jointly explores omics-specific learning and cross-omics correlation learning for effective multi-omics data classification. Experiments using mRNA expression data, DNA methylation data, and microRNA expression data show improved classification performance. The method can also identify important biomarkers related to the investigated biomedical problems.","keyword_count":7,"keywords":[{"rank":1,"term":"integrative analysis of multiple types of omics data","type":"topic_phrase","normalized_term":"multi-omics data integration","confidence":0.98,"source_position":{"start":154,"end":206},"adaptive_resource_match":true},{"rank":2,"term":"Multi-Omics Graph cOnvolutional NETworks","type":"keyword","normalized_term":"MOGONET","confidence":0.97,"source_position":{"start":258,"end":298},"adaptive_resource_match":true},{"rank":3,"term":"biomedical classification","type":"topic_phrase","normalized_term":"biomedical classification","confidence":0.95,"source_position":{"start":313,"end":338},"adaptive_resource_match":true},{"rank":4,"term":"cross-omics correlation learning","type":"keyword","normalized_term":"cross-omics correlation learning","confidence":0.93,"source_position":{"start":393,"end":425},"adaptive_resource_match":true},{"rank":5,"term":"mRNA expression data","type":"keyword","normalized_term":"mRNA expression data","confidence":0.9,"source_position":{"start":491,"end":511},"adaptive_resource_match":true},{"rank":6,"term":"DNA methylation data","type":"keyword","normalized_term":"DNA methylation data","confidence":0.89,"source_position":{"start":513,"end":533},"adaptive_resource_match":true},{"rank":7,"term":"important biomarkers","type":"topic_phrase","normalized_term":"biomarker identification","confidence":0.87,"source_position":{"start":635,"end":655},"adaptive_resource_match":true}]},{"id":"text2","text":"Multivariate time series analysis remains challenging because of high dimensionality, dynamic temporal patterns, and complex interactions among variables. This paper proposes HGTS-Former, a hypergraph-based Transformer backbone for multivariate time series analysis. The method normalizes and embeds patches into tokens, applies multi-head self-attention, constructs hierarchical hypergraphs to aggregate temporal patterns and cross-variable relations, and converts hyperedge features into node representations. Experiments on representative time series tasks and public datasets validate the effectiveness of the proposed model.","keyword_count":7,"keywords":[{"rank":1,"term":"multivariate time series analysis","type":"topic_phrase","normalized_term":"multivariate time series analysis","confidence":0.98,"source_position":{"start":232,"end":265},"adaptive_resource_match":true},{"rank":2,"term":"HGTS-Former","type":"keyword","normalized_term":"HGTS-Former","confidence":0.96,"source_position":{"start":175,"end":186},"adaptive_resource_match":true},{"rank":3,"term":"hypergraph-based Transformer backbone","type":"topic_phrase","normalized_term":"hypergraph Transformer","confidence":0.95,"source_position":{"start":190,"end":227},"adaptive_resource_match":true},{"rank":4,"term":"multi-head self-attention","type":"keyword","normalized_term":"multi-head self-attention","confidence":0.92,"source_position":{"start":329,"end":354},"adaptive_resource_match":true},{"rank":5,"term":"hierarchical hypergraphs","type":"keyword","normalized_term":"hierarchical hypergraph","confidence":0.91,"source_position":{"start":367,"end":391},"adaptive_resource_match":true},{"rank":6,"term":"cross-variable relations","type":"topic_phrase","normalized_term":"cross-variable dependency","confidence":0.89,"source_position":{"start":427,"end":451},"adaptive_resource_match":true},{"rank":7,"term":"hyperedge features","type":"keyword","normalized_term":"hyperedge representation","confidence":0.86,"source_position":{"start":466,"end":484},"adaptive_resource_match":false}]},{"id":"text3","text":"Time series anomaly detection aims to identify samples that deviate from normal distributions and is important in many real-world applications. Existing methods are mostly centralized and domain-specific, making them difficult to generalize across decentralized institutions with privacy constraints. This paper proposes FAST-MAD, a resource-aware framework for federated multivariate time series anomaly detection. It combines multi-resolution transformation, frequency-oriented patching, inter-series interaction, modularized model separation, sharded federated training, and decomposed client-server alignment. Experiments demonstrate effective anomaly detection under heterogeneous data distributions and constrained computational resources.","keyword_count":7,"keywords":[{"rank":1,"term":"time series anomaly detection","type":"topic_phrase","normalized_term":"time series anomaly detection","confidence":0.98,"source_position":{"start":385,"end":414},"adaptive_resource_match":true},{"rank":2,"term":"FAST-MAD","type":"keyword","normalized_term":"FAST-MAD","confidence":0.96,"source_position":{"start":321,"end":329},"adaptive_resource_match":true},{"rank":3,"term":"federated multivariate time series anomaly detection","type":"topic_phrase","normalized_term":"federated anomaly detection","confidence":0.95,"source_position":{"start":362,"end":414},"adaptive_resource_match":true},{"rank":4,"term":"multi-resolution transformation","type":"keyword","normalized_term":"multi-resolution transformation","confidence":0.92,"source_position":{"start":428,"end":459},"adaptive_resource_match":true},{"rank":5,"term":"frequency-oriented patching","type":"keyword","normalized_term":"frequency-oriented patching","confidence":0.9,"source_position":{"start":461,"end":488},"adaptive_resource_match":true},{"rank":6,"term":"sharded federated training","type":"topic_phrase","normalized_term":"sharded federated learning","confidence":0.88,"source_position":{"start":546,"end":572},"adaptive_resource_match":true},{"rank":7,"term":"client-server alignment","type":"topic_phrase","normalized_term":"client-server alignment","confidence":0.86,"source_position":{"start":589,"end":612},"adaptive_resource_match":false}]}],"demoTextResult":{"code":200,"message":"success","data":{"tool":"英文科技文献关键词识别","input_type":"text","document":{"abstract":"To fully utilize advances in omics technologies and achieve a comprehensive understanding of human diseases, novel computational methods are required for integrative analysis of multiple types of omics data. We present a multi-omics integrative method named Multi-Omics Graph cOnvolutional NETworks (MOGONET) for biomedical classification. MOGONET jointly explores omics-specific learning and cross-omics correlation learning for effective multi-omics data classification. Experiments using mRNA expression data, DNA methylation data, and microRNA expression data show improved classification performance. The method can also identify important biomarkers related to the investigated biomedical problems.","language":"en","abstract_complete":true},"term_count":7,"keywords_or_topic_phrases":[{"rank":1,"term":"integrative analysis of multiple types of omics data","type":"topic_phrase","normalized_term":"multi-omics data integration","confidence":0.98,"source_position":{"start":154,"end":206},"adaptive_resource_match":true},{"rank":2,"term":"Multi-Omics Graph cOnvolutional NETworks","type":"keyword","normalized_term":"MOGONET","confidence":0.97,"source_position":{"start":258,"end":298},"adaptive_resource_match":true},{"rank":3,"term":"biomedical classification","type":"topic_phrase","normalized_term":"biomedical classification","confidence":0.95,"source_position":{"start":313,"end":338},"adaptive_resource_match":true},{"rank":4,"term":"cross-omics correlation learning","type":"keyword","normalized_term":"cross-omics correlation learning","confidence":0.93,"source_position":{"start":393,"end":425},"adaptive_resource_match":true},{"rank":5,"term":"mRNA expression data","type":"keyword","normalized_term":"mRNA expression data","confidence":0.9,"source_position":{"start":491,"end":511},"adaptive_resource_match":true},{"rank":6,"term":"DNA methylation data","type":"keyword","normalized_term":"DNA methylation data","confidence":0.89,"source_position":{"start":513,"end":533},"adaptive_resource_match":true},{"rank":7,"term":"important biomarkers","type":"topic_phrase","normalized_term":"biomarker identification","confidence":0.87,"source_position":{"start":635,"end":655},"adaptive_resource_match":true}]},"meta":{"adaptive_domain_resource_used":true,"adaptive_resource_term_count":12,"internal_taxonomy_normalization_used":true,"internal_taxonomy_rule_count":13,"min_keywords":5,"max_keywords":8,"normalize_terms":true,"preserve_order":true,"request_id":"req_keywords_en_text_202607190001","elapsed_ms":816}},"demoBatchTextResult":{"code":200,"message":"batch_completed","data":{"batch_id":"batch_keywords_en_text_202607190001","input_type":"texts","total":3,"success_count":3,"failed_count":0,"results":[{"index":1,"input_id":"text1","status":"success","code":200,"result":{"tool":"英文科技文献关键词识别","input_type":"text","document":{"abstract":"To fully utilize advances in omics technologies and achieve a comprehensive understanding of human diseases, novel computational methods are required for integrative analysis of multiple types of omics data. We present a multi-omics integrative method named Multi-Omics Graph cOnvolutional NETworks (MOGONET) for biomedical classification. MOGONET jointly explores omics-specific learning and cross-omics correlation learning for effective multi-omics data classification. Experiments using mRNA expression data, DNA methylation data, and microRNA expression data show improved classification performance. The method can also identify important biomarkers related to the investigated biomedical problems.","language":"en","abstract_complete":true},"term_count":7,"keywords_or_topic_phrases":[{"rank":1,"term":"integrative analysis of multiple types of omics data","type":"topic_phrase","normalized_term":"multi-omics data integration","confidence":0.98,"source_position":{"start":154,"end":206},"adaptive_resource_match":true},{"rank":2,"term":"Multi-Omics Graph cOnvolutional NETworks","type":"keyword","normalized_term":"MOGONET","confidence":0.97,"source_position":{"start":258,"end":298},"adaptive_resource_match":true},{"rank":3,"term":"biomedical classification","type":"topic_phrase","normalized_term":"biomedical classification","confidence":0.95,"source_position":{"start":313,"end":338},"adaptive_resource_match":true},{"rank":4,"term":"cross-omics correlation learning","type":"keyword","normalized_term":"cross-omics correlation learning","confidence":0.93,"source_position":{"start":393,"end":425},"adaptive_resource_match":true},{"rank":5,"term":"mRNA expression data","type":"keyword","normalized_term":"mRNA expression data","confidence":0.9,"source_position":{"start":491,"end":511},"adaptive_resource_match":true},{"rank":6,"term":"DNA methylation data","type":"keyword","normalized_term":"DNA methylation data","confidence":0.89,"source_position":{"start":513,"end":533},"adaptive_resource_match":true},{"rank":7,"term":"important biomarkers","type":"topic_phrase","normalized_term":"biomarker identification","confidence":0.87,"source_position":{"start":635,"end":655},"adaptive_resource_match":true}]}},{"index":2,"input_id":"text2","status":"success","code":200,"result":{"tool":"英文科技文献关键词识别","input_type":"text","document":{"abstract":"Multivariate time series analysis remains challenging because of high dimensionality, dynamic temporal patterns, and complex interactions among variables. This paper proposes HGTS-Former, a hypergraph-based Transformer backbone for multivariate time series analysis. The method normalizes and embeds patches into tokens, applies multi-head self-attention, constructs hierarchical hypergraphs to aggregate temporal patterns and cross-variable relations, and converts hyperedge features into node representations. Experiments on representative time series tasks and public datasets validate the effectiveness of the proposed model.","language":"en","abstract_complete":true},"term_count":7,"keywords_or_topic_phrases":[{"rank":1,"term":"multivariate time series analysis","type":"topic_phrase","normalized_term":"multivariate time series analysis","confidence":0.98,"source_position":{"start":232,"end":265},"adaptive_resource_match":true},{"rank":2,"term":"HGTS-Former","type":"keyword","normalized_term":"HGTS-Former","confidence":0.96,"source_position":{"start":175,"end":186},"adaptive_resource_match":true},{"rank":3,"term":"hypergraph-based Transformer backbone","type":"topic_phrase","normalized_term":"hypergraph Transformer","confidence":0.95,"source_position":{"start":190,"end":227},"adaptive_resource_match":true},{"rank":4,"term":"multi-head self-attention","type":"keyword","normalized_term":"multi-head self-attention","confidence":0.92,"source_position":{"start":329,"end":354},"adaptive_resource_match":true},{"rank":5,"term":"hierarchical hypergraphs","type":"keyword","normalized_term":"hierarchical hypergraph","confidence":0.91,"source_position":{"start":367,"end":391},"adaptive_resource_match":true},{"rank":6,"term":"cross-variable relations","type":"topic_phrase","normalized_term":"cross-variable dependency","confidence":0.89,"source_position":{"start":427,"end":451},"adaptive_resource_match":true},{"rank":7,"term":"hyperedge features","type":"keyword","normalized_term":"hyperedge representation","confidence":0.86,"source_position":{"start":466,"end":484},"adaptive_resource_match":false}]}},{"index":3,"input_id":"text3","status":"success","code":200,"result":{"tool":"英文科技文献关键词识别","input_type":"text","document":{"abstract":"Time series anomaly detection aims to identify samples that deviate from normal distributions and is important in many real-world applications. Existing methods are mostly centralized and domain-specific, making them difficult to generalize across decentralized institutions with privacy constraints. This paper proposes FAST-MAD, a resource-aware framework for federated multivariate time series anomaly detection. It combines multi-resolution transformation, frequency-oriented patching, inter-series interaction, modularized model separation, sharded federated training, and decomposed client-server alignment. Experiments demonstrate effective anomaly detection under heterogeneous data distributions and constrained computational resources.","language":"en","abstract_complete":true},"term_count":7,"keywords_or_topic_phrases":[{"rank":1,"term":"time series anomaly detection","type":"topic_phrase","normalized_term":"time series anomaly detection","confidence":0.98,"source_position":{"start":385,"end":414},"adaptive_resource_match":true},{"rank":2,"term":"FAST-MAD","type":"keyword","normalized_term":"FAST-MAD","confidence":0.96,"source_position":{"start":321,"end":329},"adaptive_resource_match":true},{"rank":3,"term":"federated multivariate time series anomaly detection","type":"topic_phrase","normalized_term":"federated anomaly detection","confidence":0.95,"source_position":{"start":362,"end":414},"adaptive_resource_match":true},{"rank":4,"term":"multi-resolution transformation","type":"keyword","normalized_term":"multi-resolution transformation","confidence":0.92,"source_position":{"start":428,"end":459},"adaptive_resource_match":true},{"rank":5,"term":"frequency-oriented patching","type":"keyword","normalized_term":"frequency-oriented patching","confidence":0.9,"source_position":{"start":461,"end":488},"adaptive_resource_match":true},{"rank":6,"term":"sharded federated training","type":"topic_phrase","normalized_term":"sharded federated learning","confidence":0.88,"source_position":{"start":546,"end":572},"adaptive_resource_match":true},{"rank":7,"term":"client-server alignment","type":"topic_phrase","normalized_term":"client-server alignment","confidence":0.86,"source_position":{"start":589,"end":612},"adaptive_resource_match":false}]}}]},"meta":{"adaptive_domain_resource_used":true,"adaptive_resource_term_count":12,"internal_taxonomy_normalization_used":true,"internal_taxonomy_rule_count":13,"min_keywords":5,"max_keywords":8,"normalize_terms":true,"preserve_order":true,"max_concurrency":3,"elapsed_ms":1912}},"demoFileResult":{"code":200,"message":"success","data":{"tool":"英文科技文献关键词识别","input_type":"file","document":{"abstract":"To fully utilize advances in omics technologies and achieve a comprehensive understanding of human diseases, novel computational methods are required for integrative analysis of multiple types of omics data. We present a multi-omics integrative method named Multi-Omics Graph cOnvolutional NETworks (MOGONET) for biomedical classification. MOGONET jointly explores omics-specific learning and cross-omics correlation learning for effective multi-omics data classification. Experiments using mRNA expression data, DNA methylation data, and microRNA expression data show improved classification performance. The method can also identify important biomarkers related to the investigated biomedical problems.","language":"en","abstract_complete":true},"term_count":7,"keywords_or_topic_phrases":[{"rank":1,"term":"integrative analysis of multiple types of omics data","type":"topic_phrase","normalized_term":"multi-omics data integration","confidence":0.98,"source_position":{"start":154,"end":206},"adaptive_resource_match":true},{"rank":2,"term":"Multi-Omics Graph cOnvolutional NETworks","type":"keyword","normalized_term":"MOGONET","confidence":0.97,"source_position":{"start":258,"end":298},"adaptive_resource_match":true},{"rank":3,"term":"biomedical classification","type":"topic_phrase","normalized_term":"biomedical classification","confidence":0.95,"source_position":{"start":313,"end":338},"adaptive_resource_match":true},{"rank":4,"term":"cross-omics correlation learning","type":"keyword","normalized_term":"cross-omics correlation learning","confidence":0.93,"source_position":{"start":393,"end":425},"adaptive_resource_match":true},{"rank":5,"term":"mRNA expression data","type":"keyword","normalized_term":"mRNA expression data","confidence":0.9,"source_position":{"start":491,"end":511},"adaptive_resource_match":true},{"rank":6,"term":"DNA methylation data","type":"keyword","normalized_term":"DNA methylation data","confidence":0.89,"source_position":{"start":513,"end":533},"adaptive_resource_match":true},{"rank":7,"term":"important biomarkers","type":"topic_phrase","normalized_term":"biomarker identification","confidence":0.87,"source_position":{"start":635,"end":655},"adaptive_resource_match":true}],"input":{"input_type":"file","file_name":"MOGONET.pdf","file_format":"PDF","file_size":"1322087 B","document_parse_status":"success","abstract_location_status":"success"}},"meta":{"adaptive_domain_resource_used":true,"adaptive_resource_term_count":12,"internal_taxonomy_normalization_used":true,"internal_taxonomy_rule_count":13,"min_keywords":5,"max_keywords":8,"normalize_terms":true,"preserve_order":true,"request_id":"req_keywords_en_file_text1_202607190001","elapsed_ms":816}},"demoBatchFileResult":{"code":200,"message":"batch_completed","data":{"batch_id":"batch_keywords_en_file_202607190001","input_type":"files","total":3,"success_count":3,"failed_count":0,"results":[{"index":1,"file_name":"MOGONET.pdf","status":"success","code":200,"result":{"tool":"英文科技文献关键词识别","input_type":"file","document":{"abstract":"To fully utilize advances in omics technologies and achieve a comprehensive understanding of human diseases, novel computational methods are required for integrative analysis of multiple types of omics data. We present a multi-omics integrative method named Multi-Omics Graph cOnvolutional NETworks (MOGONET) for biomedical classification. MOGONET jointly explores omics-specific learning and cross-omics correlation learning for effective multi-omics data classification. Experiments using mRNA expression data, DNA methylation data, and microRNA expression data show improved classification performance. The method can also identify important biomarkers related to the investigated biomedical problems.","language":"en","abstract_complete":true},"term_count":7,"keywords_or_topic_phrases":[{"rank":1,"term":"integrative analysis of multiple types of omics data","type":"topic_phrase","normalized_term":"multi-omics data integration","confidence":0.98,"source_position":{"start":154,"end":206},"adaptive_resource_match":true},{"rank":2,"term":"Multi-Omics Graph cOnvolutional NETworks","type":"keyword","normalized_term":"MOGONET","confidence":0.97,"source_position":{"start":258,"end":298},"adaptive_resource_match":true},{"rank":3,"term":"biomedical classification","type":"topic_phrase","normalized_term":"biomedical classification","confidence":0.95,"source_position":{"start":313,"end":338},"adaptive_resource_match":true},{"rank":4,"term":"cross-omics correlation learning","type":"keyword","normalized_term":"cross-omics correlation learning","confidence":0.93,"source_position":{"start":393,"end":425},"adaptive_resource_match":true},{"rank":5,"term":"mRNA expression data","type":"keyword","normalized_term":"mRNA expression data","confidence":0.9,"source_position":{"start":491,"end":511},"adaptive_resource_match":true},{"rank":6,"term":"DNA methylation data","type":"keyword","normalized_term":"DNA methylation data","confidence":0.89,"source_position":{"start":513,"end":533},"adaptive_resource_match":true},{"rank":7,"term":"important biomarkers","type":"topic_phrase","normalized_term":"biomarker identification","confidence":0.87,"source_position":{"start":635,"end":655},"adaptive_resource_match":true}]}},{"index":2,"file_name":"HGTS-Former_keyword_abstract.txt","status":"success","code":200,"result":{"tool":"英文科技文献关键词识别","input_type":"file","document":{"abstract":"Multivariate time series analysis remains challenging because of high dimensionality, dynamic temporal patterns, and complex interactions among variables. This paper proposes HGTS-Former, a hypergraph-based Transformer backbone for multivariate time series analysis. The method normalizes and embeds patches into tokens, applies multi-head self-attention, constructs hierarchical hypergraphs to aggregate temporal patterns and cross-variable relations, and converts hyperedge features into node representations. Experiments on representative time series tasks and public datasets validate the effectiveness of the proposed model.","language":"en","abstract_complete":true},"term_count":7,"keywords_or_topic_phrases":[{"rank":1,"term":"multivariate time series analysis","type":"topic_phrase","normalized_term":"multivariate time series analysis","confidence":0.98,"source_position":{"start":232,"end":265},"adaptive_resource_match":true},{"rank":2,"term":"HGTS-Former","type":"keyword","normalized_term":"HGTS-Former","confidence":0.96,"source_position":{"start":175,"end":186},"adaptive_resource_match":true},{"rank":3,"term":"hypergraph-based Transformer backbone","type":"topic_phrase","normalized_term":"hypergraph Transformer","confidence":0.95,"source_position":{"start":190,"end":227},"adaptive_resource_match":true},{"rank":4,"term":"multi-head self-attention","type":"keyword","normalized_term":"multi-head self-attention","confidence":0.92,"source_position":{"start":329,"end":354},"adaptive_resource_match":true},{"rank":5,"term":"hierarchical hypergraphs","type":"keyword","normalized_term":"hierarchical hypergraph","confidence":0.91,"source_position":{"start":367,"end":391},"adaptive_resource_match":true},{"rank":6,"term":"cross-variable relations","type":"topic_phrase","normalized_term":"cross-variable dependency","confidence":0.89,"source_position":{"start":427,"end":451},"adaptive_resource_match":true},{"rank":7,"term":"hyperedge features","type":"keyword","normalized_term":"hyperedge representation","confidence":0.86,"source_position":{"start":466,"end":484},"adaptive_resource_match":false}]}},{"index":3,"file_name":"FAST-MAD_keyword_abstract.txt","status":"success","code":200,"result":{"tool":"英文科技文献关键词识别","input_type":"file","document":{"abstract":"Time series anomaly detection aims to identify samples that deviate from normal distributions and is important in many real-world applications. Existing methods are mostly centralized and domain-specific, making them difficult to generalize across decentralized institutions with privacy constraints. This paper proposes FAST-MAD, a resource-aware framework for federated multivariate time series anomaly detection. It combines multi-resolution transformation, frequency-oriented patching, inter-series interaction, modularized model separation, sharded federated training, and decomposed client-server alignment. Experiments demonstrate effective anomaly detection under heterogeneous data distributions and constrained computational resources.","language":"en","abstract_complete":true},"term_count":7,"keywords_or_topic_phrases":[{"rank":1,"term":"time series anomaly detection","type":"topic_phrase","normalized_term":"time series anomaly detection","confidence":0.98,"source_position":{"start":385,"end":414},"adaptive_resource_match":true},{"rank":2,"term":"FAST-MAD","type":"keyword","normalized_term":"FAST-MAD","confidence":0.96,"source_position":{"start":321,"end":329},"adaptive_resource_match":true},{"rank":3,"term":"federated multivariate time series anomaly detection","type":"topic_phrase","normalized_term":"federated anomaly detection","confidence":0.95,"source_position":{"start":362,"end":414},"adaptive_resource_match":true},{"rank":4,"term":"multi-resolution transformation","type":"keyword","normalized_term":"multi-resolution transformation","confidence":0.92,"source_position":{"start":428,"end":459},"adaptive_resource_match":true},{"rank":5,"term":"frequency-oriented patching","type":"keyword","normalized_term":"frequency-oriented patching","confidence":0.9,"source_position":{"start":461,"end":488},"adaptive_resource_match":true},{"rank":6,"term":"sharded federated training","type":"topic_phrase","normalized_term":"sharded federated learning","confidence":0.88,"source_position":{"start":546,"end":572},"adaptive_resource_match":true},{"rank":7,"term":"client-server alignment","type":"topic_phrase","normalized_term":"client-server alignment","confidence":0.86,"source_position":{"start":589,"end":612},"adaptive_resource_match":false}]}}]},"meta":{"adaptive_domain_resource_used":true,"adaptive_resource_term_count":12,"internal_taxonomy_normalization_used":true,"internal_taxonomy_rule_count":13,"min_keywords":5,"max_keywords":8,"normalize_terms":true,"preserve_order":true,"max_concurrency":3,"elapsed_ms":2784}},"response":{"code":200,"message":"batch_completed","data":{"batch_id":"batch_keywords_en_file_202607190001","input_type":"files","total":3,"success_count":3,"failed_count":0,"results":[{"index":1,"file_name":"MOGONET.pdf","status":"success","code":200,"result":{"tool":"英文科技文献关键词识别","input_type":"file","document":{"abstract":"To fully utilize advances in omics technologies and achieve a comprehensive understanding of human diseases, novel computational methods are required for integrative analysis of multiple types of omics data. We present a multi-omics integrative method named Multi-Omics Graph cOnvolutional NETworks (MOGONET) for biomedical classification. MOGONET jointly explores omics-specific learning and cross-omics correlation learning for effective multi-omics data classification. Experiments using mRNA expression data, DNA methylation data, and microRNA expression data show improved classification performance. The method can also identify important biomarkers related to the investigated biomedical problems.","language":"en","abstract_complete":true},"term_count":7,"keywords_or_topic_phrases":[{"rank":1,"term":"integrative analysis of multiple types of omics data","type":"topic_phrase","normalized_term":"multi-omics data integration","confidence":0.98,"source_position":{"start":154,"end":206},"adaptive_resource_match":true},{"rank":2,"term":"Multi-Omics Graph cOnvolutional NETworks","type":"keyword","normalized_term":"MOGONET","confidence":0.97,"source_position":{"start":258,"end":298},"adaptive_resource_match":true},{"rank":3,"term":"biomedical classification","type":"topic_phrase","normalized_term":"biomedical classification","confidence":0.95,"source_position":{"start":313,"end":338},"adaptive_resource_match":true},{"rank":4,"term":"cross-omics correlation learning","type":"keyword","normalized_term":"cross-omics correlation learning","confidence":0.93,"source_position":{"start":393,"end":425},"adaptive_resource_match":true},{"rank":5,"term":"mRNA expression data","type":"keyword","normalized_term":"mRNA expression data","confidence":0.9,"source_position":{"start":491,"end":511},"adaptive_resource_match":true},{"rank":6,"term":"DNA methylation data","type":"keyword","normalized_term":"DNA methylation data","confidence":0.89,"source_position":{"start":513,"end":533},"adaptive_resource_match":true},{"rank":7,"term":"important biomarkers","type":"topic_phrase","normalized_term":"biomarker identification","confidence":0.87,"source_position":{"start":635,"end":655},"adaptive_resource_match":true}]}},{"index":2,"file_name":"HGTS-Former_keyword_abstract.txt","status":"success","code":200,"result":{"tool":"英文科技文献关键词识别","input_type":"file","document":{"abstract":"Multivariate time series analysis remains challenging because of high dimensionality, dynamic temporal patterns, and complex interactions among variables. This paper proposes HGTS-Former, a hypergraph-based Transformer backbone for multivariate time series analysis. The method normalizes and embeds patches into tokens, applies multi-head self-attention, constructs hierarchical hypergraphs to aggregate temporal patterns and cross-variable relations, and converts hyperedge features into node representations. Experiments on representative time series tasks and public datasets validate the effectiveness of the proposed model.","language":"en","abstract_complete":true},"term_count":7,"keywords_or_topic_phrases":[{"rank":1,"term":"multivariate time series analysis","type":"topic_phrase","normalized_term":"multivariate time series analysis","confidence":0.98,"source_position":{"start":232,"end":265},"adaptive_resource_match":true},{"rank":2,"term":"HGTS-Former","type":"keyword","normalized_term":"HGTS-Former","confidence":0.96,"source_position":{"start":175,"end":186},"adaptive_resource_match":true},{"rank":3,"term":"hypergraph-based Transformer backbone","type":"topic_phrase","normalized_term":"hypergraph Transformer","confidence":0.95,"source_position":{"start":190,"end":227},"adaptive_resource_match":true},{"rank":4,"term":"multi-head self-attention","type":"keyword","normalized_term":"multi-head self-attention","confidence":0.92,"source_position":{"start":329,"end":354},"adaptive_resource_match":true},{"rank":5,"term":"hierarchical hypergraphs","type":"keyword","normalized_term":"hierarchical hypergraph","confidence":0.91,"source_position":{"start":367,"end":391},"adaptive_resource_match":true},{"rank":6,"term":"cross-variable relations","type":"topic_phrase","normalized_term":"cross-variable dependency","confidence":0.89,"source_position":{"start":427,"end":451},"adaptive_resource_match":true},{"rank":7,"term":"hyperedge features","type":"keyword","normalized_term":"hyperedge representation","confidence":0.86,"source_position":{"start":466,"end":484},"adaptive_resource_match":false}]}},{"index":3,"file_name":"FAST-MAD_keyword_abstract.txt","status":"success","code":200,"result":{"tool":"英文科技文献关键词识别","input_type":"file","document":{"abstract":"Time series anomaly detection aims to identify samples that deviate from normal distributions and is important in many real-world applications. Existing methods are mostly centralized and domain-specific, making them difficult to generalize across decentralized institutions with privacy constraints. This paper proposes FAST-MAD, a resource-aware framework for federated multivariate time series anomaly detection. It combines multi-resolution transformation, frequency-oriented patching, inter-series interaction, modularized model separation, sharded federated training, and decomposed client-server alignment. Experiments demonstrate effective anomaly detection under heterogeneous data distributions and constrained computational resources.","language":"en","abstract_complete":true},"term_count":7,"keywords_or_topic_phrases":[{"rank":1,"term":"time series anomaly detection","type":"topic_phrase","normalized_term":"time series anomaly detection","confidence":0.98,"source_position":{"start":385,"end":414},"adaptive_resource_match":true},{"rank":2,"term":"FAST-MAD","type":"keyword","normalized_term":"FAST-MAD","confidence":0.96,"source_position":{"start":321,"end":329},"adaptive_resource_match":true},{"rank":3,"term":"federated multivariate time series anomaly detection","type":"topic_phrase","normalized_term":"federated anomaly detection","confidence":0.95,"source_position":{"start":362,"end":414},"adaptive_resource_match":true},{"rank":4,"term":"multi-resolution transformation","type":"keyword","normalized_term":"multi-resolution transformation","confidence":0.92,"source_position":{"start":428,"end":459},"adaptive_resource_match":true},{"rank":5,"term":"frequency-oriented patching","type":"keyword","normalized_term":"frequency-oriented patching","confidence":0.9,"source_position":{"start":461,"end":488},"adaptive_resource_match":true},{"rank":6,"term":"sharded federated training","type":"topic_phrase","normalized_term":"sharded federated learning","confidence":0.88,"source_position":{"start":546,"end":572},"adaptive_resource_match":true},{"rank":7,"term":"client-server alignment","type":"topic_phrase","normalized_term":"client-server alignment","confidence":0.86,"source_position":{"start":589,"end":612},"adaptive_resource_match":false}]}}]},"meta":{"adaptive_domain_resource_used":true,"adaptive_resource_term_count":12,"internal_taxonomy_normalization_used":true,"internal_taxonomy_rule_count":13,"min_keywords":5,"max_keywords":8,"normalize_terms":true,"preserve_order":true,"max_concurrency":3,"elapsed_ms":2784}},"sampleFileName":"MOGONET.pdf","sampleFileSize":"1322087 B","demoFileSizeBytes":1322087,"demoFileSha256":"6f6f55bc4c5556fdbdad09d2d51ca05bd8da9adb8e992d5fb0b85cac0f28cda5","demoFileFnv1a32":"15a27ddf","batchSampleFileNames":["MOGONET.pdf","HGTS-Former_keyword_abstract.txt","FAST-MAD_keyword_abstract.txt"],"demoFileFixtures":[{"file_name":"MOGONET.pdf","size_bytes":1322087,"sha256":"6f6f55bc4c5556fdbdad09d2d51ca05bd8da9adb8e992d5fb0b85cac0f28cda5","fnv1a32":"15a27ddf","result":{"code":200,"message":"success","data":{"tool":"英文科技文献关键词识别","input_type":"file","document":{"abstract":"To fully utilize advances in omics technologies and achieve a comprehensive understanding of human diseases, novel computational methods are required for integrative analysis of multiple types of omics data. We present a multi-omics integrative method named Multi-Omics Graph cOnvolutional NETworks (MOGONET) for biomedical classification. MOGONET jointly explores omics-specific learning and cross-omics correlation learning for effective multi-omics data classification. Experiments using mRNA expression data, DNA methylation data, and microRNA expression data show improved classification performance. The method can also identify important biomarkers related to the investigated biomedical problems.","language":"en","abstract_complete":true},"term_count":7,"keywords_or_topic_phrases":[{"rank":1,"term":"integrative analysis of multiple types of omics data","type":"topic_phrase","normalized_term":"multi-omics data integration","confidence":0.98,"source_position":{"start":154,"end":206},"adaptive_resource_match":true},{"rank":2,"term":"Multi-Omics Graph cOnvolutional NETworks","type":"keyword","normalized_term":"MOGONET","confidence":0.97,"source_position":{"start":258,"end":298},"adaptive_resource_match":true},{"rank":3,"term":"biomedical classification","type":"topic_phrase","normalized_term":"biomedical classification","confidence":0.95,"source_position":{"start":313,"end":338},"adaptive_resource_match":true},{"rank":4,"term":"cross-omics correlation learning","type":"keyword","normalized_term":"cross-omics correlation learning","confidence":0.93,"source_position":{"start":393,"end":425},"adaptive_resource_match":true},{"rank":5,"term":"mRNA expression data","type":"keyword","normalized_term":"mRNA expression data","confidence":0.9,"source_position":{"start":491,"end":511},"adaptive_resource_match":true},{"rank":6,"term":"DNA methylation data","type":"keyword","normalized_term":"DNA methylation data","confidence":0.89,"source_position":{"start":513,"end":533},"adaptive_resource_match":true},{"rank":7,"term":"important biomarkers","type":"topic_phrase","normalized_term":"biomarker identification","confidence":0.87,"source_position":{"start":635,"end":655},"adaptive_resource_match":true}],"input":{"input_type":"file","file_name":"MOGONET.pdf","file_format":"PDF","file_size":"1322087 B","document_parse_status":"success","abstract_location_status":"success"}},"meta":{"adaptive_domain_resource_used":true,"adaptive_resource_term_count":12,"internal_taxonomy_normalization_used":true,"internal_taxonomy_rule_count":13,"min_keywords":5,"max_keywords":8,"normalize_terms":true,"preserve_order":true,"request_id":"req_keywords_en_file_text1_202607190001","elapsed_ms":816}}},{"file_name":"HGTS-Former_keyword_abstract.txt","size_bytes":629,"sha256":"65613b96d98bbad18020e00a7593b91c707a0b82707a373f4ab7d13e725cc7f0","fnv1a32":"0e4ad9f4","result":{"code":200,"message":"success","data":{"tool":"英文科技文献关键词识别","input_type":"file","document":{"abstract":"Multivariate time series analysis remains challenging because of high dimensionality, dynamic temporal patterns, and complex interactions among variables. This paper proposes HGTS-Former, a hypergraph-based Transformer backbone for multivariate time series analysis. The method normalizes and embeds patches into tokens, applies multi-head self-attention, constructs hierarchical hypergraphs to aggregate temporal patterns and cross-variable relations, and converts hyperedge features into node representations. Experiments on representative time series tasks and public datasets validate the effectiveness of the proposed model.","language":"en","abstract_complete":true},"term_count":7,"keywords_or_topic_phrases":[{"rank":1,"term":"multivariate time series analysis","type":"topic_phrase","normalized_term":"multivariate time series analysis","confidence":0.98,"source_position":{"start":232,"end":265},"adaptive_resource_match":true},{"rank":2,"term":"HGTS-Former","type":"keyword","normalized_term":"HGTS-Former","confidence":0.96,"source_position":{"start":175,"end":186},"adaptive_resource_match":true},{"rank":3,"term":"hypergraph-based Transformer backbone","type":"topic_phrase","normalized_term":"hypergraph Transformer","confidence":0.95,"source_position":{"start":190,"end":227},"adaptive_resource_match":true},{"rank":4,"term":"multi-head self-attention","type":"keyword","normalized_term":"multi-head self-attention","confidence":0.92,"source_position":{"start":329,"end":354},"adaptive_resource_match":true},{"rank":5,"term":"hierarchical hypergraphs","type":"keyword","normalized_term":"hierarchical hypergraph","confidence":0.91,"source_position":{"start":367,"end":391},"adaptive_resource_match":true},{"rank":6,"term":"cross-variable relations","type":"topic_phrase","normalized_term":"cross-variable dependency","confidence":0.89,"source_position":{"start":427,"end":451},"adaptive_resource_match":true},{"rank":7,"term":"hyperedge features","type":"keyword","normalized_term":"hyperedge representation","confidence":0.86,"source_position":{"start":466,"end":484},"adaptive_resource_match":false}],"input":{"input_type":"file","file_name":"HGTS-Former_keyword_abstract.txt","file_format":"TXT","file_size":"629 B","document_parse_status":"success","abstract_location_status":"success"}},"meta":{"adaptive_domain_resource_used":true,"adaptive_resource_term_count":12,"internal_taxonomy_normalization_used":true,"internal_taxonomy_rule_count":13,"min_keywords":5,"max_keywords":8,"normalize_terms":true,"preserve_order":true,"request_id":"req_keywords_en_file_text2_202607190001","elapsed_ms":816}}},{"file_name":"FAST-MAD_keyword_abstract.txt","size_bytes":745,"sha256":"f3bbf6782319c56772c23c01d954bdc3b1e58696330f1598587e71bf71af9e70","fnv1a32":"cf5ba831","result":{"code":200,"message":"success","data":{"tool":"英文科技文献关键词识别","input_type":"file","document":{"abstract":"Time series anomaly detection aims to identify samples that deviate from normal distributions and is important in many real-world applications. Existing methods are mostly centralized and domain-specific, making them difficult to generalize across decentralized institutions with privacy constraints. This paper proposes FAST-MAD, a resource-aware framework for federated multivariate time series anomaly detection. It combines multi-resolution transformation, frequency-oriented patching, inter-series interaction, modularized model separation, sharded federated training, and decomposed client-server alignment. Experiments demonstrate effective anomaly detection under heterogeneous data distributions and constrained computational resources.","language":"en","abstract_complete":true},"term_count":7,"keywords_or_topic_phrases":[{"rank":1,"term":"time series anomaly detection","type":"topic_phrase","normalized_term":"time series anomaly detection","confidence":0.98,"source_position":{"start":385,"end":414},"adaptive_resource_match":true},{"rank":2,"term":"FAST-MAD","type":"keyword","normalized_term":"FAST-MAD","confidence":0.96,"source_position":{"start":321,"end":329},"adaptive_resource_match":true},{"rank":3,"term":"federated multivariate time series anomaly detection","type":"topic_phrase","normalized_term":"federated anomaly detection","confidence":0.95,"source_position":{"start":362,"end":414},"adaptive_resource_match":true},{"rank":4,"term":"multi-resolution transformation","type":"keyword","normalized_term":"multi-resolution transformation","confidence":0.92,"source_position":{"start":428,"end":459},"adaptive_resource_match":true},{"rank":5,"term":"frequency-oriented patching","type":"keyword","normalized_term":"frequency-oriented patching","confidence":0.9,"source_position":{"start":461,"end":488},"adaptive_resource_match":true},{"rank":6,"term":"sharded federated training","type":"topic_phrase","normalized_term":"sharded federated learning","confidence":0.88,"source_position":{"start":546,"end":572},"adaptive_resource_match":true},{"rank":7,"term":"client-server alignment","type":"topic_phrase","normalized_term":"client-server alignment","confidence":0.86,"source_position":{"start":589,"end":612},"adaptive_resource_match":false}],"input":{"input_type":"file","file_name":"FAST-MAD_keyword_abstract.txt","file_format":"TXT","file_size":"745 B","document_parse_status":"success","abstract_location_status":"success"}},"meta":{"adaptive_domain_resource_used":true,"adaptive_resource_term_count":12,"internal_taxonomy_normalization_used":true,"internal_taxonomy_rule_count":13,"min_keywords":5,"max_keywords":8,"normalize_terms":true,"preserve_order":true,"request_id":"req_keywords_en_file_text3_202607190001","elapsed_ms":816}}}],"internalTerminologyResourceMode":"adaptive"},
      "rq-detect": {"group":"研究问题识别工具","title":"研究问题句及短语识别","documentType":"research-question","languageCode":"zh","languageName":"中文","description":"从科技文献文件中识别研究空白、技术难点、核心任务和待解决问题，提取研究问题句与问题短语，并完成问题归并、主次关系组织、类型判定和统计分析。支持单文件和批量文件。","features":"单文件识别、批量文件识别、PDF/DOCX/TXT解析、章节结构提取、显式问题识别、隐式问题识别、研究问题短语抽取、主问题与子问题组织、章节和页码溯源、统计摘要","scenarios":"学位论文研究问题提炼、科研论文问题识别、批量科技文献分析、技术难点梳理、科研情报分析","endpoint":"/api/v1/research-question/file","fileEndpoint":"/api/v1/research-question/file","batchFileEndpoint":"/api/v1/research-question/files","inputModes":["file","batch"],"modeLabels":{"file":"单文件","batch":"批量文件"},"supportsFileUpload":true,"supportsBatchUpload":true,"acceptedFiles":[".pdf",".docx",".txt"],"maxFileSizeMB":50,"maxBatchFiles":20,"documentTarget":"文档章节与研究问题候选句","fileProcessingHint":"上传一个PDF、DOCX或TXT文件，完成文档解析、章节提取和研究问题识别","batchProcessingHint":"逐文件完成解析、章节提取、问题句识别、短语抽取、结构化归并和统计分析","params":[["file","file","conditional","单文件模式必填"],["files","file[]","conditional","批量文件模式必填，最多20个文件"],["format_requirements","object","required","文档分析范围、章节保留、问题类型、页码溯源及最低置信度等要求"],["language","string","optional","zh、en或auto"],["document_scope","string","optional","full_document、abstract_and_introduction或selected_sections"],["preserve_section_hierarchy","boolean","optional","是否保留章节层级"],["sentence_segmentation","string","optional","auto或presegmented"],["recognize_explicit_questions","boolean","optional","是否识别显式研究问题"],["recognize_implicit_questions","boolean","optional","是否识别隐式研究问题"],["return_source_section","boolean","optional","是否返回来源章节"],["return_page_number","boolean","optional","是否返回来源页码"],["minimum_confidence","number","optional","最低置信度，默认0.75"],["max_concurrency","integer","optional","批量并发数，默认3"],["continue_on_error","boolean","optional","单文件失败后是否继续"]],"payload":{"format_requirements":{"language":"zh","document_scope":"abstract_and_introduction","preserve_section_hierarchy":true,"sentence_segmentation":"auto","recognize_explicit_questions":true,"recognize_implicit_questions":true,"return_source_section":true,"return_page_number":true,"minimum_confidence":0.75}},"sampleFileName":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架.pdf","sampleFileSize":"3.17 MB","demoFileSizeBytes":3322216,"demoFileSha256":"4c51e28c11e4954d05e192a41337eb0e7d606c0b9097aeafa16ba858711b91c0","demoFileFnv1a32":"20540fb6","batchSampleFileNames":["基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架.pdf","社交媒体机器人检测_摘要问题片段.txt","社交媒体机器人检测_绪论问题片段.txt"],"demoFileResult":{"code":200,"message":"success","data":{"tool":"研究问题句及短语识别","input_type":"file","input":{"file_name":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架.pdf","file_format":"PDF","file_size":"3.17 MB","document_parse_status":"success","section_extraction_status":"success","text_format_validation_status":"success"},"document":{"title":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架","language":"zh","page_count":83,"analysis_scope":["摘要","1 绪论","1.2 国内外研究现状","1.3 本文主要工作及贡献"]},"research_question_sentences":[{"sentence_id":"S1","sentence":"因此，如何高效检测社交媒体机器人成为人工智能安全领域的重要课题。","expression_type":"explicit","trigger_patterns":["如何","重要课题"],"confidence":0.98,"position":{"page_number":7,"source_section":"摘要"}},{"sentence_id":"S2","sentence":"基于多模态的方法时常面临数据稀疏、噪声干扰、算力需求大等问题，且在模态融合过程中容易出现对部分模态的过度依赖，导致整体模型在缺少部分模态时性能显著下降。","expression_type":"implicit","trigger_patterns":["面临","问题","过度依赖","性能显著下降"],"confidence":0.96,"position":{"page_number":7,"source_section":"摘要"}},{"sentence_id":"S3","sentence":"基于社交图关系的方法过度依赖图关系型数据，但是该类数据常因隐私保护与平台接口限制难以获取，从而严重制约模型的性能与实际应用。","expression_type":"implicit","trigger_patterns":["过度依赖","难以获取","严重制约"],"confidence":0.97,"position":{"page_number":7,"source_section":"摘要"}},{"sentence_id":"S4","sentence":"当前主流的检测方法对数据获取、处理以及GPU算力要求较高，如何在增强模型检测性能的同时降低复杂度、提高效率成为关键研究方向。","expression_type":"explicit","trigger_patterns":["如何","关键研究方向"],"confidence":0.98,"position":{"page_number":15,"source_section":"1 绪论"}},{"sentence_id":"S5","sentence":"随着数据规模不断扩大，不同模态之间在稀疏性和表达能力上的差异日益突出，导致融合过程中面临信息不均衡、模型结构复杂和单一模态偏倚等问题。","expression_type":"implicit","trigger_patterns":["差异日益突出","信息不均衡","模态偏倚"],"confidence":0.93,"position":{"page_number":17,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"}},{"sentence_id":"S6","sentence":"社交图关系型数据的获取通常依赖平台API权限并受到隐私保护政策限制，使依赖图结构的检测模型难以在真实场景中获得完整输入并充分发挥性能优势。","expression_type":"implicit","trigger_patterns":["受到限制","难以获得完整输入"],"confidence":0.95,"position":{"page_number":18,"source_section":"1.2.2 基于社交图关系数据建模的社交媒体机器人检测方法"}}],"research_question_phrases":[{"phrase_id":"RQP1","sentence_id":"S1","phrase":"如何高效检测社交媒体机器人","normalized_question":"如何提高社交媒体机器人检测的准确性与效率？","confidence":0.98},{"phrase_id":"RQP2","sentence_id":"S2","phrase":"缓解多模态数据稀疏、噪声干扰和算力需求大的问题","normalized_question":"如何缓解多模态数据稀疏与噪声干扰并降低计算资源需求？","confidence":0.95},{"phrase_id":"RQP3","sentence_id":"S2","phrase":"避免模型对部分模态的过度依赖","normalized_question":"如何降低多模态融合过程中的单一模态依赖？","confidence":0.96},{"phrase_id":"RQP4","sentence_id":"S3","phrase":"在社交图关系数据难以获取时保持检测性能","normalized_question":"如何在缺少完整社交图关系数据时保持机器人检测性能？","confidence":0.97},{"phrase_id":"RQP5","sentence_id":"S4","phrase":"在增强检测性能的同时降低复杂度、提高效率","normalized_question":"如何兼顾检测性能、模型复杂度与推理效率？","confidence":0.98},{"phrase_id":"RQP6","sentence_id":"S5","phrase":"解决多模态融合中的信息不均衡和模态偏倚","normalized_question":"如何提升多模态信息融合的稳定性与鲁棒性？","confidence":0.93},{"phrase_id":"RQP7","sentence_id":"S6","phrase":"降低模型对社交图关系数据的依赖","normalized_question":"如何构建不依赖完整社交图关系数据的检测框架？","confidence":0.96}],"structured_research_questions":[{"research_question_id":"RQ1","role":"main_question","parent_question_id":null,"question":"如何在真实应用场景中实现高效、准确且稳定的社交媒体机器人检测？","question_type":"综合任务定义型","research_object":"社交媒体机器人检测","research_targets":["检测准确性","检测效率","模型稳定性","实际应用能力"],"constraints":["数据获取受限","计算资源受限","多模态数据不完整"],"evidence_sentence_ids":["S1","S4"],"source_phrase_ids":["RQP1","RQP5"],"confidence":0.98},{"research_question_id":"RQ2","role":"sub_question","parent_question_id":"RQ1","question":"如何缓解多模态数据稀疏、噪声干扰、信息不均衡和单一模态偏倚，提升多模态融合效果？","question_type":"多模态融合优化型","research_object":"多模态社交媒体机器人检测模型","research_targets":["多视图信息融合","模态权重自适应","融合稳定性","分类性能"],"constraints":["数据稀疏","噪声干扰","模态缺失","算力需求较高"],"evidence_sentence_ids":["S2","S5"],"source_phrase_ids":["RQP2","RQP3","RQP6"],"confidence":0.96},{"research_question_id":"RQ3","role":"sub_question","parent_question_id":"RQ1","question":"如何在社交图关系数据难以获取的条件下保持检测性能，并降低资源消耗和模型数据依赖？","question_type":"数据依赖消减型","research_object":"基于社交图关系的机器人检测模型","research_targets":["降低图关系数据依赖","知识迁移","模型泛化能力","资源消耗控制"],"constraints":["平台API权限限制","隐私保护政策","社交图结构不完整"],"evidence_sentence_ids":["S3","S6"],"source_phrase_ids":["RQP4","RQP7"],"confidence":0.97},{"research_question_id":"RQ4","role":"sub_question","parent_question_id":"RQ1","question":"如何将无需完整社交图关系数据的机器人检测框架部署为可实际使用的检测系统？","question_type":"系统应用型","research_object":"社交媒体机器人检测系统","research_targets":["在线检测","批量检测","结果可视化","实际部署"],"constraints":["不依赖完整社交图关系数据","操作便捷","满足真实平台应用需求"],"evidence_sentence_ids":["S3","S4"],"source_phrase_ids":["RQP4","RQP5","RQP7"],"confidence":0.93}],"research_question_statistics":{"document_page_count":83,"analyzed_section_count":4,"research_question_sentence_count":6,"explicit_question_sentence_count":2,"implicit_question_sentence_count":4,"research_question_phrase_count":7,"structured_question_count":4,"main_question_count":1,"sub_question_count":3,"question_type_distribution":[{"question_type":"综合任务定义型","count":1,"percentage":25.0},{"question_type":"多模态融合优化型","count":1,"percentage":25.0},{"question_type":"数据依赖消减型","count":1,"percentage":25.0},{"question_type":"系统应用型","count":1,"percentage":25.0}],"average_confidence":0.96}},"meta":{"fixed_demo_output":true,"format_requirements":{"language":"zh","document_scope":"abstract_and_introduction","preserve_section_hierarchy":true,"sentence_segmentation":"auto","recognize_explicit_questions":true,"recognize_implicit_questions":true,"return_source_section":true,"return_page_number":true,"minimum_confidence":0.75},"request_id":"req_research_question_file_202607200001","elapsed_ms":1842}},"demoBatchFileResult":{"code":200,"message":"batch_completed","data":{"batch_id":"batch_research_question_files_202607200001","input_type":"files","total":3,"success_count":3,"failed_count":0,"results":[{"index":1,"file_name":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架.pdf","status":"success","code":200,"result":{"tool":"研究问题句及短语识别","input_type":"file","input":{"file_name":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架.pdf","file_format":"PDF","file_size":"3.17 MB","document_parse_status":"success","section_extraction_status":"success","text_format_validation_status":"success"},"document":{"title":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架","language":"zh","page_count":83,"analysis_scope":["摘要","1 绪论","1.2 国内外研究现状","1.3 本文主要工作及贡献"]},"research_question_sentences":[{"sentence_id":"S1","sentence":"因此，如何高效检测社交媒体机器人成为人工智能安全领域的重要课题。","expression_type":"explicit","trigger_patterns":["如何","重要课题"],"confidence":0.98,"position":{"page_number":7,"source_section":"摘要"}},{"sentence_id":"S2","sentence":"基于多模态的方法时常面临数据稀疏、噪声干扰、算力需求大等问题，且在模态融合过程中容易出现对部分模态的过度依赖，导致整体模型在缺少部分模态时性能显著下降。","expression_type":"implicit","trigger_patterns":["面临","问题","过度依赖","性能显著下降"],"confidence":0.96,"position":{"page_number":7,"source_section":"摘要"}},{"sentence_id":"S3","sentence":"基于社交图关系的方法过度依赖图关系型数据，但是该类数据常因隐私保护与平台接口限制难以获取，从而严重制约模型的性能与实际应用。","expression_type":"implicit","trigger_patterns":["过度依赖","难以获取","严重制约"],"confidence":0.97,"position":{"page_number":7,"source_section":"摘要"}},{"sentence_id":"S4","sentence":"当前主流的检测方法对数据获取、处理以及GPU算力要求较高，如何在增强模型检测性能的同时降低复杂度、提高效率成为关键研究方向。","expression_type":"explicit","trigger_patterns":["如何","关键研究方向"],"confidence":0.98,"position":{"page_number":15,"source_section":"1 绪论"}},{"sentence_id":"S5","sentence":"随着数据规模不断扩大，不同模态之间在稀疏性和表达能力上的差异日益突出，导致融合过程中面临信息不均衡、模型结构复杂和单一模态偏倚等问题。","expression_type":"implicit","trigger_patterns":["差异日益突出","信息不均衡","模态偏倚"],"confidence":0.93,"position":{"page_number":17,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"}},{"sentence_id":"S6","sentence":"社交图关系型数据的获取通常依赖平台API权限并受到隐私保护政策限制，使依赖图结构的检测模型难以在真实场景中获得完整输入并充分发挥性能优势。","expression_type":"implicit","trigger_patterns":["受到限制","难以获得完整输入"],"confidence":0.95,"position":{"page_number":18,"source_section":"1.2.2 基于社交图关系数据建模的社交媒体机器人检测方法"}}],"research_question_phrases":[{"phrase_id":"RQP1","sentence_id":"S1","phrase":"如何高效检测社交媒体机器人","normalized_question":"如何提高社交媒体机器人检测的准确性与效率？","confidence":0.98},{"phrase_id":"RQP2","sentence_id":"S2","phrase":"缓解多模态数据稀疏、噪声干扰和算力需求大的问题","normalized_question":"如何缓解多模态数据稀疏与噪声干扰并降低计算资源需求？","confidence":0.95},{"phrase_id":"RQP3","sentence_id":"S2","phrase":"避免模型对部分模态的过度依赖","normalized_question":"如何降低多模态融合过程中的单一模态依赖？","confidence":0.96},{"phrase_id":"RQP4","sentence_id":"S3","phrase":"在社交图关系数据难以获取时保持检测性能","normalized_question":"如何在缺少完整社交图关系数据时保持机器人检测性能？","confidence":0.97},{"phrase_id":"RQP5","sentence_id":"S4","phrase":"在增强检测性能的同时降低复杂度、提高效率","normalized_question":"如何兼顾检测性能、模型复杂度与推理效率？","confidence":0.98},{"phrase_id":"RQP6","sentence_id":"S5","phrase":"解决多模态融合中的信息不均衡和模态偏倚","normalized_question":"如何提升多模态信息融合的稳定性与鲁棒性？","confidence":0.93},{"phrase_id":"RQP7","sentence_id":"S6","phrase":"降低模型对社交图关系数据的依赖","normalized_question":"如何构建不依赖完整社交图关系数据的检测框架？","confidence":0.96}],"structured_research_questions":[{"research_question_id":"RQ1","role":"main_question","parent_question_id":null,"question":"如何在真实应用场景中实现高效、准确且稳定的社交媒体机器人检测？","question_type":"综合任务定义型","research_object":"社交媒体机器人检测","research_targets":["检测准确性","检测效率","模型稳定性","实际应用能力"],"constraints":["数据获取受限","计算资源受限","多模态数据不完整"],"evidence_sentence_ids":["S1","S4"],"source_phrase_ids":["RQP1","RQP5"],"confidence":0.98},{"research_question_id":"RQ2","role":"sub_question","parent_question_id":"RQ1","question":"如何缓解多模态数据稀疏、噪声干扰、信息不均衡和单一模态偏倚，提升多模态融合效果？","question_type":"多模态融合优化型","research_object":"多模态社交媒体机器人检测模型","research_targets":["多视图信息融合","模态权重自适应","融合稳定性","分类性能"],"constraints":["数据稀疏","噪声干扰","模态缺失","算力需求较高"],"evidence_sentence_ids":["S2","S5"],"source_phrase_ids":["RQP2","RQP3","RQP6"],"confidence":0.96},{"research_question_id":"RQ3","role":"sub_question","parent_question_id":"RQ1","question":"如何在社交图关系数据难以获取的条件下保持检测性能，并降低资源消耗和模型数据依赖？","question_type":"数据依赖消减型","research_object":"基于社交图关系的机器人检测模型","research_targets":["降低图关系数据依赖","知识迁移","模型泛化能力","资源消耗控制"],"constraints":["平台API权限限制","隐私保护政策","社交图结构不完整"],"evidence_sentence_ids":["S3","S6"],"source_phrase_ids":["RQP4","RQP7"],"confidence":0.97},{"research_question_id":"RQ4","role":"sub_question","parent_question_id":"RQ1","question":"如何将无需完整社交图关系数据的机器人检测框架部署为可实际使用的检测系统？","question_type":"系统应用型","research_object":"社交媒体机器人检测系统","research_targets":["在线检测","批量检测","结果可视化","实际部署"],"constraints":["不依赖完整社交图关系数据","操作便捷","满足真实平台应用需求"],"evidence_sentence_ids":["S3","S4"],"source_phrase_ids":["RQP4","RQP5","RQP7"],"confidence":0.93}],"research_question_statistics":{"document_page_count":83,"analyzed_section_count":4,"research_question_sentence_count":6,"explicit_question_sentence_count":2,"implicit_question_sentence_count":4,"research_question_phrase_count":7,"structured_question_count":4,"main_question_count":1,"sub_question_count":3,"question_type_distribution":[{"question_type":"综合任务定义型","count":1,"percentage":25.0},{"question_type":"多模态融合优化型","count":1,"percentage":25.0},{"question_type":"数据依赖消减型","count":1,"percentage":25.0},{"question_type":"系统应用型","count":1,"percentage":25.0}],"average_confidence":0.96}}},{"index":2,"file_name":"社交媒体机器人检测_摘要问题片段.txt","status":"success","code":200,"result":{"tool":"研究问题句及短语识别","input_type":"file","input":{"file_name":"社交媒体机器人检测_摘要问题片段.txt","file_format":"TXT","file_size":"516 B","document_parse_status":"success","section_extraction_status":"success","text_format_validation_status":"success"},"document":{"title":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架","language":"zh","page_count":null,"analysis_scope":["摘要问题片段"]},"research_question_sentences":[{"sentence_id":"S1","sentence":"因此，如何高效检测社交媒体机器人成为人工智能安全领域的重要课题。","expression_type":"explicit","trigger_patterns":["如何","重要课题"],"confidence":0.98,"position":{"page_number":7,"source_section":"摘要"}},{"sentence_id":"S2","sentence":"基于多模态的方法时常面临数据稀疏、噪声干扰、算力需求大等问题，且在模态融合过程中容易出现对部分模态的过度依赖，导致整体模型在缺少部分模态时性能显著下降。","expression_type":"implicit","trigger_patterns":["面临","问题","过度依赖","性能显著下降"],"confidence":0.96,"position":{"page_number":7,"source_section":"摘要"}},{"sentence_id":"S3","sentence":"基于社交图关系的方法过度依赖图关系型数据，但是该类数据常因隐私保护与平台接口限制难以获取，从而严重制约模型的性能与实际应用。","expression_type":"implicit","trigger_patterns":["过度依赖","难以获取","严重制约"],"confidence":0.97,"position":{"page_number":7,"source_section":"摘要"}}],"research_question_phrases":[{"phrase_id":"RQP1","sentence_id":"S1","phrase":"如何高效检测社交媒体机器人","normalized_question":"如何提高社交媒体机器人检测的准确性与效率？","confidence":0.98},{"phrase_id":"RQP2","sentence_id":"S2","phrase":"缓解多模态数据稀疏、噪声干扰和算力需求大的问题","normalized_question":"如何缓解多模态数据稀疏与噪声干扰并降低计算资源需求？","confidence":0.95},{"phrase_id":"RQP3","sentence_id":"S2","phrase":"避免模型对部分模态的过度依赖","normalized_question":"如何降低多模态融合过程中的单一模态依赖？","confidence":0.96},{"phrase_id":"RQP4","sentence_id":"S3","phrase":"在社交图关系数据难以获取时保持检测性能","normalized_question":"如何在缺少完整社交图关系数据时保持机器人检测性能？","confidence":0.97}],"structured_research_questions":[{"research_question_id":"RQ1","role":"main_question","parent_question_id":null,"question":"如何在真实应用场景中实现高效、准确且稳定的社交媒体机器人检测？","question_type":"综合任务定义型","research_object":"社交媒体机器人检测","research_targets":["检测准确性","检测效率","模型稳定性","实际应用能力"],"constraints":["数据获取受限","计算资源受限","多模态数据不完整"],"evidence_sentence_ids":["S1","S4"],"source_phrase_ids":["RQP1","RQP5"],"confidence":0.98},{"research_question_id":"RQ2","role":"sub_question","parent_question_id":"RQ1","question":"如何缓解多模态数据稀疏、噪声干扰、信息不均衡和单一模态偏倚，提升多模态融合效果？","question_type":"多模态融合优化型","research_object":"多模态社交媒体机器人检测模型","research_targets":["多视图信息融合","模态权重自适应","融合稳定性","分类性能"],"constraints":["数据稀疏","噪声干扰","模态缺失","算力需求较高"],"evidence_sentence_ids":["S2","S5"],"source_phrase_ids":["RQP2","RQP3","RQP6"],"confidence":0.96},{"research_question_id":"RQ3","role":"sub_question","parent_question_id":"RQ1","question":"如何在社交图关系数据难以获取的条件下保持检测性能，并降低资源消耗和模型数据依赖？","question_type":"数据依赖消减型","research_object":"基于社交图关系的机器人检测模型","research_targets":["降低图关系数据依赖","知识迁移","模型泛化能力","资源消耗控制"],"constraints":["平台API权限限制","隐私保护政策","社交图结构不完整"],"evidence_sentence_ids":["S3","S6"],"source_phrase_ids":["RQP4","RQP7"],"confidence":0.97}],"research_question_statistics":{"document_page_count":1,"analyzed_section_count":1,"research_question_sentence_count":3,"explicit_question_sentence_count":1,"implicit_question_sentence_count":2,"research_question_phrase_count":4,"structured_question_count":3,"main_question_count":1,"sub_question_count":2,"question_type_distribution":[{"question_type":"综合任务定义型","count":1,"percentage":33.33},{"question_type":"多模态融合优化型","count":1,"percentage":33.33},{"question_type":"数据依赖消减型","count":1,"percentage":33.33}],"average_confidence":0.97}}},{"index":3,"file_name":"社交媒体机器人检测_绪论问题片段.txt","status":"success","code":200,"result":{"tool":"研究问题句及短语识别","input_type":"file","input":{"file_name":"社交媒体机器人检测_绪论问题片段.txt","file_format":"TXT","file_size":"555 B","document_parse_status":"success","section_extraction_status":"success","text_format_validation_status":"success"},"document":{"title":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架","language":"zh","page_count":null,"analysis_scope":["1 绪论问题片段","1.2 国内外研究现状问题片段"]},"research_question_sentences":[{"sentence_id":"S4","sentence":"当前主流的检测方法对数据获取、处理以及GPU算力要求较高，如何在增强模型检测性能的同时降低复杂度、提高效率成为关键研究方向。","expression_type":"explicit","trigger_patterns":["如何","关键研究方向"],"confidence":0.98,"position":{"page_number":15,"source_section":"1 绪论"}},{"sentence_id":"S5","sentence":"随着数据规模不断扩大，不同模态之间在稀疏性和表达能力上的差异日益突出，导致融合过程中面临信息不均衡、模型结构复杂和单一模态偏倚等问题。","expression_type":"implicit","trigger_patterns":["差异日益突出","信息不均衡","模态偏倚"],"confidence":0.93,"position":{"page_number":17,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"}},{"sentence_id":"S6","sentence":"社交图关系型数据的获取通常依赖平台API权限并受到隐私保护政策限制，使依赖图结构的检测模型难以在真实场景中获得完整输入并充分发挥性能优势。","expression_type":"implicit","trigger_patterns":["受到限制","难以获得完整输入"],"confidence":0.95,"position":{"page_number":18,"source_section":"1.2.2 基于社交图关系数据建模的社交媒体机器人检测方法"}}],"research_question_phrases":[{"phrase_id":"RQP5","sentence_id":"S4","phrase":"在增强检测性能的同时降低复杂度、提高效率","normalized_question":"如何兼顾检测性能、模型复杂度与推理效率？","confidence":0.98},{"phrase_id":"RQP6","sentence_id":"S5","phrase":"解决多模态融合中的信息不均衡和模态偏倚","normalized_question":"如何提升多模态信息融合的稳定性与鲁棒性？","confidence":0.93},{"phrase_id":"RQP7","sentence_id":"S6","phrase":"降低模型对社交图关系数据的依赖","normalized_question":"如何构建不依赖完整社交图关系数据的检测框架？","confidence":0.96}],"structured_research_questions":[{"research_question_id":"RQ1","role":"main_question","parent_question_id":null,"question":"如何在真实应用场景中实现高效、准确且稳定的社交媒体机器人检测？","question_type":"综合任务定义型","research_object":"社交媒体机器人检测","research_targets":["检测准确性","检测效率","模型稳定性","实际应用能力"],"constraints":["数据获取受限","计算资源受限","多模态数据不完整"],"evidence_sentence_ids":["S1","S4"],"source_phrase_ids":["RQP1","RQP5"],"confidence":0.98},{"research_question_id":"RQ2","role":"sub_question","parent_question_id":"RQ1","question":"如何缓解多模态数据稀疏、噪声干扰、信息不均衡和单一模态偏倚，提升多模态融合效果？","question_type":"多模态融合优化型","research_object":"多模态社交媒体机器人检测模型","research_targets":["多视图信息融合","模态权重自适应","融合稳定性","分类性能"],"constraints":["数据稀疏","噪声干扰","模态缺失","算力需求较高"],"evidence_sentence_ids":["S2","S5"],"source_phrase_ids":["RQP2","RQP3","RQP6"],"confidence":0.96},{"research_question_id":"RQ3","role":"sub_question","parent_question_id":"RQ1","question":"如何在社交图关系数据难以获取的条件下保持检测性能，并降低资源消耗和模型数据依赖？","question_type":"数据依赖消减型","research_object":"基于社交图关系的机器人检测模型","research_targets":["降低图关系数据依赖","知识迁移","模型泛化能力","资源消耗控制"],"constraints":["平台API权限限制","隐私保护政策","社交图结构不完整"],"evidence_sentence_ids":["S3","S6"],"source_phrase_ids":["RQP4","RQP7"],"confidence":0.97}],"research_question_statistics":{"document_page_count":1,"analyzed_section_count":2,"research_question_sentence_count":3,"explicit_question_sentence_count":1,"implicit_question_sentence_count":2,"research_question_phrase_count":3,"structured_question_count":3,"main_question_count":1,"sub_question_count":2,"question_type_distribution":[{"question_type":"综合任务定义型","count":1,"percentage":33.33},{"question_type":"多模态融合优化型","count":1,"percentage":33.33},{"question_type":"数据依赖消减型","count":1,"percentage":33.33}],"average_confidence":0.95}}}]},"meta":{"format_requirements":{"language":"zh","document_scope":"abstract_and_introduction","preserve_section_hierarchy":true,"sentence_segmentation":"auto","recognize_explicit_questions":true,"recognize_implicit_questions":true,"return_source_section":true,"return_page_number":true,"minimum_confidence":0.75},"max_concurrency":3,"continue_on_error":true,"elapsed_ms":3926}},"response":{"code":200,"message":"batch_completed","data":{"batch_id":"batch_research_question_files_202607200001","input_type":"files","total":3,"success_count":3,"failed_count":0,"results":[{"index":1,"file_name":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架.pdf","status":"success","code":200,"result":{"tool":"研究问题句及短语识别","input_type":"file","input":{"file_name":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架.pdf","file_format":"PDF","file_size":"3.17 MB","document_parse_status":"success","section_extraction_status":"success","text_format_validation_status":"success"},"document":{"title":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架","language":"zh","page_count":83,"analysis_scope":["摘要","1 绪论","1.2 国内外研究现状","1.3 本文主要工作及贡献"]},"research_question_sentences":[{"sentence_id":"S1","sentence":"因此，如何高效检测社交媒体机器人成为人工智能安全领域的重要课题。","expression_type":"explicit","trigger_patterns":["如何","重要课题"],"confidence":0.98,"position":{"page_number":7,"source_section":"摘要"}},{"sentence_id":"S2","sentence":"基于多模态的方法时常面临数据稀疏、噪声干扰、算力需求大等问题，且在模态融合过程中容易出现对部分模态的过度依赖，导致整体模型在缺少部分模态时性能显著下降。","expression_type":"implicit","trigger_patterns":["面临","问题","过度依赖","性能显著下降"],"confidence":0.96,"position":{"page_number":7,"source_section":"摘要"}},{"sentence_id":"S3","sentence":"基于社交图关系的方法过度依赖图关系型数据，但是该类数据常因隐私保护与平台接口限制难以获取，从而严重制约模型的性能与实际应用。","expression_type":"implicit","trigger_patterns":["过度依赖","难以获取","严重制约"],"confidence":0.97,"position":{"page_number":7,"source_section":"摘要"}},{"sentence_id":"S4","sentence":"当前主流的检测方法对数据获取、处理以及GPU算力要求较高，如何在增强模型检测性能的同时降低复杂度、提高效率成为关键研究方向。","expression_type":"explicit","trigger_patterns":["如何","关键研究方向"],"confidence":0.98,"position":{"page_number":15,"source_section":"1 绪论"}},{"sentence_id":"S5","sentence":"随着数据规模不断扩大，不同模态之间在稀疏性和表达能力上的差异日益突出，导致融合过程中面临信息不均衡、模型结构复杂和单一模态偏倚等问题。","expression_type":"implicit","trigger_patterns":["差异日益突出","信息不均衡","模态偏倚"],"confidence":0.93,"position":{"page_number":17,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"}},{"sentence_id":"S6","sentence":"社交图关系型数据的获取通常依赖平台API权限并受到隐私保护政策限制，使依赖图结构的检测模型难以在真实场景中获得完整输入并充分发挥性能优势。","expression_type":"implicit","trigger_patterns":["受到限制","难以获得完整输入"],"confidence":0.95,"position":{"page_number":18,"source_section":"1.2.2 基于社交图关系数据建模的社交媒体机器人检测方法"}}],"research_question_phrases":[{"phrase_id":"RQP1","sentence_id":"S1","phrase":"如何高效检测社交媒体机器人","normalized_question":"如何提高社交媒体机器人检测的准确性与效率？","confidence":0.98},{"phrase_id":"RQP2","sentence_id":"S2","phrase":"缓解多模态数据稀疏、噪声干扰和算力需求大的问题","normalized_question":"如何缓解多模态数据稀疏与噪声干扰并降低计算资源需求？","confidence":0.95},{"phrase_id":"RQP3","sentence_id":"S2","phrase":"避免模型对部分模态的过度依赖","normalized_question":"如何降低多模态融合过程中的单一模态依赖？","confidence":0.96},{"phrase_id":"RQP4","sentence_id":"S3","phrase":"在社交图关系数据难以获取时保持检测性能","normalized_question":"如何在缺少完整社交图关系数据时保持机器人检测性能？","confidence":0.97},{"phrase_id":"RQP5","sentence_id":"S4","phrase":"在增强检测性能的同时降低复杂度、提高效率","normalized_question":"如何兼顾检测性能、模型复杂度与推理效率？","confidence":0.98},{"phrase_id":"RQP6","sentence_id":"S5","phrase":"解决多模态融合中的信息不均衡和模态偏倚","normalized_question":"如何提升多模态信息融合的稳定性与鲁棒性？","confidence":0.93},{"phrase_id":"RQP7","sentence_id":"S6","phrase":"降低模型对社交图关系数据的依赖","normalized_question":"如何构建不依赖完整社交图关系数据的检测框架？","confidence":0.96}],"structured_research_questions":[{"research_question_id":"RQ1","role":"main_question","parent_question_id":null,"question":"如何在真实应用场景中实现高效、准确且稳定的社交媒体机器人检测？","question_type":"综合任务定义型","research_object":"社交媒体机器人检测","research_targets":["检测准确性","检测效率","模型稳定性","实际应用能力"],"constraints":["数据获取受限","计算资源受限","多模态数据不完整"],"evidence_sentence_ids":["S1","S4"],"source_phrase_ids":["RQP1","RQP5"],"confidence":0.98},{"research_question_id":"RQ2","role":"sub_question","parent_question_id":"RQ1","question":"如何缓解多模态数据稀疏、噪声干扰、信息不均衡和单一模态偏倚，提升多模态融合效果？","question_type":"多模态融合优化型","research_object":"多模态社交媒体机器人检测模型","research_targets":["多视图信息融合","模态权重自适应","融合稳定性","分类性能"],"constraints":["数据稀疏","噪声干扰","模态缺失","算力需求较高"],"evidence_sentence_ids":["S2","S5"],"source_phrase_ids":["RQP2","RQP3","RQP6"],"confidence":0.96},{"research_question_id":"RQ3","role":"sub_question","parent_question_id":"RQ1","question":"如何在社交图关系数据难以获取的条件下保持检测性能，并降低资源消耗和模型数据依赖？","question_type":"数据依赖消减型","research_object":"基于社交图关系的机器人检测模型","research_targets":["降低图关系数据依赖","知识迁移","模型泛化能力","资源消耗控制"],"constraints":["平台API权限限制","隐私保护政策","社交图结构不完整"],"evidence_sentence_ids":["S3","S6"],"source_phrase_ids":["RQP4","RQP7"],"confidence":0.97},{"research_question_id":"RQ4","role":"sub_question","parent_question_id":"RQ1","question":"如何将无需完整社交图关系数据的机器人检测框架部署为可实际使用的检测系统？","question_type":"系统应用型","research_object":"社交媒体机器人检测系统","research_targets":["在线检测","批量检测","结果可视化","实际部署"],"constraints":["不依赖完整社交图关系数据","操作便捷","满足真实平台应用需求"],"evidence_sentence_ids":["S3","S4"],"source_phrase_ids":["RQP4","RQP5","RQP7"],"confidence":0.93}],"research_question_statistics":{"document_page_count":83,"analyzed_section_count":4,"research_question_sentence_count":6,"explicit_question_sentence_count":2,"implicit_question_sentence_count":4,"research_question_phrase_count":7,"structured_question_count":4,"main_question_count":1,"sub_question_count":3,"question_type_distribution":[{"question_type":"综合任务定义型","count":1,"percentage":25.0},{"question_type":"多模态融合优化型","count":1,"percentage":25.0},{"question_type":"数据依赖消减型","count":1,"percentage":25.0},{"question_type":"系统应用型","count":1,"percentage":25.0}],"average_confidence":0.96}}},{"index":2,"file_name":"社交媒体机器人检测_摘要问题片段.txt","status":"success","code":200,"result":{"tool":"研究问题句及短语识别","input_type":"file","input":{"file_name":"社交媒体机器人检测_摘要问题片段.txt","file_format":"TXT","file_size":"516 B","document_parse_status":"success","section_extraction_status":"success","text_format_validation_status":"success"},"document":{"title":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架","language":"zh","page_count":null,"analysis_scope":["摘要问题片段"]},"research_question_sentences":[{"sentence_id":"S1","sentence":"因此，如何高效检测社交媒体机器人成为人工智能安全领域的重要课题。","expression_type":"explicit","trigger_patterns":["如何","重要课题"],"confidence":0.98,"position":{"page_number":7,"source_section":"摘要"}},{"sentence_id":"S2","sentence":"基于多模态的方法时常面临数据稀疏、噪声干扰、算力需求大等问题，且在模态融合过程中容易出现对部分模态的过度依赖，导致整体模型在缺少部分模态时性能显著下降。","expression_type":"implicit","trigger_patterns":["面临","问题","过度依赖","性能显著下降"],"confidence":0.96,"position":{"page_number":7,"source_section":"摘要"}},{"sentence_id":"S3","sentence":"基于社交图关系的方法过度依赖图关系型数据，但是该类数据常因隐私保护与平台接口限制难以获取，从而严重制约模型的性能与实际应用。","expression_type":"implicit","trigger_patterns":["过度依赖","难以获取","严重制约"],"confidence":0.97,"position":{"page_number":7,"source_section":"摘要"}}],"research_question_phrases":[{"phrase_id":"RQP1","sentence_id":"S1","phrase":"如何高效检测社交媒体机器人","normalized_question":"如何提高社交媒体机器人检测的准确性与效率？","confidence":0.98},{"phrase_id":"RQP2","sentence_id":"S2","phrase":"缓解多模态数据稀疏、噪声干扰和算力需求大的问题","normalized_question":"如何缓解多模态数据稀疏与噪声干扰并降低计算资源需求？","confidence":0.95},{"phrase_id":"RQP3","sentence_id":"S2","phrase":"避免模型对部分模态的过度依赖","normalized_question":"如何降低多模态融合过程中的单一模态依赖？","confidence":0.96},{"phrase_id":"RQP4","sentence_id":"S3","phrase":"在社交图关系数据难以获取时保持检测性能","normalized_question":"如何在缺少完整社交图关系数据时保持机器人检测性能？","confidence":0.97}],"structured_research_questions":[{"research_question_id":"RQ1","role":"main_question","parent_question_id":null,"question":"如何在真实应用场景中实现高效、准确且稳定的社交媒体机器人检测？","question_type":"综合任务定义型","research_object":"社交媒体机器人检测","research_targets":["检测准确性","检测效率","模型稳定性","实际应用能力"],"constraints":["数据获取受限","计算资源受限","多模态数据不完整"],"evidence_sentence_ids":["S1","S4"],"source_phrase_ids":["RQP1","RQP5"],"confidence":0.98},{"research_question_id":"RQ2","role":"sub_question","parent_question_id":"RQ1","question":"如何缓解多模态数据稀疏、噪声干扰、信息不均衡和单一模态偏倚，提升多模态融合效果？","question_type":"多模态融合优化型","research_object":"多模态社交媒体机器人检测模型","research_targets":["多视图信息融合","模态权重自适应","融合稳定性","分类性能"],"constraints":["数据稀疏","噪声干扰","模态缺失","算力需求较高"],"evidence_sentence_ids":["S2","S5"],"source_phrase_ids":["RQP2","RQP3","RQP6"],"confidence":0.96},{"research_question_id":"RQ3","role":"sub_question","parent_question_id":"RQ1","question":"如何在社交图关系数据难以获取的条件下保持检测性能，并降低资源消耗和模型数据依赖？","question_type":"数据依赖消减型","research_object":"基于社交图关系的机器人检测模型","research_targets":["降低图关系数据依赖","知识迁移","模型泛化能力","资源消耗控制"],"constraints":["平台API权限限制","隐私保护政策","社交图结构不完整"],"evidence_sentence_ids":["S3","S6"],"source_phrase_ids":["RQP4","RQP7"],"confidence":0.97}],"research_question_statistics":{"document_page_count":1,"analyzed_section_count":1,"research_question_sentence_count":3,"explicit_question_sentence_count":1,"implicit_question_sentence_count":2,"research_question_phrase_count":4,"structured_question_count":3,"main_question_count":1,"sub_question_count":2,"question_type_distribution":[{"question_type":"综合任务定义型","count":1,"percentage":33.33},{"question_type":"多模态融合优化型","count":1,"percentage":33.33},{"question_type":"数据依赖消减型","count":1,"percentage":33.33}],"average_confidence":0.97}}},{"index":3,"file_name":"社交媒体机器人检测_绪论问题片段.txt","status":"success","code":200,"result":{"tool":"研究问题句及短语识别","input_type":"file","input":{"file_name":"社交媒体机器人检测_绪论问题片段.txt","file_format":"TXT","file_size":"555 B","document_parse_status":"success","section_extraction_status":"success","text_format_validation_status":"success"},"document":{"title":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架","language":"zh","page_count":null,"analysis_scope":["1 绪论问题片段","1.2 国内外研究现状问题片段"]},"research_question_sentences":[{"sentence_id":"S4","sentence":"当前主流的检测方法对数据获取、处理以及GPU算力要求较高，如何在增强模型检测性能的同时降低复杂度、提高效率成为关键研究方向。","expression_type":"explicit","trigger_patterns":["如何","关键研究方向"],"confidence":0.98,"position":{"page_number":15,"source_section":"1 绪论"}},{"sentence_id":"S5","sentence":"随着数据规模不断扩大，不同模态之间在稀疏性和表达能力上的差异日益突出，导致融合过程中面临信息不均衡、模型结构复杂和单一模态偏倚等问题。","expression_type":"implicit","trigger_patterns":["差异日益突出","信息不均衡","模态偏倚"],"confidence":0.93,"position":{"page_number":17,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"}},{"sentence_id":"S6","sentence":"社交图关系型数据的获取通常依赖平台API权限并受到隐私保护政策限制，使依赖图结构的检测模型难以在真实场景中获得完整输入并充分发挥性能优势。","expression_type":"implicit","trigger_patterns":["受到限制","难以获得完整输入"],"confidence":0.95,"position":{"page_number":18,"source_section":"1.2.2 基于社交图关系数据建模的社交媒体机器人检测方法"}}],"research_question_phrases":[{"phrase_id":"RQP5","sentence_id":"S4","phrase":"在增强检测性能的同时降低复杂度、提高效率","normalized_question":"如何兼顾检测性能、模型复杂度与推理效率？","confidence":0.98},{"phrase_id":"RQP6","sentence_id":"S5","phrase":"解决多模态融合中的信息不均衡和模态偏倚","normalized_question":"如何提升多模态信息融合的稳定性与鲁棒性？","confidence":0.93},{"phrase_id":"RQP7","sentence_id":"S6","phrase":"降低模型对社交图关系数据的依赖","normalized_question":"如何构建不依赖完整社交图关系数据的检测框架？","confidence":0.96}],"structured_research_questions":[{"research_question_id":"RQ1","role":"main_question","parent_question_id":null,"question":"如何在真实应用场景中实现高效、准确且稳定的社交媒体机器人检测？","question_type":"综合任务定义型","research_object":"社交媒体机器人检测","research_targets":["检测准确性","检测效率","模型稳定性","实际应用能力"],"constraints":["数据获取受限","计算资源受限","多模态数据不完整"],"evidence_sentence_ids":["S1","S4"],"source_phrase_ids":["RQP1","RQP5"],"confidence":0.98},{"research_question_id":"RQ2","role":"sub_question","parent_question_id":"RQ1","question":"如何缓解多模态数据稀疏、噪声干扰、信息不均衡和单一模态偏倚，提升多模态融合效果？","question_type":"多模态融合优化型","research_object":"多模态社交媒体机器人检测模型","research_targets":["多视图信息融合","模态权重自适应","融合稳定性","分类性能"],"constraints":["数据稀疏","噪声干扰","模态缺失","算力需求较高"],"evidence_sentence_ids":["S2","S5"],"source_phrase_ids":["RQP2","RQP3","RQP6"],"confidence":0.96},{"research_question_id":"RQ3","role":"sub_question","parent_question_id":"RQ1","question":"如何在社交图关系数据难以获取的条件下保持检测性能，并降低资源消耗和模型数据依赖？","question_type":"数据依赖消减型","research_object":"基于社交图关系的机器人检测模型","research_targets":["降低图关系数据依赖","知识迁移","模型泛化能力","资源消耗控制"],"constraints":["平台API权限限制","隐私保护政策","社交图结构不完整"],"evidence_sentence_ids":["S3","S6"],"source_phrase_ids":["RQP4","RQP7"],"confidence":0.97}],"research_question_statistics":{"document_page_count":1,"analyzed_section_count":2,"research_question_sentence_count":3,"explicit_question_sentence_count":1,"implicit_question_sentence_count":2,"research_question_phrase_count":3,"structured_question_count":3,"main_question_count":1,"sub_question_count":2,"question_type_distribution":[{"question_type":"综合任务定义型","count":1,"percentage":33.33},{"question_type":"多模态融合优化型","count":1,"percentage":33.33},{"question_type":"数据依赖消减型","count":1,"percentage":33.33}],"average_confidence":0.95}}}]},"meta":{"format_requirements":{"language":"zh","document_scope":"abstract_and_introduction","preserve_section_hierarchy":true,"sentence_segmentation":"auto","recognize_explicit_questions":true,"recognize_implicit_questions":true,"return_source_section":true,"return_page_number":true,"minimum_confidence":0.75},"max_concurrency":3,"continue_on_error":true,"elapsed_ms":3926}},"demoFileFixtures":[{"file_name":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架.pdf","size_bytes":3322216,"sha256":"4c51e28c11e4954d05e192a41337eb0e7d606c0b9097aeafa16ba858711b91c0","fnv1a32":"20540fb6","result":{"code":200,"message":"success","data":{"tool":"研究问题句及短语识别","input_type":"file","input":{"file_name":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架.pdf","file_format":"PDF","file_size":"3.17 MB","document_parse_status":"success","section_extraction_status":"success","text_format_validation_status":"success"},"document":{"title":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架","language":"zh","page_count":83,"analysis_scope":["摘要","1 绪论","1.2 国内外研究现状","1.3 本文主要工作及贡献"]},"research_question_sentences":[{"sentence_id":"S1","sentence":"因此，如何高效检测社交媒体机器人成为人工智能安全领域的重要课题。","expression_type":"explicit","trigger_patterns":["如何","重要课题"],"confidence":0.98,"position":{"page_number":7,"source_section":"摘要"}},{"sentence_id":"S2","sentence":"基于多模态的方法时常面临数据稀疏、噪声干扰、算力需求大等问题，且在模态融合过程中容易出现对部分模态的过度依赖，导致整体模型在缺少部分模态时性能显著下降。","expression_type":"implicit","trigger_patterns":["面临","问题","过度依赖","性能显著下降"],"confidence":0.96,"position":{"page_number":7,"source_section":"摘要"}},{"sentence_id":"S3","sentence":"基于社交图关系的方法过度依赖图关系型数据，但是该类数据常因隐私保护与平台接口限制难以获取，从而严重制约模型的性能与实际应用。","expression_type":"implicit","trigger_patterns":["过度依赖","难以获取","严重制约"],"confidence":0.97,"position":{"page_number":7,"source_section":"摘要"}},{"sentence_id":"S4","sentence":"当前主流的检测方法对数据获取、处理以及GPU算力要求较高，如何在增强模型检测性能的同时降低复杂度、提高效率成为关键研究方向。","expression_type":"explicit","trigger_patterns":["如何","关键研究方向"],"confidence":0.98,"position":{"page_number":15,"source_section":"1 绪论"}},{"sentence_id":"S5","sentence":"随着数据规模不断扩大，不同模态之间在稀疏性和表达能力上的差异日益突出，导致融合过程中面临信息不均衡、模型结构复杂和单一模态偏倚等问题。","expression_type":"implicit","trigger_patterns":["差异日益突出","信息不均衡","模态偏倚"],"confidence":0.93,"position":{"page_number":17,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"}},{"sentence_id":"S6","sentence":"社交图关系型数据的获取通常依赖平台API权限并受到隐私保护政策限制，使依赖图结构的检测模型难以在真实场景中获得完整输入并充分发挥性能优势。","expression_type":"implicit","trigger_patterns":["受到限制","难以获得完整输入"],"confidence":0.95,"position":{"page_number":18,"source_section":"1.2.2 基于社交图关系数据建模的社交媒体机器人检测方法"}}],"research_question_phrases":[{"phrase_id":"RQP1","sentence_id":"S1","phrase":"如何高效检测社交媒体机器人","normalized_question":"如何提高社交媒体机器人检测的准确性与效率？","confidence":0.98},{"phrase_id":"RQP2","sentence_id":"S2","phrase":"缓解多模态数据稀疏、噪声干扰和算力需求大的问题","normalized_question":"如何缓解多模态数据稀疏与噪声干扰并降低计算资源需求？","confidence":0.95},{"phrase_id":"RQP3","sentence_id":"S2","phrase":"避免模型对部分模态的过度依赖","normalized_question":"如何降低多模态融合过程中的单一模态依赖？","confidence":0.96},{"phrase_id":"RQP4","sentence_id":"S3","phrase":"在社交图关系数据难以获取时保持检测性能","normalized_question":"如何在缺少完整社交图关系数据时保持机器人检测性能？","confidence":0.97},{"phrase_id":"RQP5","sentence_id":"S4","phrase":"在增强检测性能的同时降低复杂度、提高效率","normalized_question":"如何兼顾检测性能、模型复杂度与推理效率？","confidence":0.98},{"phrase_id":"RQP6","sentence_id":"S5","phrase":"解决多模态融合中的信息不均衡和模态偏倚","normalized_question":"如何提升多模态信息融合的稳定性与鲁棒性？","confidence":0.93},{"phrase_id":"RQP7","sentence_id":"S6","phrase":"降低模型对社交图关系数据的依赖","normalized_question":"如何构建不依赖完整社交图关系数据的检测框架？","confidence":0.96}],"structured_research_questions":[{"research_question_id":"RQ1","role":"main_question","parent_question_id":null,"question":"如何在真实应用场景中实现高效、准确且稳定的社交媒体机器人检测？","question_type":"综合任务定义型","research_object":"社交媒体机器人检测","research_targets":["检测准确性","检测效率","模型稳定性","实际应用能力"],"constraints":["数据获取受限","计算资源受限","多模态数据不完整"],"evidence_sentence_ids":["S1","S4"],"source_phrase_ids":["RQP1","RQP5"],"confidence":0.98},{"research_question_id":"RQ2","role":"sub_question","parent_question_id":"RQ1","question":"如何缓解多模态数据稀疏、噪声干扰、信息不均衡和单一模态偏倚，提升多模态融合效果？","question_type":"多模态融合优化型","research_object":"多模态社交媒体机器人检测模型","research_targets":["多视图信息融合","模态权重自适应","融合稳定性","分类性能"],"constraints":["数据稀疏","噪声干扰","模态缺失","算力需求较高"],"evidence_sentence_ids":["S2","S5"],"source_phrase_ids":["RQP2","RQP3","RQP6"],"confidence":0.96},{"research_question_id":"RQ3","role":"sub_question","parent_question_id":"RQ1","question":"如何在社交图关系数据难以获取的条件下保持检测性能，并降低资源消耗和模型数据依赖？","question_type":"数据依赖消减型","research_object":"基于社交图关系的机器人检测模型","research_targets":["降低图关系数据依赖","知识迁移","模型泛化能力","资源消耗控制"],"constraints":["平台API权限限制","隐私保护政策","社交图结构不完整"],"evidence_sentence_ids":["S3","S6"],"source_phrase_ids":["RQP4","RQP7"],"confidence":0.97},{"research_question_id":"RQ4","role":"sub_question","parent_question_id":"RQ1","question":"如何将无需完整社交图关系数据的机器人检测框架部署为可实际使用的检测系统？","question_type":"系统应用型","research_object":"社交媒体机器人检测系统","research_targets":["在线检测","批量检测","结果可视化","实际部署"],"constraints":["不依赖完整社交图关系数据","操作便捷","满足真实平台应用需求"],"evidence_sentence_ids":["S3","S4"],"source_phrase_ids":["RQP4","RQP5","RQP7"],"confidence":0.93}],"research_question_statistics":{"document_page_count":83,"analyzed_section_count":4,"research_question_sentence_count":6,"explicit_question_sentence_count":2,"implicit_question_sentence_count":4,"research_question_phrase_count":7,"structured_question_count":4,"main_question_count":1,"sub_question_count":3,"question_type_distribution":[{"question_type":"综合任务定义型","count":1,"percentage":25.0},{"question_type":"多模态融合优化型","count":1,"percentage":25.0},{"question_type":"数据依赖消减型","count":1,"percentage":25.0},{"question_type":"系统应用型","count":1,"percentage":25.0}],"average_confidence":0.96}},"meta":{"fixed_demo_output":true,"format_requirements":{"language":"zh","document_scope":"abstract_and_introduction","preserve_section_hierarchy":true,"sentence_segmentation":"auto","recognize_explicit_questions":true,"recognize_implicit_questions":true,"return_source_section":true,"return_page_number":true,"minimum_confidence":0.75},"request_id":"req_research_question_file_202607200001","elapsed_ms":1842}}},{"file_name":"社交媒体机器人检测_摘要问题片段.txt","size_bytes":516,"sha256":"e915ec43413526d26283cd588c384215a7a7f2a0d5a0bba34755a2353ee7f3b0","fnv1a32":"a1ffbb41","result":{"code":200,"message":"success","data":{"tool":"研究问题句及短语识别","input_type":"file","input":{"file_name":"社交媒体机器人检测_摘要问题片段.txt","file_format":"TXT","file_size":"516 B","document_parse_status":"success","section_extraction_status":"success","text_format_validation_status":"success"},"document":{"title":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架","language":"zh","page_count":null,"analysis_scope":["摘要问题片段"]},"research_question_sentences":[{"sentence_id":"S1","sentence":"因此，如何高效检测社交媒体机器人成为人工智能安全领域的重要课题。","expression_type":"explicit","trigger_patterns":["如何","重要课题"],"confidence":0.98,"position":{"page_number":7,"source_section":"摘要"}},{"sentence_id":"S2","sentence":"基于多模态的方法时常面临数据稀疏、噪声干扰、算力需求大等问题，且在模态融合过程中容易出现对部分模态的过度依赖，导致整体模型在缺少部分模态时性能显著下降。","expression_type":"implicit","trigger_patterns":["面临","问题","过度依赖","性能显著下降"],"confidence":0.96,"position":{"page_number":7,"source_section":"摘要"}},{"sentence_id":"S3","sentence":"基于社交图关系的方法过度依赖图关系型数据，但是该类数据常因隐私保护与平台接口限制难以获取，从而严重制约模型的性能与实际应用。","expression_type":"implicit","trigger_patterns":["过度依赖","难以获取","严重制约"],"confidence":0.97,"position":{"page_number":7,"source_section":"摘要"}}],"research_question_phrases":[{"phrase_id":"RQP1","sentence_id":"S1","phrase":"如何高效检测社交媒体机器人","normalized_question":"如何提高社交媒体机器人检测的准确性与效率？","confidence":0.98},{"phrase_id":"RQP2","sentence_id":"S2","phrase":"缓解多模态数据稀疏、噪声干扰和算力需求大的问题","normalized_question":"如何缓解多模态数据稀疏与噪声干扰并降低计算资源需求？","confidence":0.95},{"phrase_id":"RQP3","sentence_id":"S2","phrase":"避免模型对部分模态的过度依赖","normalized_question":"如何降低多模态融合过程中的单一模态依赖？","confidence":0.96},{"phrase_id":"RQP4","sentence_id":"S3","phrase":"在社交图关系数据难以获取时保持检测性能","normalized_question":"如何在缺少完整社交图关系数据时保持机器人检测性能？","confidence":0.97}],"structured_research_questions":[{"research_question_id":"RQ1","role":"main_question","parent_question_id":null,"question":"如何在真实应用场景中实现高效、准确且稳定的社交媒体机器人检测？","question_type":"综合任务定义型","research_object":"社交媒体机器人检测","research_targets":["检测准确性","检测效率","模型稳定性","实际应用能力"],"constraints":["数据获取受限","计算资源受限","多模态数据不完整"],"evidence_sentence_ids":["S1","S4"],"source_phrase_ids":["RQP1","RQP5"],"confidence":0.98},{"research_question_id":"RQ2","role":"sub_question","parent_question_id":"RQ1","question":"如何缓解多模态数据稀疏、噪声干扰、信息不均衡和单一模态偏倚，提升多模态融合效果？","question_type":"多模态融合优化型","research_object":"多模态社交媒体机器人检测模型","research_targets":["多视图信息融合","模态权重自适应","融合稳定性","分类性能"],"constraints":["数据稀疏","噪声干扰","模态缺失","算力需求较高"],"evidence_sentence_ids":["S2","S5"],"source_phrase_ids":["RQP2","RQP3","RQP6"],"confidence":0.96},{"research_question_id":"RQ3","role":"sub_question","parent_question_id":"RQ1","question":"如何在社交图关系数据难以获取的条件下保持检测性能，并降低资源消耗和模型数据依赖？","question_type":"数据依赖消减型","research_object":"基于社交图关系的机器人检测模型","research_targets":["降低图关系数据依赖","知识迁移","模型泛化能力","资源消耗控制"],"constraints":["平台API权限限制","隐私保护政策","社交图结构不完整"],"evidence_sentence_ids":["S3","S6"],"source_phrase_ids":["RQP4","RQP7"],"confidence":0.97}],"research_question_statistics":{"document_page_count":1,"analyzed_section_count":1,"research_question_sentence_count":3,"explicit_question_sentence_count":1,"implicit_question_sentence_count":2,"research_question_phrase_count":4,"structured_question_count":3,"main_question_count":1,"sub_question_count":2,"question_type_distribution":[{"question_type":"综合任务定义型","count":1,"percentage":33.33},{"question_type":"多模态融合优化型","count":1,"percentage":33.33},{"question_type":"数据依赖消减型","count":1,"percentage":33.33}],"average_confidence":0.97}},"meta":{"fixed_demo_output":true,"format_requirements":{"language":"zh","document_scope":"abstract_and_introduction","preserve_section_hierarchy":true,"sentence_segmentation":"auto","recognize_explicit_questions":true,"recognize_implicit_questions":true,"return_source_section":true,"return_page_number":true,"minimum_confidence":0.75},"request_id":"req_research_question_abstract_txt_202607200001","elapsed_ms":1842}}},{"file_name":"社交媒体机器人检测_绪论问题片段.txt","size_bytes":555,"sha256":"bfcf229355bae8c6dfd3dcf33548dcfb737735b2ddd2106114efc137aee5ef61","fnv1a32":"8360c3db","result":{"code":200,"message":"success","data":{"tool":"研究问题句及短语识别","input_type":"file","input":{"file_name":"社交媒体机器人检测_绪论问题片段.txt","file_format":"TXT","file_size":"555 B","document_parse_status":"success","section_extraction_status":"success","text_format_validation_status":"success"},"document":{"title":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架","language":"zh","page_count":null,"analysis_scope":["1 绪论问题片段","1.2 国内外研究现状问题片段"]},"research_question_sentences":[{"sentence_id":"S4","sentence":"当前主流的检测方法对数据获取、处理以及GPU算力要求较高，如何在增强模型检测性能的同时降低复杂度、提高效率成为关键研究方向。","expression_type":"explicit","trigger_patterns":["如何","关键研究方向"],"confidence":0.98,"position":{"page_number":15,"source_section":"1 绪论"}},{"sentence_id":"S5","sentence":"随着数据规模不断扩大，不同模态之间在稀疏性和表达能力上的差异日益突出，导致融合过程中面临信息不均衡、模型结构复杂和单一模态偏倚等问题。","expression_type":"implicit","trigger_patterns":["差异日益突出","信息不均衡","模态偏倚"],"confidence":0.93,"position":{"page_number":17,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"}},{"sentence_id":"S6","sentence":"社交图关系型数据的获取通常依赖平台API权限并受到隐私保护政策限制，使依赖图结构的检测模型难以在真实场景中获得完整输入并充分发挥性能优势。","expression_type":"implicit","trigger_patterns":["受到限制","难以获得完整输入"],"confidence":0.95,"position":{"page_number":18,"source_section":"1.2.2 基于社交图关系数据建模的社交媒体机器人检测方法"}}],"research_question_phrases":[{"phrase_id":"RQP5","sentence_id":"S4","phrase":"在增强检测性能的同时降低复杂度、提高效率","normalized_question":"如何兼顾检测性能、模型复杂度与推理效率？","confidence":0.98},{"phrase_id":"RQP6","sentence_id":"S5","phrase":"解决多模态融合中的信息不均衡和模态偏倚","normalized_question":"如何提升多模态信息融合的稳定性与鲁棒性？","confidence":0.93},{"phrase_id":"RQP7","sentence_id":"S6","phrase":"降低模型对社交图关系数据的依赖","normalized_question":"如何构建不依赖完整社交图关系数据的检测框架？","confidence":0.96}],"structured_research_questions":[{"research_question_id":"RQ1","role":"main_question","parent_question_id":null,"question":"如何在真实应用场景中实现高效、准确且稳定的社交媒体机器人检测？","question_type":"综合任务定义型","research_object":"社交媒体机器人检测","research_targets":["检测准确性","检测效率","模型稳定性","实际应用能力"],"constraints":["数据获取受限","计算资源受限","多模态数据不完整"],"evidence_sentence_ids":["S1","S4"],"source_phrase_ids":["RQP1","RQP5"],"confidence":0.98},{"research_question_id":"RQ2","role":"sub_question","parent_question_id":"RQ1","question":"如何缓解多模态数据稀疏、噪声干扰、信息不均衡和单一模态偏倚，提升多模态融合效果？","question_type":"多模态融合优化型","research_object":"多模态社交媒体机器人检测模型","research_targets":["多视图信息融合","模态权重自适应","融合稳定性","分类性能"],"constraints":["数据稀疏","噪声干扰","模态缺失","算力需求较高"],"evidence_sentence_ids":["S2","S5"],"source_phrase_ids":["RQP2","RQP3","RQP6"],"confidence":0.96},{"research_question_id":"RQ3","role":"sub_question","parent_question_id":"RQ1","question":"如何在社交图关系数据难以获取的条件下保持检测性能，并降低资源消耗和模型数据依赖？","question_type":"数据依赖消减型","research_object":"基于社交图关系的机器人检测模型","research_targets":["降低图关系数据依赖","知识迁移","模型泛化能力","资源消耗控制"],"constraints":["平台API权限限制","隐私保护政策","社交图结构不完整"],"evidence_sentence_ids":["S3","S6"],"source_phrase_ids":["RQP4","RQP7"],"confidence":0.97}],"research_question_statistics":{"document_page_count":1,"analyzed_section_count":2,"research_question_sentence_count":3,"explicit_question_sentence_count":1,"implicit_question_sentence_count":2,"research_question_phrase_count":3,"structured_question_count":3,"main_question_count":1,"sub_question_count":2,"question_type_distribution":[{"question_type":"综合任务定义型","count":1,"percentage":33.33},{"question_type":"多模态融合优化型","count":1,"percentage":33.33},{"question_type":"数据依赖消减型","count":1,"percentage":33.33}],"average_confidence":0.95}},"meta":{"fixed_demo_output":true,"format_requirements":{"language":"zh","document_scope":"abstract_and_introduction","preserve_section_hierarchy":true,"sentence_segmentation":"auto","recognize_explicit_questions":true,"recognize_implicit_questions":true,"return_source_section":true,"return_page_number":true,"minimum_confidence":0.75},"request_id":"req_research_question_intro_txt_202607200001","elapsed_ms":1842}}}]},
      "citation-sentiment": {"group":"引用句识别工具","title":"引用情感识别","documentType":"citation-sentiment","languageCode":"en","languageName":"英文","description":"从科技文献全文中自动识别带有引文标记的句子，结合引用句上下文和引文元数据，判断原文作者对被引研究价值的态度属于支持、中立或有局限性。","features":"单文件识别、批量文件识别、全文引用句抽取、引文标记定位、上下文窗口分析、引文元数据匹配、支持/中立/有局限性三分类、证据短语提取、置信度输出、情感统计摘要","scenarios":"科研成果影响力分析、引文价值评价、学术传播研究、文献综述辅助、批量引文分析","endpoint":"/api/v1/citation/sentiment/file","fileEndpoint":"/api/v1/citation/sentiment/file","batchFileEndpoint":"/api/v1/citation/sentiment/files","inputModes":["file","batch"],"modeLabels":{"file":"单文件","batch":"批量文件"},"supportsFileUpload":true,"supportsBatchUpload":true,"acceptedFiles":[".pdf",".docx",".txt"],"maxFileSizeMB":50,"maxBatchFiles":20,"documentTarget":"科技文献全文、引用句、上下文和引文元数据","fileProcessingHint":"上传一个PDF、DOCX或TXT文件，系统自动抽取引用句、上下文并匹配参考文献元数据","batchProcessingHint":"逐文件抽取引用句并完成支持、中立、有局限性三分类，返回结构化清单与统计摘要","params":[["file","file","conditional","单文件模式必填：科技文献全文文件"],["files","file[]","conditional","批量文件模式必填：最多20个科技文献全文文件"],["analysis_settings","object","required","引用句抽取、上下文窗口、元数据匹配和输出要求"],["citation_extraction_mode","string","optional","auto_extract或provided_citations，默认auto_extract"],["context_window","integer","optional","引用句前后文窗口，默认1句"],["citation_metadata","object[]","optional","高级可选项：仅在文档缺少参考文献列表、自动解析失败或需要人工校正时提供；默认从参考文献列表自动解析"],["return_context","boolean","optional","是否返回上下文片段，默认true"],["return_position","boolean","optional","是否返回页码和章节，默认true"],["return_citation_metadata","boolean","optional","是否返回匹配后的引文元数据，默认true"],["minimum_confidence","number","optional","最低置信度，默认0.75"],["max_concurrency","integer","optional","批量任务并发数，默认3"],["continue_on_error","boolean","optional","单文件失败时是否继续处理，默认true"]],"payload":{"analysis_settings":{"language":"en","citation_extraction_mode":"auto_extract","context_window":1,"parse_reference_metadata":true,"return_context":true,"return_position":true,"return_citation_metadata":true,"manual_metadata_override":false,"minimum_confidence":0.75},"citation_metadata":[{"reference_id":"REF4_REF11","citation_marker":"[4, 11]","cited_authors":["Brooks et al.","Couairon et al."],"work_name":"InstructPix2Pix and DiffEdit","method_category":"Diffusion-based visual customization"},{"reference_id":"REF15_REF29","citation_marker":"[15, 29]","cited_authors":["Fu et al.","Huang et al."],"work_name":"MGIE and SmartEdit","method_category":"MLLM-assisted visual customization"},{"reference_id":"REF70_REF71","citation_marker":"[70, 71]","cited_authors":["Previous affective image generation studies"],"work_name":"Emotion-perception image generation methods","method_category":"Affective image generation"},{"reference_id":"REF48","citation_marker":"[48]","cited_authors":["Psychological study authors"],"work_name":"Study of visual elements and emotion elicitation","method_category":"Psychology of visual emotion"},{"reference_id":"REF39_REF41_REF7_REF42","citation_marker":"[39, 41, 7, 42]","cited_authors":["Model-editing researchers"],"work_name":"Model editing for low-resource alignment","method_category":"Model editing"},{"reference_id":"REF13_REF53","citation_marker":"[13, 53]","cited_authors":["Dhariwal and Nichol","Diffusion-model researchers"],"work_name":"Diffusion models for image generation","method_category":"Image generation"},{"reference_id":"REF50_REF46","citation_marker":"[50, 46]","cited_authors":["Qu et al.","OpenAI"],"work_name":"ChatGPT-assisted image layout generation","method_category":"LLM-assisted diffusion"}]},"sampleFileName":"Towards_LLM-centric_Affective_Visual_Customization_EPEM.pdf","sampleFileSize":"1.36 MB","demoFileSizeBytes":1428872,"demoFileSha256":"d1037be735339a49205aa968192446fe001eab25aba893c114a433f47a733eca","demoFileFnv1a32":"d28db6ef","batchSampleFileNames":["Towards_LLM-centric_Affective_Visual_Customization_EPEM.pdf","引用情感识别_多模态方法引用片段.txt","引用情感识别_图关系方法引用片段.txt"],"demoFileResult":{"code":200,"message":"success","data":{"tool":"引用情感识别","input_type":"file","input":{"file_name":"Towards_LLM-centric_Affective_Visual_Customization_EPEM.pdf","file_format":"PDF","file_size":"1.36 MB","document_parse_status":"success","citation_extraction_status":"success","reference_metadata_match_status":"success"},"document":{"title":"Towards LLM-centric Affective Visual Customization via Efficient and Precise Emotion Manipulating","authors":["Jiamin Luo","Xuqian Gu","Jingjing Wang","Jiahong Lu"],"language":"en","page_count":10,"venue":"The ACM Web Conference 2026","analysis_scope":["1 Introduction","2 Related Work"]},"citation_sentiment_results":[{"citation_id":"CIT1","citation_markers":["[4]","[11]"],"citation_sentence":"Most existing studies [4, 11] on visual customization leverage different generative models to generate the edited images.","sentiment":"中立","sentiment_code":"neutral","evidence_phrase":"leverage different generative models","context":{"previous_sentence":"Visual customization routinely focuses on employing various control conditions to edit objects in images.","current_sentence":"Most existing studies [4, 11] on visual customization leverage different generative models to generate the edited images.","next_sentence":"A small amount of recent studies [15, 29] have explored the use of Multimodal Large Language Models to assist diffusion models."},"citation_metadata":{"reference_id":"REF4_REF11","citation_marker":"[4, 11]","cited_authors":["Brooks et al.","Couairon et al."],"work_name":"InstructPix2Pix and DiffEdit","method_category":"Diffusion-based visual customization"},"source_position":{"page_number":2,"source_section":"1 Introduction"},"confidence":0.96},{"citation_id":"CIT2","citation_markers":["[15]","[29]"],"citation_sentence":"A small amount of recent studies [15, 29] have explored the use of Multimodal Large Language Models to assist diffusion models aligning conditions and images.","sentiment":"中立","sentiment_code":"neutral","evidence_phrase":"have explored the use of Multimodal Large Language Models","context":{"previous_sentence":"Most existing studies use GANs, VAEs or diffusion models to generate edited images.","current_sentence":"A small amount of recent studies [15, 29] have explored the use of Multimodal Large Language Models to assist diffusion models aligning conditions and images.","next_sentence":"Despite this progress, these approaches mainly edit objective concepts and remain limited in manipulating subjective emotions."},"citation_metadata":{"reference_id":"REF15_REF29","citation_marker":"[15, 29]","cited_authors":["Fu et al.","Huang et al."],"work_name":"MGIE and SmartEdit","method_category":"MLLM-assisted visual customization"},"source_position":{"page_number":2,"source_section":"1 Introduction"},"confidence":0.95},{"citation_id":"CIT3","citation_markers":["[4]","[11]","[15]","[29]"],"citation_sentence":"Despite these efforts achieving great progress, they focus on editing objective concepts in images and are limited in manipulating subjective emotions inherent in images.","sentiment":"有局限性","sentiment_code":"limitation","evidence_phrase":"are limited in manipulating subjective emotions","context":{"previous_sentence":"Existing generative and MLLM-assisted customization methods have made substantial progress.","current_sentence":"Despite these efforts achieving great progress, they focus on editing objective concepts in images and are limited in manipulating subjective emotions inherent in images.","next_sentence":"A few studies [70, 71] focus on generating emotion-perception images, but they are not chat-paradigm."},"citation_metadata":{"reference_id":"REF4_REF11_REF15_REF29","citation_marker":"[4, 11, 15, 29]","cited_authors":["Brooks et al.","Couairon et al.","Fu et al.","Huang et al."],"work_name":"Existing diffusion-based and MLLM-assisted visual customization methods","method_category":"Visual customization"},"source_position":{"page_number":2,"source_section":"1 Introduction"},"confidence":0.98},{"citation_id":"CIT4","citation_markers":["[70]","[71]"],"citation_sentence":"A few studies [70, 71] have focused on generating emotion-perception images, while they are not chat-paradigm, making it difficult to understand editing instructions and adapt to user interaction.","sentiment":"有局限性","sentiment_code":"limitation","evidence_phrase":"they are not chat-paradigm","context":{"previous_sentence":"Existing customization methods remain limited in manipulating subjective emotions.","current_sentence":"A few studies [70, 71] have focused on generating emotion-perception images, while they are not chat-paradigm, making it difficult to understand editing instructions and adapt to user interaction.","next_sentence":"Building on these observations, the paper proposes the L-AVC task."},"citation_metadata":{"reference_id":"REF70_REF71","citation_marker":"[70, 71]","cited_authors":["Previous affective image generation studies"],"work_name":"Emotion-perception image generation methods","method_category":"Affective image generation"},"source_position":{"page_number":2,"source_section":"1 Introduction"},"confidence":0.98},{"citation_id":"CIT5","citation_markers":["[48]"],"citation_sentence":"Psychological studies [48] have demonstrated that specific visual elements are often responsible for evoking emotions.","sentiment":"支持","sentiment_code":"support","evidence_phrase":"have demonstrated that specific visual elements","context":{"previous_sentence":"The L-AVC task requires editing inherently subjective emotions.","current_sentence":"Psychological studies [48] have demonstrated that specific visual elements are often responsible for evoking emotions.","next_sentence":"The paper therefore uses subjective emotions as a bridge between visual elements and the emotions they evoke."},"citation_metadata":{"reference_id":"REF48","citation_marker":"[48]","cited_authors":["Psychological study authors"],"work_name":"Study of visual elements and emotion elicitation","method_category":"Psychology of visual emotion"},"source_position":{"page_number":2,"source_section":"1 Introduction"},"confidence":0.97},{"citation_id":"CIT6","citation_markers":["[39]","[41]","[7]","[42]"],"citation_sentence":"Some studies [39, 41] attempt to leverage model editing [7, 42] to achieve efficient alignment on low-resource corpora.","sentiment":"支持","sentiment_code":"support","evidence_phrase":"achieve efficient alignment on low-resource corpora","context":{"previous_sentence":"Constructing large-scale aligned corpora for emotion conversion is difficult and expensive.","current_sentence":"Some studies [39, 41] attempt to leverage model editing [7, 42] to achieve efficient alignment on low-resource corpora.","next_sentence":"Inspired by these studies, the paper explores low-cost model editing for inter-emotion semantic alignment."},"citation_metadata":{"reference_id":"REF39_REF41_REF7_REF42","citation_marker":"[39, 41, 7, 42]","cited_authors":["Model-editing researchers"],"work_name":"Model editing for low-resource alignment","method_category":"Model editing"},"source_position":{"page_number":2,"source_section":"1 Introduction"},"confidence":0.96},{"citation_id":"CIT7","citation_markers":["[13]","[53]"],"citation_sentence":"The rise of diffusion models has ignited a surge in the field of image generation [13, 53].","sentiment":"支持","sentiment_code":"support","evidence_phrase":"has ignited a surge","context":{"previous_sentence":"The related-work section begins with visual customization.","current_sentence":"The rise of diffusion models has ignited a surge in the field of image generation [13, 53].","next_sentence":"Visual customization focuses on modifying desired elements while maintaining semantically unrelated content."},"citation_metadata":{"reference_id":"REF13_REF53","citation_marker":"[13, 53]","cited_authors":["Dhariwal and Nichol","Diffusion-model researchers"],"work_name":"Diffusion models for image generation","method_category":"Image generation"},"source_position":{"page_number":2,"source_section":"2 Related Work · Visual Customization"},"confidence":0.94},{"citation_id":"CIT8","citation_markers":["[50]","[46]"],"citation_sentence":"Qu et al. [50] utilize ChatGPT [46] to generate image layouts and employ a diffusion model conditioned on prompts and layouts to synthesize images.","sentiment":"中立","sentiment_code":"neutral","evidence_phrase":"utilize ChatGPT to generate image layouts","context":{"previous_sentence":"Several studies use the semantic understanding capability of LLMs to enhance text-conditioned generation.","current_sentence":"Qu et al. [50] utilize ChatGPT [46] to generate image layouts and employ a diffusion model conditioned on prompts and layouts to synthesize images.","next_sentence":"Other studies transfer knowledge from LLMs to diffusion models or jointly train MLLMs and editing models."},"citation_metadata":{"reference_id":"REF50_REF46","citation_marker":"[50, 46]","cited_authors":["Qu et al.","OpenAI"],"work_name":"ChatGPT-assisted image layout generation","method_category":"LLM-assisted diffusion"},"source_position":{"page_number":3,"source_section":"2 Related Work · LLM-assisted Diffusion Models"},"confidence":0.95}],"citation_sentiment_statistics":{"citation_sentence_count":8,"support_count":3,"neutral_count":3,"limitation_count":2,"sentiment_distribution":[{"sentiment":"支持","count":3,"percentage":37.5},{"sentiment":"中立","count":3,"percentage":37.5},{"sentiment":"有局限性","count":2,"percentage":25.0}],"average_confidence":0.9613}},"meta":{"fixed_demo_output":true,"fixed_demo_document":"Towards LLM-centric Affective Visual Customization via Efficient and Precise Emotion Manipulating","citation_metadata_source":"auto_parsed_from_reference_list","analysis_settings":{"language":"en","citation_extraction_mode":"auto_extract","context_window":1,"parse_reference_metadata":true,"return_context":true,"return_position":true,"return_citation_metadata":true,"manual_metadata_override":false,"minimum_confidence":0.75},"request_id":"req_citation_sentiment_epem_file_202607200001","elapsed_ms":1546}},"demoBatchFileResult":{"code":200,"message":"batch_completed","data":{"batch_id":"batch_citation_sentiment_files_202607200001","input_type":"files","total":3,"success_count":3,"failed_count":0,"results":[{"index":1,"file_name":"Towards_LLM-centric_Affective_Visual_Customization_EPEM.pdf","status":"success","code":200,"result":{"tool":"引用情感识别","input_type":"file","input":{"file_name":"Towards_LLM-centric_Affective_Visual_Customization_EPEM.pdf","file_format":"PDF","file_size":"1.36 MB","document_parse_status":"success","citation_extraction_status":"success","reference_metadata_match_status":"success"},"document":{"title":"Towards LLM-centric Affective Visual Customization via Efficient and Precise Emotion Manipulating","authors":["Jiamin Luo","Xuqian Gu","Jingjing Wang","Jiahong Lu"],"language":"en","page_count":10,"venue":"The ACM Web Conference 2026","analysis_scope":["1 Introduction","2 Related Work"]},"citation_sentiment_results":[{"citation_id":"CIT1","citation_markers":["[4]","[11]"],"citation_sentence":"Most existing studies [4, 11] on visual customization leverage different generative models to generate the edited images.","sentiment":"中立","sentiment_code":"neutral","evidence_phrase":"leverage different generative models","context":{"previous_sentence":"Visual customization routinely focuses on employing various control conditions to edit objects in images.","current_sentence":"Most existing studies [4, 11] on visual customization leverage different generative models to generate the edited images.","next_sentence":"A small amount of recent studies [15, 29] have explored the use of Multimodal Large Language Models to assist diffusion models."},"citation_metadata":{"reference_id":"REF4_REF11","citation_marker":"[4, 11]","cited_authors":["Brooks et al.","Couairon et al."],"work_name":"InstructPix2Pix and DiffEdit","method_category":"Diffusion-based visual customization"},"source_position":{"page_number":2,"source_section":"1 Introduction"},"confidence":0.96},{"citation_id":"CIT2","citation_markers":["[15]","[29]"],"citation_sentence":"A small amount of recent studies [15, 29] have explored the use of Multimodal Large Language Models to assist diffusion models aligning conditions and images.","sentiment":"中立","sentiment_code":"neutral","evidence_phrase":"have explored the use of Multimodal Large Language Models","context":{"previous_sentence":"Most existing studies use GANs, VAEs or diffusion models to generate edited images.","current_sentence":"A small amount of recent studies [15, 29] have explored the use of Multimodal Large Language Models to assist diffusion models aligning conditions and images.","next_sentence":"Despite this progress, these approaches mainly edit objective concepts and remain limited in manipulating subjective emotions."},"citation_metadata":{"reference_id":"REF15_REF29","citation_marker":"[15, 29]","cited_authors":["Fu et al.","Huang et al."],"work_name":"MGIE and SmartEdit","method_category":"MLLM-assisted visual customization"},"source_position":{"page_number":2,"source_section":"1 Introduction"},"confidence":0.95},{"citation_id":"CIT3","citation_markers":["[4]","[11]","[15]","[29]"],"citation_sentence":"Despite these efforts achieving great progress, they focus on editing objective concepts in images and are limited in manipulating subjective emotions inherent in images.","sentiment":"有局限性","sentiment_code":"limitation","evidence_phrase":"are limited in manipulating subjective emotions","context":{"previous_sentence":"Existing generative and MLLM-assisted customization methods have made substantial progress.","current_sentence":"Despite these efforts achieving great progress, they focus on editing objective concepts in images and are limited in manipulating subjective emotions inherent in images.","next_sentence":"A few studies [70, 71] focus on generating emotion-perception images, but they are not chat-paradigm."},"citation_metadata":{"reference_id":"REF4_REF11_REF15_REF29","citation_marker":"[4, 11, 15, 29]","cited_authors":["Brooks et al.","Couairon et al.","Fu et al.","Huang et al."],"work_name":"Existing diffusion-based and MLLM-assisted visual customization methods","method_category":"Visual customization"},"source_position":{"page_number":2,"source_section":"1 Introduction"},"confidence":0.98},{"citation_id":"CIT4","citation_markers":["[70]","[71]"],"citation_sentence":"A few studies [70, 71] have focused on generating emotion-perception images, while they are not chat-paradigm, making it difficult to understand editing instructions and adapt to user interaction.","sentiment":"有局限性","sentiment_code":"limitation","evidence_phrase":"they are not chat-paradigm","context":{"previous_sentence":"Existing customization methods remain limited in manipulating subjective emotions.","current_sentence":"A few studies [70, 71] have focused on generating emotion-perception images, while they are not chat-paradigm, making it difficult to understand editing instructions and adapt to user interaction.","next_sentence":"Building on these observations, the paper proposes the L-AVC task."},"citation_metadata":{"reference_id":"REF70_REF71","citation_marker":"[70, 71]","cited_authors":["Previous affective image generation studies"],"work_name":"Emotion-perception image generation methods","method_category":"Affective image generation"},"source_position":{"page_number":2,"source_section":"1 Introduction"},"confidence":0.98},{"citation_id":"CIT5","citation_markers":["[48]"],"citation_sentence":"Psychological studies [48] have demonstrated that specific visual elements are often responsible for evoking emotions.","sentiment":"支持","sentiment_code":"support","evidence_phrase":"have demonstrated that specific visual elements","context":{"previous_sentence":"The L-AVC task requires editing inherently subjective emotions.","current_sentence":"Psychological studies [48] have demonstrated that specific visual elements are often responsible for evoking emotions.","next_sentence":"The paper therefore uses subjective emotions as a bridge between visual elements and the emotions they evoke."},"citation_metadata":{"reference_id":"REF48","citation_marker":"[48]","cited_authors":["Psychological study authors"],"work_name":"Study of visual elements and emotion elicitation","method_category":"Psychology of visual emotion"},"source_position":{"page_number":2,"source_section":"1 Introduction"},"confidence":0.97},{"citation_id":"CIT6","citation_markers":["[39]","[41]","[7]","[42]"],"citation_sentence":"Some studies [39, 41] attempt to leverage model editing [7, 42] to achieve efficient alignment on low-resource corpora.","sentiment":"支持","sentiment_code":"support","evidence_phrase":"achieve efficient alignment on low-resource corpora","context":{"previous_sentence":"Constructing large-scale aligned corpora for emotion conversion is difficult and expensive.","current_sentence":"Some studies [39, 41] attempt to leverage model editing [7, 42] to achieve efficient alignment on low-resource corpora.","next_sentence":"Inspired by these studies, the paper explores low-cost model editing for inter-emotion semantic alignment."},"citation_metadata":{"reference_id":"REF39_REF41_REF7_REF42","citation_marker":"[39, 41, 7, 42]","cited_authors":["Model-editing researchers"],"work_name":"Model editing for low-resource alignment","method_category":"Model editing"},"source_position":{"page_number":2,"source_section":"1 Introduction"},"confidence":0.96},{"citation_id":"CIT7","citation_markers":["[13]","[53]"],"citation_sentence":"The rise of diffusion models has ignited a surge in the field of image generation [13, 53].","sentiment":"支持","sentiment_code":"support","evidence_phrase":"has ignited a surge","context":{"previous_sentence":"The related-work section begins with visual customization.","current_sentence":"The rise of diffusion models has ignited a surge in the field of image generation [13, 53].","next_sentence":"Visual customization focuses on modifying desired elements while maintaining semantically unrelated content."},"citation_metadata":{"reference_id":"REF13_REF53","citation_marker":"[13, 53]","cited_authors":["Dhariwal and Nichol","Diffusion-model researchers"],"work_name":"Diffusion models for image generation","method_category":"Image generation"},"source_position":{"page_number":2,"source_section":"2 Related Work · Visual Customization"},"confidence":0.94},{"citation_id":"CIT8","citation_markers":["[50]","[46]"],"citation_sentence":"Qu et al. [50] utilize ChatGPT [46] to generate image layouts and employ a diffusion model conditioned on prompts and layouts to synthesize images.","sentiment":"中立","sentiment_code":"neutral","evidence_phrase":"utilize ChatGPT to generate image layouts","context":{"previous_sentence":"Several studies use the semantic understanding capability of LLMs to enhance text-conditioned generation.","current_sentence":"Qu et al. [50] utilize ChatGPT [46] to generate image layouts and employ a diffusion model conditioned on prompts and layouts to synthesize images.","next_sentence":"Other studies transfer knowledge from LLMs to diffusion models or jointly train MLLMs and editing models."},"citation_metadata":{"reference_id":"REF50_REF46","citation_marker":"[50, 46]","cited_authors":["Qu et al.","OpenAI"],"work_name":"ChatGPT-assisted image layout generation","method_category":"LLM-assisted diffusion"},"source_position":{"page_number":3,"source_section":"2 Related Work · LLM-assisted Diffusion Models"},"confidence":0.95}],"citation_sentiment_statistics":{"citation_sentence_count":8,"support_count":3,"neutral_count":3,"limitation_count":2,"sentiment_distribution":[{"sentiment":"支持","count":3,"percentage":37.5},{"sentiment":"中立","count":3,"percentage":37.5},{"sentiment":"有局限性","count":2,"percentage":25.0}],"average_confidence":0.9613}}},{"index":2,"file_name":"引用情感识别_多模态方法引用片段.txt","status":"success","code":200,"result":{"tool":"引用情感识别","input_type":"file","input":{"file_name":"引用情感识别_多模态方法引用片段.txt","file_format":"TXT","file_size":"509 B","document_parse_status":"success","citation_extraction_status":"success","reference_metadata_match_status":"success"},"document":{"title":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架","language":"zh","page_count":null,"analysis_scope":"full_text"},"citation_sentiment_results":[{"citation_id":"CIT1","citation_markers":["[34]"],"citation_sentence":"Wu[34]等人提出的MSM-BD方法结合了用户头像、用户属性和推文文本等多模态特征，利用专门设计的编码器对各模态信息进行提取，并通过跨模态残差交叉注意力模块实现多模态特征融合。","sentiment":"中立","sentiment_code":"neutral","evidence_phrase":"提出的MSM-BD方法结合了","context":{"previous_sentence":"当前基于多模态相关的研究主要从特征融合和分类结果集成两个方向展开。","current_sentence":"Wu[34]等人提出的MSM-BD方法结合了用户头像、用户属性和推文文本等多模态特征，利用专门设计的编码器对各模态信息进行提取，并通过跨模态残差交叉注意力模块实现多模态特征融合。","next_sentence":"Gong[35]等人提出BotSAI框架，通过整合用户多模态信息提升检测准确性与跨模态表示一致性。"},"citation_metadata":{"reference_id":"REF34","citation_marker":"[34]","cited_authors":["Wu"],"work_name":"MSM-BD","method_category":"多模态特征融合"},"source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.96},{"citation_id":"CIT2","citation_markers":["[36]"],"citation_sentence":"Feng[36]等人提出了一种名为SATAR的自监督学习方法，该方法融合了文本语义信息与用户行为特征，构建无监督表示学习框架。","sentiment":"中立","sentiment_code":"neutral","evidence_phrase":"提出了一种名为SATAR的自监督学习方法","context":{"previous_sentence":"Gong[35]等人提出BotSAI框架，通过整合用户多模态信息提升检测准确性与跨模态表示一致性。","current_sentence":"Feng[36]等人提出了一种名为SATAR的自监督学习方法，该方法融合了文本语义信息与用户行为特征，构建无监督表示学习框架。","next_sentence":"Guo等人[37]的BGSRD模型融合了BERT文本语义信息和GCN图结构关系。"},"citation_metadata":{"reference_id":"REF36","citation_marker":"[36]","cited_authors":["Feng"],"work_name":"SATAR","method_category":"自监督多模态表示学习"},"source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.94},{"citation_id":"CIT3","citation_markers":["[37]"],"citation_sentence":"Guo等人[37]的BGSRD模型融合了BERT的文本语义信息和GCN的图结构关系，联合训练后显著提高检测准确率。","sentiment":"支持","sentiment_code":"support","evidence_phrase":"联合训练后显著提高检测准确率","context":{"previous_sentence":"Feng[36]等人提出SATAR自监督学习方法，融合文本语义信息与用户行为特征。","current_sentence":"Guo等人[37]的BGSRD模型融合了BERT的文本语义信息和GCN的图结构关系，联合训练后显著提高检测准确率。","next_sentence":"Liu等人[38]的BotMoE方法利用社区感知的专家混合层整合元数据、文本和网络结构特征。"},"citation_metadata":{"reference_id":"REF37","citation_marker":"[37]","cited_authors":["Guo"],"work_name":"BGSRD","method_category":"BERT与GCN联合建模"},"source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.98},{"citation_id":"CIT4","citation_markers":["[34-43]"],"citation_sentence":"尽管现有的基于多模态数据的研究方法在提升社交媒体机器人检测性能方面表现出了显著优势，但不同模态之间在稀疏性和表达能力上的差异日益突出，导致融合过程中面临信息不均衡等问题。","sentiment":"有局限性","sentiment_code":"limitation","evidence_phrase":"但不同模态之间在稀疏性和表达能力上的差异日益突出","context":{"previous_sentence":"Carley等[43]研发BotBuster系统，使用混合专家架构分析账户信息的特定片段。","current_sentence":"尽管现有的基于多模态数据的研究方法在提升社交媒体机器人检测性能方面表现出了显著优势，但不同模态之间在稀疏性和表达能力上的差异日益突出，导致融合过程中面临信息不均衡等问题。","next_sentence":"同时，此类模型通常结构复杂、算力需求较大，难以高效适应大规模检测任务。"},"citation_metadata":{"reference_id":"REF34_REF43","citation_marker":"[34-43]","cited_authors":["多篇多模态机器人检测研究"],"work_name":"多模态检测方法集合","method_category":"多模态特征融合与结果集成"},"source_position":{"page_number":17,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.97}],"citation_sentiment_statistics":{"citation_sentence_count":4,"support_count":1,"neutral_count":2,"limitation_count":1,"sentiment_distribution":[{"sentiment":"支持","count":1,"percentage":25.0},{"sentiment":"中立","count":2,"percentage":50.0},{"sentiment":"有局限性","count":1,"percentage":25.0}],"average_confidence":0.9625}}},{"index":3,"file_name":"引用情感识别_图关系方法引用片段.txt","status":"success","code":200,"result":{"tool":"引用情感识别","input_type":"file","input":{"file_name":"引用情感识别_图关系方法引用片段.txt","file_format":"TXT","file_size":"470 B","document_parse_status":"success","citation_extraction_status":"success","reference_metadata_match_status":"success"},"document":{"title":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架","language":"zh","page_count":null,"analysis_scope":"full_text"},"citation_sentiment_results":[{"citation_id":"CIT5","citation_markers":["[44]"],"citation_sentence":"Lyu[44]等人提出DCGNN模型，通过构建包含时间关系和社交关系的图结构，有效地利用社交图关系数据捕捉用户的爆发行为和静态特征，从而提高了社交机器人检测的准确性。","sentiment":"支持","sentiment_code":"support","evidence_phrase":"从而提高了社交机器人检测的准确性","context":{"previous_sentence":"基于用户图关系的方法能够捕捉社交网络中的复杂交互关系和结构特征。","current_sentence":"Lyu[44]等人提出DCGNN模型，通过构建包含时间关系和社交关系的图结构，有效地利用社交图关系数据捕捉用户的爆发行为和静态特征，从而提高了社交机器人检测的准确性。","next_sentence":"Guyan等人提出PEGNN[45]模型，利用图神经网络捕捉用户之间的复杂交互关系。"},"citation_metadata":{"reference_id":"REF44","citation_marker":"[44]","cited_authors":["Lyu"],"work_name":"DCGNN","method_category":"社交图关系建模"},"source_position":{"page_number":17,"source_section":"1.2.2 基于社交图关系数据建模的社交媒体机器人检测方法"},"confidence":0.97},{"citation_id":"CIT6","citation_markers":["[44-53]"],"citation_sentence":"上述基于社交图关系数据建模的方法在捕捉用户间复杂交互模式方面具有优势，但是社交图关系型数据的获取通常依赖平台API权限，受到访问限制和隐私保护政策制约，在实际应用中往往难以获得完整、高质量的社交网络结构。","sentiment":"有局限性","sentiment_code":"limitation","evidence_phrase":"但是社交图关系型数据的获取通常依赖平台API权限","context":{"previous_sentence":"Yang和Wu[53]等人提出seBot框架，通过结合社区结构和对抗性行为信息提高机器人检测性能。","current_sentence":"上述基于社交图关系数据建模的方法在捕捉用户间复杂交互模式方面具有优势，但是社交图关系型数据的获取通常依赖平台API权限，受到访问限制和隐私保护政策制约，在实际应用中往往难以获得完整、高质量的社交网络结构。","next_sentence":"这导致依赖图结构的检测模型在实际部署中难以获取充足的关键输入数据。"},"citation_metadata":{"reference_id":"REF44_REF53","citation_marker":"[44-53]","cited_authors":["多篇图关系建模研究"],"work_name":"社交图关系检测方法集合","method_category":"图神经网络与异构图建模"},"source_position":{"page_number":18,"source_section":"1.2.2 基于社交图关系数据建模的社交媒体机器人检测方法"},"confidence":0.98}],"citation_sentiment_statistics":{"citation_sentence_count":2,"support_count":1,"neutral_count":0,"limitation_count":1,"sentiment_distribution":[{"sentiment":"支持","count":1,"percentage":50.0},{"sentiment":"中立","count":0,"percentage":0.0},{"sentiment":"有局限性","count":1,"percentage":50.0}],"average_confidence":0.975}}}]},"meta":{"analysis_settings":{"language":"zh","citation_extraction_mode":"auto_extract","context_window":1,"parse_reference_metadata":true,"return_context":true,"return_position":true,"return_citation_metadata":true,"minimum_confidence":0.75},"max_concurrency":3,"continue_on_error":true,"elapsed_ms":3486}},"response":{"code":200,"message":"batch_completed","data":{"batch_id":"batch_citation_sentiment_files_202607200001","input_type":"files","total":3,"success_count":3,"failed_count":0,"results":[{"index":1,"file_name":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架.pdf","status":"success","code":200,"result":{"tool":"引用情感识别","input_type":"file","input":{"file_name":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架.pdf","file_format":"PDF","file_size":"3.17 MB","document_parse_status":"success","citation_extraction_status":"success","reference_metadata_match_status":"success"},"document":{"title":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架","language":"zh","page_count":83,"analysis_scope":"full_text"},"citation_sentiment_results":[{"citation_id":"CIT1","citation_markers":["[34]"],"citation_sentence":"Wu[34]等人提出的MSM-BD方法结合了用户头像、用户属性和推文文本等多模态特征，利用专门设计的编码器对各模态信息进行提取，并通过跨模态残差交叉注意力模块实现多模态特征融合。","sentiment":"中立","sentiment_code":"neutral","evidence_phrase":"提出的MSM-BD方法结合了","context":{"previous_sentence":"当前基于多模态相关的研究主要从特征融合和分类结果集成两个方向展开。","current_sentence":"Wu[34]等人提出的MSM-BD方法结合了用户头像、用户属性和推文文本等多模态特征，利用专门设计的编码器对各模态信息进行提取，并通过跨模态残差交叉注意力模块实现多模态特征融合。","next_sentence":"Gong[35]等人提出BotSAI框架，通过整合用户多模态信息提升检测准确性与跨模态表示一致性。"},"citation_metadata":{"reference_id":"REF34","citation_marker":"[34]","cited_authors":["Wu"],"work_name":"MSM-BD","method_category":"多模态特征融合"},"source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.96},{"citation_id":"CIT2","citation_markers":["[36]"],"citation_sentence":"Feng[36]等人提出了一种名为SATAR的自监督学习方法，该方法融合了文本语义信息与用户行为特征，构建无监督表示学习框架。","sentiment":"中立","sentiment_code":"neutral","evidence_phrase":"提出了一种名为SATAR的自监督学习方法","context":{"previous_sentence":"Gong[35]等人提出BotSAI框架，通过整合用户多模态信息提升检测准确性与跨模态表示一致性。","current_sentence":"Feng[36]等人提出了一种名为SATAR的自监督学习方法，该方法融合了文本语义信息与用户行为特征，构建无监督表示学习框架。","next_sentence":"Guo等人[37]的BGSRD模型融合了BERT文本语义信息和GCN图结构关系。"},"citation_metadata":{"reference_id":"REF36","citation_marker":"[36]","cited_authors":["Feng"],"work_name":"SATAR","method_category":"自监督多模态表示学习"},"source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.94},{"citation_id":"CIT3","citation_markers":["[37]"],"citation_sentence":"Guo等人[37]的BGSRD模型融合了BERT的文本语义信息和GCN的图结构关系，联合训练后显著提高检测准确率。","sentiment":"支持","sentiment_code":"support","evidence_phrase":"联合训练后显著提高检测准确率","context":{"previous_sentence":"Feng[36]等人提出SATAR自监督学习方法，融合文本语义信息与用户行为特征。","current_sentence":"Guo等人[37]的BGSRD模型融合了BERT的文本语义信息和GCN的图结构关系，联合训练后显著提高检测准确率。","next_sentence":"Liu等人[38]的BotMoE方法利用社区感知的专家混合层整合元数据、文本和网络结构特征。"},"citation_metadata":{"reference_id":"REF37","citation_marker":"[37]","cited_authors":["Guo"],"work_name":"BGSRD","method_category":"BERT与GCN联合建模"},"source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.98},{"citation_id":"CIT4","citation_markers":["[34-43]"],"citation_sentence":"尽管现有的基于多模态数据的研究方法在提升社交媒体机器人检测性能方面表现出了显著优势，但不同模态之间在稀疏性和表达能力上的差异日益突出，导致融合过程中面临信息不均衡等问题。","sentiment":"有局限性","sentiment_code":"limitation","evidence_phrase":"但不同模态之间在稀疏性和表达能力上的差异日益突出","context":{"previous_sentence":"Carley等[43]研发BotBuster系统，使用混合专家架构分析账户信息的特定片段。","current_sentence":"尽管现有的基于多模态数据的研究方法在提升社交媒体机器人检测性能方面表现出了显著优势，但不同模态之间在稀疏性和表达能力上的差异日益突出，导致融合过程中面临信息不均衡等问题。","next_sentence":"同时，此类模型通常结构复杂、算力需求较大，难以高效适应大规模检测任务。"},"citation_metadata":{"reference_id":"REF34_REF43","citation_marker":"[34-43]","cited_authors":["多篇多模态机器人检测研究"],"work_name":"多模态检测方法集合","method_category":"多模态特征融合与结果集成"},"source_position":{"page_number":17,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.97},{"citation_id":"CIT5","citation_markers":["[44]"],"citation_sentence":"Lyu[44]等人提出DCGNN模型，通过构建包含时间关系和社交关系的图结构，有效地利用社交图关系数据捕捉用户的爆发行为和静态特征，从而提高了社交机器人检测的准确性。","sentiment":"支持","sentiment_code":"support","evidence_phrase":"从而提高了社交机器人检测的准确性","context":{"previous_sentence":"基于用户图关系的方法能够捕捉社交网络中的复杂交互关系和结构特征。","current_sentence":"Lyu[44]等人提出DCGNN模型，通过构建包含时间关系和社交关系的图结构，有效地利用社交图关系数据捕捉用户的爆发行为和静态特征，从而提高了社交机器人检测的准确性。","next_sentence":"Guyan等人提出PEGNN[45]模型，利用图神经网络捕捉用户之间的复杂交互关系。"},"citation_metadata":{"reference_id":"REF44","citation_marker":"[44]","cited_authors":["Lyu"],"work_name":"DCGNN","method_category":"社交图关系建模"},"source_position":{"page_number":17,"source_section":"1.2.2 基于社交图关系数据建模的社交媒体机器人检测方法"},"confidence":0.97},{"citation_id":"CIT6","citation_markers":["[44-53]"],"citation_sentence":"上述基于社交图关系数据建模的方法在捕捉用户间复杂交互模式方面具有优势，但是社交图关系型数据的获取通常依赖平台API权限，受到访问限制和隐私保护政策制约，在实际应用中往往难以获得完整、高质量的社交网络结构。","sentiment":"有局限性","sentiment_code":"limitation","evidence_phrase":"但是社交图关系型数据的获取通常依赖平台API权限","context":{"previous_sentence":"Yang和Wu[53]等人提出seBot框架，通过结合社区结构和对抗性行为信息提高机器人检测性能。","current_sentence":"上述基于社交图关系数据建模的方法在捕捉用户间复杂交互模式方面具有优势，但是社交图关系型数据的获取通常依赖平台API权限，受到访问限制和隐私保护政策制约，在实际应用中往往难以获得完整、高质量的社交网络结构。","next_sentence":"这导致依赖图结构的检测模型在实际部署中难以获取充足的关键输入数据。"},"citation_metadata":{"reference_id":"REF44_REF53","citation_marker":"[44-53]","cited_authors":["多篇图关系建模研究"],"work_name":"社交图关系检测方法集合","method_category":"图神经网络与异构图建模"},"source_position":{"page_number":18,"source_section":"1.2.2 基于社交图关系数据建模的社交媒体机器人检测方法"},"confidence":0.98}],"citation_sentiment_statistics":{"citation_sentence_count":6,"support_count":2,"neutral_count":2,"limitation_count":2,"sentiment_distribution":[{"sentiment":"支持","count":2,"percentage":33.33},{"sentiment":"中立","count":2,"percentage":33.33},{"sentiment":"有局限性","count":2,"percentage":33.33}],"average_confidence":0.9667}}},{"index":2,"file_name":"引用情感识别_多模态方法引用片段.txt","status":"success","code":200,"result":{"tool":"引用情感识别","input_type":"file","input":{"file_name":"引用情感识别_多模态方法引用片段.txt","file_format":"TXT","file_size":"509 B","document_parse_status":"success","citation_extraction_status":"success","reference_metadata_match_status":"success"},"document":{"title":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架","language":"zh","page_count":null,"analysis_scope":"full_text"},"citation_sentiment_results":[{"citation_id":"CIT1","citation_markers":["[34]"],"citation_sentence":"Wu[34]等人提出的MSM-BD方法结合了用户头像、用户属性和推文文本等多模态特征，利用专门设计的编码器对各模态信息进行提取，并通过跨模态残差交叉注意力模块实现多模态特征融合。","sentiment":"中立","sentiment_code":"neutral","evidence_phrase":"提出的MSM-BD方法结合了","context":{"previous_sentence":"当前基于多模态相关的研究主要从特征融合和分类结果集成两个方向展开。","current_sentence":"Wu[34]等人提出的MSM-BD方法结合了用户头像、用户属性和推文文本等多模态特征，利用专门设计的编码器对各模态信息进行提取，并通过跨模态残差交叉注意力模块实现多模态特征融合。","next_sentence":"Gong[35]等人提出BotSAI框架，通过整合用户多模态信息提升检测准确性与跨模态表示一致性。"},"citation_metadata":{"reference_id":"REF34","citation_marker":"[34]","cited_authors":["Wu"],"work_name":"MSM-BD","method_category":"多模态特征融合"},"source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.96},{"citation_id":"CIT2","citation_markers":["[36]"],"citation_sentence":"Feng[36]等人提出了一种名为SATAR的自监督学习方法，该方法融合了文本语义信息与用户行为特征，构建无监督表示学习框架。","sentiment":"中立","sentiment_code":"neutral","evidence_phrase":"提出了一种名为SATAR的自监督学习方法","context":{"previous_sentence":"Gong[35]等人提出BotSAI框架，通过整合用户多模态信息提升检测准确性与跨模态表示一致性。","current_sentence":"Feng[36]等人提出了一种名为SATAR的自监督学习方法，该方法融合了文本语义信息与用户行为特征，构建无监督表示学习框架。","next_sentence":"Guo等人[37]的BGSRD模型融合了BERT文本语义信息和GCN图结构关系。"},"citation_metadata":{"reference_id":"REF36","citation_marker":"[36]","cited_authors":["Feng"],"work_name":"SATAR","method_category":"自监督多模态表示学习"},"source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.94},{"citation_id":"CIT3","citation_markers":["[37]"],"citation_sentence":"Guo等人[37]的BGSRD模型融合了BERT的文本语义信息和GCN的图结构关系，联合训练后显著提高检测准确率。","sentiment":"支持","sentiment_code":"support","evidence_phrase":"联合训练后显著提高检测准确率","context":{"previous_sentence":"Feng[36]等人提出SATAR自监督学习方法，融合文本语义信息与用户行为特征。","current_sentence":"Guo等人[37]的BGSRD模型融合了BERT的文本语义信息和GCN的图结构关系，联合训练后显著提高检测准确率。","next_sentence":"Liu等人[38]的BotMoE方法利用社区感知的专家混合层整合元数据、文本和网络结构特征。"},"citation_metadata":{"reference_id":"REF37","citation_marker":"[37]","cited_authors":["Guo"],"work_name":"BGSRD","method_category":"BERT与GCN联合建模"},"source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.98},{"citation_id":"CIT4","citation_markers":["[34-43]"],"citation_sentence":"尽管现有的基于多模态数据的研究方法在提升社交媒体机器人检测性能方面表现出了显著优势，但不同模态之间在稀疏性和表达能力上的差异日益突出，导致融合过程中面临信息不均衡等问题。","sentiment":"有局限性","sentiment_code":"limitation","evidence_phrase":"但不同模态之间在稀疏性和表达能力上的差异日益突出","context":{"previous_sentence":"Carley等[43]研发BotBuster系统，使用混合专家架构分析账户信息的特定片段。","current_sentence":"尽管现有的基于多模态数据的研究方法在提升社交媒体机器人检测性能方面表现出了显著优势，但不同模态之间在稀疏性和表达能力上的差异日益突出，导致融合过程中面临信息不均衡等问题。","next_sentence":"同时，此类模型通常结构复杂、算力需求较大，难以高效适应大规模检测任务。"},"citation_metadata":{"reference_id":"REF34_REF43","citation_marker":"[34-43]","cited_authors":["多篇多模态机器人检测研究"],"work_name":"多模态检测方法集合","method_category":"多模态特征融合与结果集成"},"source_position":{"page_number":17,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.97}],"citation_sentiment_statistics":{"citation_sentence_count":4,"support_count":1,"neutral_count":2,"limitation_count":1,"sentiment_distribution":[{"sentiment":"支持","count":1,"percentage":25.0},{"sentiment":"中立","count":2,"percentage":50.0},{"sentiment":"有局限性","count":1,"percentage":25.0}],"average_confidence":0.9625}}},{"index":3,"file_name":"引用情感识别_图关系方法引用片段.txt","status":"success","code":200,"result":{"tool":"引用情感识别","input_type":"file","input":{"file_name":"引用情感识别_图关系方法引用片段.txt","file_format":"TXT","file_size":"470 B","document_parse_status":"success","citation_extraction_status":"success","reference_metadata_match_status":"success"},"document":{"title":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架","language":"zh","page_count":null,"analysis_scope":"full_text"},"citation_sentiment_results":[{"citation_id":"CIT5","citation_markers":["[44]"],"citation_sentence":"Lyu[44]等人提出DCGNN模型，通过构建包含时间关系和社交关系的图结构，有效地利用社交图关系数据捕捉用户的爆发行为和静态特征，从而提高了社交机器人检测的准确性。","sentiment":"支持","sentiment_code":"support","evidence_phrase":"从而提高了社交机器人检测的准确性","context":{"previous_sentence":"基于用户图关系的方法能够捕捉社交网络中的复杂交互关系和结构特征。","current_sentence":"Lyu[44]等人提出DCGNN模型，通过构建包含时间关系和社交关系的图结构，有效地利用社交图关系数据捕捉用户的爆发行为和静态特征，从而提高了社交机器人检测的准确性。","next_sentence":"Guyan等人提出PEGNN[45]模型，利用图神经网络捕捉用户之间的复杂交互关系。"},"citation_metadata":{"reference_id":"REF44","citation_marker":"[44]","cited_authors":["Lyu"],"work_name":"DCGNN","method_category":"社交图关系建模"},"source_position":{"page_number":17,"source_section":"1.2.2 基于社交图关系数据建模的社交媒体机器人检测方法"},"confidence":0.97},{"citation_id":"CIT6","citation_markers":["[44-53]"],"citation_sentence":"上述基于社交图关系数据建模的方法在捕捉用户间复杂交互模式方面具有优势，但是社交图关系型数据的获取通常依赖平台API权限，受到访问限制和隐私保护政策制约，在实际应用中往往难以获得完整、高质量的社交网络结构。","sentiment":"有局限性","sentiment_code":"limitation","evidence_phrase":"但是社交图关系型数据的获取通常依赖平台API权限","context":{"previous_sentence":"Yang和Wu[53]等人提出seBot框架，通过结合社区结构和对抗性行为信息提高机器人检测性能。","current_sentence":"上述基于社交图关系数据建模的方法在捕捉用户间复杂交互模式方面具有优势，但是社交图关系型数据的获取通常依赖平台API权限，受到访问限制和隐私保护政策制约，在实际应用中往往难以获得完整、高质量的社交网络结构。","next_sentence":"这导致依赖图结构的检测模型在实际部署中难以获取充足的关键输入数据。"},"citation_metadata":{"reference_id":"REF44_REF53","citation_marker":"[44-53]","cited_authors":["多篇图关系建模研究"],"work_name":"社交图关系检测方法集合","method_category":"图神经网络与异构图建模"},"source_position":{"page_number":18,"source_section":"1.2.2 基于社交图关系数据建模的社交媒体机器人检测方法"},"confidence":0.98}],"citation_sentiment_statistics":{"citation_sentence_count":2,"support_count":1,"neutral_count":0,"limitation_count":1,"sentiment_distribution":[{"sentiment":"支持","count":1,"percentage":50.0},{"sentiment":"中立","count":0,"percentage":0.0},{"sentiment":"有局限性","count":1,"percentage":50.0}],"average_confidence":0.975}}}]},"meta":{"analysis_settings":{"language":"zh","citation_extraction_mode":"auto_extract","context_window":1,"parse_reference_metadata":true,"return_context":true,"return_position":true,"return_citation_metadata":true,"minimum_confidence":0.75},"max_concurrency":3,"continue_on_error":true,"elapsed_ms":3486}},"demoFileFixtures":[{"file_name":"Towards_LLM-centric_Affective_Visual_Customization_EPEM.pdf","size_bytes":1428872,"sha256":"d1037be735339a49205aa968192446fe001eab25aba893c114a433f47a733eca","fnv1a32":"d28db6ef","result":{"code":200,"message":"success","data":{"tool":"引用情感识别","input_type":"file","input":{"file_name":"Towards_LLM-centric_Affective_Visual_Customization_EPEM.pdf","file_format":"PDF","file_size":"1.36 MB","document_parse_status":"success","citation_extraction_status":"success","reference_metadata_match_status":"success"},"document":{"title":"Towards LLM-centric Affective Visual Customization via Efficient and Precise Emotion Manipulating","authors":["Jiamin Luo","Xuqian Gu","Jingjing Wang","Jiahong Lu"],"language":"en","page_count":10,"venue":"The ACM Web Conference 2026","analysis_scope":["1 Introduction","2 Related Work"]},"citation_sentiment_results":[{"citation_id":"CIT1","citation_markers":["[4]","[11]"],"citation_sentence":"Most existing studies [4, 11] on visual customization leverage different generative models to generate the edited images.","sentiment":"中立","sentiment_code":"neutral","evidence_phrase":"leverage different generative models","context":{"previous_sentence":"Visual customization routinely focuses on employing various control conditions to edit objects in images.","current_sentence":"Most existing studies [4, 11] on visual customization leverage different generative models to generate the edited images.","next_sentence":"A small amount of recent studies [15, 29] have explored the use of Multimodal Large Language Models to assist diffusion models."},"citation_metadata":{"reference_id":"REF4_REF11","citation_marker":"[4, 11]","cited_authors":["Brooks et al.","Couairon et al."],"work_name":"InstructPix2Pix and DiffEdit","method_category":"Diffusion-based visual customization"},"source_position":{"page_number":2,"source_section":"1 Introduction"},"confidence":0.96},{"citation_id":"CIT2","citation_markers":["[15]","[29]"],"citation_sentence":"A small amount of recent studies [15, 29] have explored the use of Multimodal Large Language Models to assist diffusion models aligning conditions and images.","sentiment":"中立","sentiment_code":"neutral","evidence_phrase":"have explored the use of Multimodal Large Language Models","context":{"previous_sentence":"Most existing studies use GANs, VAEs or diffusion models to generate edited images.","current_sentence":"A small amount of recent studies [15, 29] have explored the use of Multimodal Large Language Models to assist diffusion models aligning conditions and images.","next_sentence":"Despite this progress, these approaches mainly edit objective concepts and remain limited in manipulating subjective emotions."},"citation_metadata":{"reference_id":"REF15_REF29","citation_marker":"[15, 29]","cited_authors":["Fu et al.","Huang et al."],"work_name":"MGIE and SmartEdit","method_category":"MLLM-assisted visual customization"},"source_position":{"page_number":2,"source_section":"1 Introduction"},"confidence":0.95},{"citation_id":"CIT3","citation_markers":["[4]","[11]","[15]","[29]"],"citation_sentence":"Despite these efforts achieving great progress, they focus on editing objective concepts in images and are limited in manipulating subjective emotions inherent in images.","sentiment":"有局限性","sentiment_code":"limitation","evidence_phrase":"are limited in manipulating subjective emotions","context":{"previous_sentence":"Existing generative and MLLM-assisted customization methods have made substantial progress.","current_sentence":"Despite these efforts achieving great progress, they focus on editing objective concepts in images and are limited in manipulating subjective emotions inherent in images.","next_sentence":"A few studies [70, 71] focus on generating emotion-perception images, but they are not chat-paradigm."},"citation_metadata":{"reference_id":"REF4_REF11_REF15_REF29","citation_marker":"[4, 11, 15, 29]","cited_authors":["Brooks et al.","Couairon et al.","Fu et al.","Huang et al."],"work_name":"Existing diffusion-based and MLLM-assisted visual customization methods","method_category":"Visual customization"},"source_position":{"page_number":2,"source_section":"1 Introduction"},"confidence":0.98},{"citation_id":"CIT4","citation_markers":["[70]","[71]"],"citation_sentence":"A few studies [70, 71] have focused on generating emotion-perception images, while they are not chat-paradigm, making it difficult to understand editing instructions and adapt to user interaction.","sentiment":"有局限性","sentiment_code":"limitation","evidence_phrase":"they are not chat-paradigm","context":{"previous_sentence":"Existing customization methods remain limited in manipulating subjective emotions.","current_sentence":"A few studies [70, 71] have focused on generating emotion-perception images, while they are not chat-paradigm, making it difficult to understand editing instructions and adapt to user interaction.","next_sentence":"Building on these observations, the paper proposes the L-AVC task."},"citation_metadata":{"reference_id":"REF70_REF71","citation_marker":"[70, 71]","cited_authors":["Previous affective image generation studies"],"work_name":"Emotion-perception image generation methods","method_category":"Affective image generation"},"source_position":{"page_number":2,"source_section":"1 Introduction"},"confidence":0.98},{"citation_id":"CIT5","citation_markers":["[48]"],"citation_sentence":"Psychological studies [48] have demonstrated that specific visual elements are often responsible for evoking emotions.","sentiment":"支持","sentiment_code":"support","evidence_phrase":"have demonstrated that specific visual elements","context":{"previous_sentence":"The L-AVC task requires editing inherently subjective emotions.","current_sentence":"Psychological studies [48] have demonstrated that specific visual elements are often responsible for evoking emotions.","next_sentence":"The paper therefore uses subjective emotions as a bridge between visual elements and the emotions they evoke."},"citation_metadata":{"reference_id":"REF48","citation_marker":"[48]","cited_authors":["Psychological study authors"],"work_name":"Study of visual elements and emotion elicitation","method_category":"Psychology of visual emotion"},"source_position":{"page_number":2,"source_section":"1 Introduction"},"confidence":0.97},{"citation_id":"CIT6","citation_markers":["[39]","[41]","[7]","[42]"],"citation_sentence":"Some studies [39, 41] attempt to leverage model editing [7, 42] to achieve efficient alignment on low-resource corpora.","sentiment":"支持","sentiment_code":"support","evidence_phrase":"achieve efficient alignment on low-resource corpora","context":{"previous_sentence":"Constructing large-scale aligned corpora for emotion conversion is difficult and expensive.","current_sentence":"Some studies [39, 41] attempt to leverage model editing [7, 42] to achieve efficient alignment on low-resource corpora.","next_sentence":"Inspired by these studies, the paper explores low-cost model editing for inter-emotion semantic alignment."},"citation_metadata":{"reference_id":"REF39_REF41_REF7_REF42","citation_marker":"[39, 41, 7, 42]","cited_authors":["Model-editing researchers"],"work_name":"Model editing for low-resource alignment","method_category":"Model editing"},"source_position":{"page_number":2,"source_section":"1 Introduction"},"confidence":0.96},{"citation_id":"CIT7","citation_markers":["[13]","[53]"],"citation_sentence":"The rise of diffusion models has ignited a surge in the field of image generation [13, 53].","sentiment":"支持","sentiment_code":"support","evidence_phrase":"has ignited a surge","context":{"previous_sentence":"The related-work section begins with visual customization.","current_sentence":"The rise of diffusion models has ignited a surge in the field of image generation [13, 53].","next_sentence":"Visual customization focuses on modifying desired elements while maintaining semantically unrelated content."},"citation_metadata":{"reference_id":"REF13_REF53","citation_marker":"[13, 53]","cited_authors":["Dhariwal and Nichol","Diffusion-model researchers"],"work_name":"Diffusion models for image generation","method_category":"Image generation"},"source_position":{"page_number":2,"source_section":"2 Related Work · Visual Customization"},"confidence":0.94},{"citation_id":"CIT8","citation_markers":["[50]","[46]"],"citation_sentence":"Qu et al. [50] utilize ChatGPT [46] to generate image layouts and employ a diffusion model conditioned on prompts and layouts to synthesize images.","sentiment":"中立","sentiment_code":"neutral","evidence_phrase":"utilize ChatGPT to generate image layouts","context":{"previous_sentence":"Several studies use the semantic understanding capability of LLMs to enhance text-conditioned generation.","current_sentence":"Qu et al. [50] utilize ChatGPT [46] to generate image layouts and employ a diffusion model conditioned on prompts and layouts to synthesize images.","next_sentence":"Other studies transfer knowledge from LLMs to diffusion models or jointly train MLLMs and editing models."},"citation_metadata":{"reference_id":"REF50_REF46","citation_marker":"[50, 46]","cited_authors":["Qu et al.","OpenAI"],"work_name":"ChatGPT-assisted image layout generation","method_category":"LLM-assisted diffusion"},"source_position":{"page_number":3,"source_section":"2 Related Work · LLM-assisted Diffusion Models"},"confidence":0.95}],"citation_sentiment_statistics":{"citation_sentence_count":8,"support_count":3,"neutral_count":3,"limitation_count":2,"sentiment_distribution":[{"sentiment":"支持","count":3,"percentage":37.5},{"sentiment":"中立","count":3,"percentage":37.5},{"sentiment":"有局限性","count":2,"percentage":25.0}],"average_confidence":0.9613}},"meta":{"fixed_demo_output":true,"fixed_demo_document":"Towards LLM-centric Affective Visual Customization via Efficient and Precise Emotion Manipulating","citation_metadata_source":"auto_parsed_from_reference_list","analysis_settings":{"language":"en","citation_extraction_mode":"auto_extract","context_window":1,"parse_reference_metadata":true,"return_context":true,"return_position":true,"return_citation_metadata":true,"manual_metadata_override":false,"minimum_confidence":0.75},"request_id":"req_citation_sentiment_epem_file_202607200001","elapsed_ms":1546}}},{"file_name":"引用情感识别_多模态方法引用片段.txt","size_bytes":509,"sha256":"c85f078d1f9ff8282420f7c763db81c1d129877793b2f789920873a21d597764","fnv1a32":"50e730b2","result":{"code":200,"message":"success","data":{"tool":"引用情感识别","input_type":"file","input":{"file_name":"引用情感识别_多模态方法引用片段.txt","file_format":"TXT","file_size":"509 B","document_parse_status":"success","citation_extraction_status":"success","reference_metadata_match_status":"success"},"document":{"title":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架","language":"zh","page_count":null,"analysis_scope":"full_text"},"citation_sentiment_results":[{"citation_id":"CIT1","citation_markers":["[34]"],"citation_sentence":"Wu[34]等人提出的MSM-BD方法结合了用户头像、用户属性和推文文本等多模态特征，利用专门设计的编码器对各模态信息进行提取，并通过跨模态残差交叉注意力模块实现多模态特征融合。","sentiment":"中立","sentiment_code":"neutral","evidence_phrase":"提出的MSM-BD方法结合了","context":{"previous_sentence":"当前基于多模态相关的研究主要从特征融合和分类结果集成两个方向展开。","current_sentence":"Wu[34]等人提出的MSM-BD方法结合了用户头像、用户属性和推文文本等多模态特征，利用专门设计的编码器对各模态信息进行提取，并通过跨模态残差交叉注意力模块实现多模态特征融合。","next_sentence":"Gong[35]等人提出BotSAI框架，通过整合用户多模态信息提升检测准确性与跨模态表示一致性。"},"citation_metadata":{"reference_id":"REF34","citation_marker":"[34]","cited_authors":["Wu"],"work_name":"MSM-BD","method_category":"多模态特征融合"},"source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.96},{"citation_id":"CIT2","citation_markers":["[36]"],"citation_sentence":"Feng[36]等人提出了一种名为SATAR的自监督学习方法，该方法融合了文本语义信息与用户行为特征，构建无监督表示学习框架。","sentiment":"中立","sentiment_code":"neutral","evidence_phrase":"提出了一种名为SATAR的自监督学习方法","context":{"previous_sentence":"Gong[35]等人提出BotSAI框架，通过整合用户多模态信息提升检测准确性与跨模态表示一致性。","current_sentence":"Feng[36]等人提出了一种名为SATAR的自监督学习方法，该方法融合了文本语义信息与用户行为特征，构建无监督表示学习框架。","next_sentence":"Guo等人[37]的BGSRD模型融合了BERT文本语义信息和GCN图结构关系。"},"citation_metadata":{"reference_id":"REF36","citation_marker":"[36]","cited_authors":["Feng"],"work_name":"SATAR","method_category":"自监督多模态表示学习"},"source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.94},{"citation_id":"CIT3","citation_markers":["[37]"],"citation_sentence":"Guo等人[37]的BGSRD模型融合了BERT的文本语义信息和GCN的图结构关系，联合训练后显著提高检测准确率。","sentiment":"支持","sentiment_code":"support","evidence_phrase":"联合训练后显著提高检测准确率","context":{"previous_sentence":"Feng[36]等人提出SATAR自监督学习方法，融合文本语义信息与用户行为特征。","current_sentence":"Guo等人[37]的BGSRD模型融合了BERT的文本语义信息和GCN的图结构关系，联合训练后显著提高检测准确率。","next_sentence":"Liu等人[38]的BotMoE方法利用社区感知的专家混合层整合元数据、文本和网络结构特征。"},"citation_metadata":{"reference_id":"REF37","citation_marker":"[37]","cited_authors":["Guo"],"work_name":"BGSRD","method_category":"BERT与GCN联合建模"},"source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.98},{"citation_id":"CIT4","citation_markers":["[34-43]"],"citation_sentence":"尽管现有的基于多模态数据的研究方法在提升社交媒体机器人检测性能方面表现出了显著优势，但不同模态之间在稀疏性和表达能力上的差异日益突出，导致融合过程中面临信息不均衡等问题。","sentiment":"有局限性","sentiment_code":"limitation","evidence_phrase":"但不同模态之间在稀疏性和表达能力上的差异日益突出","context":{"previous_sentence":"Carley等[43]研发BotBuster系统，使用混合专家架构分析账户信息的特定片段。","current_sentence":"尽管现有的基于多模态数据的研究方法在提升社交媒体机器人检测性能方面表现出了显著优势，但不同模态之间在稀疏性和表达能力上的差异日益突出，导致融合过程中面临信息不均衡等问题。","next_sentence":"同时，此类模型通常结构复杂、算力需求较大，难以高效适应大规模检测任务。"},"citation_metadata":{"reference_id":"REF34_REF43","citation_marker":"[34-43]","cited_authors":["多篇多模态机器人检测研究"],"work_name":"多模态检测方法集合","method_category":"多模态特征融合与结果集成"},"source_position":{"page_number":17,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.97}],"citation_sentiment_statistics":{"citation_sentence_count":4,"support_count":1,"neutral_count":2,"limitation_count":1,"sentiment_distribution":[{"sentiment":"支持","count":1,"percentage":25.0},{"sentiment":"中立","count":2,"percentage":50.0},{"sentiment":"有局限性","count":1,"percentage":25.0}],"average_confidence":0.9625}},"meta":{"fixed_demo_output":true,"analysis_settings":{"language":"zh","citation_extraction_mode":"auto_extract","context_window":1,"parse_reference_metadata":true,"return_context":true,"return_position":true,"return_citation_metadata":true,"minimum_confidence":0.75},"request_id":"req_citation_sentiment_multimodal_txt_202607200001","elapsed_ms":1628}}},{"file_name":"引用情感识别_图关系方法引用片段.txt","size_bytes":470,"sha256":"62b42cd984797bf4ec5f36c595215a4ad368feba28e08da7b4dd597c4081e817","fnv1a32":"659b1444","result":{"code":200,"message":"success","data":{"tool":"引用情感识别","input_type":"file","input":{"file_name":"引用情感识别_图关系方法引用片段.txt","file_format":"TXT","file_size":"470 B","document_parse_status":"success","citation_extraction_status":"success","reference_metadata_match_status":"success"},"document":{"title":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架","language":"zh","page_count":null,"analysis_scope":"full_text"},"citation_sentiment_results":[{"citation_id":"CIT5","citation_markers":["[44]"],"citation_sentence":"Lyu[44]等人提出DCGNN模型，通过构建包含时间关系和社交关系的图结构，有效地利用社交图关系数据捕捉用户的爆发行为和静态特征，从而提高了社交机器人检测的准确性。","sentiment":"支持","sentiment_code":"support","evidence_phrase":"从而提高了社交机器人检测的准确性","context":{"previous_sentence":"基于用户图关系的方法能够捕捉社交网络中的复杂交互关系和结构特征。","current_sentence":"Lyu[44]等人提出DCGNN模型，通过构建包含时间关系和社交关系的图结构，有效地利用社交图关系数据捕捉用户的爆发行为和静态特征，从而提高了社交机器人检测的准确性。","next_sentence":"Guyan等人提出PEGNN[45]模型，利用图神经网络捕捉用户之间的复杂交互关系。"},"citation_metadata":{"reference_id":"REF44","citation_marker":"[44]","cited_authors":["Lyu"],"work_name":"DCGNN","method_category":"社交图关系建模"},"source_position":{"page_number":17,"source_section":"1.2.2 基于社交图关系数据建模的社交媒体机器人检测方法"},"confidence":0.97},{"citation_id":"CIT6","citation_markers":["[44-53]"],"citation_sentence":"上述基于社交图关系数据建模的方法在捕捉用户间复杂交互模式方面具有优势，但是社交图关系型数据的获取通常依赖平台API权限，受到访问限制和隐私保护政策制约，在实际应用中往往难以获得完整、高质量的社交网络结构。","sentiment":"有局限性","sentiment_code":"limitation","evidence_phrase":"但是社交图关系型数据的获取通常依赖平台API权限","context":{"previous_sentence":"Yang和Wu[53]等人提出seBot框架，通过结合社区结构和对抗性行为信息提高机器人检测性能。","current_sentence":"上述基于社交图关系数据建模的方法在捕捉用户间复杂交互模式方面具有优势，但是社交图关系型数据的获取通常依赖平台API权限，受到访问限制和隐私保护政策制约，在实际应用中往往难以获得完整、高质量的社交网络结构。","next_sentence":"这导致依赖图结构的检测模型在实际部署中难以获取充足的关键输入数据。"},"citation_metadata":{"reference_id":"REF44_REF53","citation_marker":"[44-53]","cited_authors":["多篇图关系建模研究"],"work_name":"社交图关系检测方法集合","method_category":"图神经网络与异构图建模"},"source_position":{"page_number":18,"source_section":"1.2.2 基于社交图关系数据建模的社交媒体机器人检测方法"},"confidence":0.98}],"citation_sentiment_statistics":{"citation_sentence_count":2,"support_count":1,"neutral_count":0,"limitation_count":1,"sentiment_distribution":[{"sentiment":"支持","count":1,"percentage":50.0},{"sentiment":"中立","count":0,"percentage":0.0},{"sentiment":"有局限性","count":1,"percentage":50.0}],"average_confidence":0.975}},"meta":{"fixed_demo_output":true,"analysis_settings":{"language":"zh","citation_extraction_mode":"auto_extract","context_window":1,"parse_reference_metadata":true,"return_context":true,"return_position":true,"return_citation_metadata":true,"minimum_confidence":0.75},"request_id":"req_citation_sentiment_graph_txt_202607200001","elapsed_ms":1628}}}],"onlineDemoDocument":{"title":"Towards LLM-centric Affective Visual Customization via Efficient and Precise Emotion Manipulating","file_name":"Towards_LLM-centric_Affective_Visual_Customization_EPEM.pdf"},"apiSampleFileName":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架.pdf","apiSampleFileSize":"3.17 MB","apiBatchSampleFileNames":["基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架.pdf","引用情感识别_多模态方法引用片段.txt","引用情感识别_图关系方法引用片段.txt"],"apiPayload":{"analysis_settings":{"language":"zh","citation_extraction_mode":"auto_extract","context_window":1,"parse_reference_metadata":true,"return_context":true,"return_position":true,"return_citation_metadata":true,"minimum_confidence":0.75},"citation_metadata":[{"reference_id":"REF34","citation_marker":"[34]","cited_authors":["Wu"],"work_name":"MSM-BD","method_category":"多模态特征融合"},{"reference_id":"REF36","citation_marker":"[36]","cited_authors":["Feng"],"work_name":"SATAR","method_category":"自监督多模态表示学习"},{"reference_id":"REF37","citation_marker":"[37]","cited_authors":["Guo"],"work_name":"BGSRD","method_category":"BERT与GCN联合建模"},{"reference_id":"REF43","citation_marker":"[43]","cited_authors":["Carley"],"work_name":"BotBuster","method_category":"混合专家集成检测"},{"reference_id":"REF44","citation_marker":"[44]","cited_authors":["Lyu"],"work_name":"DCGNN","method_category":"社交图关系建模"},{"reference_id":"REF44_REF53","citation_marker":"[44-53]","cited_authors":["多篇图关系建模研究"],"work_name":"社交图关系检测方法集合","method_category":"图神经网络与异构图建模"}]},"apiFileResult":{"code":200,"message":"success","data":{"tool":"引用情感识别","input_type":"file","input":{"file_name":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架.pdf","file_format":"PDF","file_size":"3.17 MB","document_parse_status":"success","citation_extraction_status":"success","reference_metadata_match_status":"success"},"document":{"title":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架","language":"zh","page_count":83,"analysis_scope":"full_text"},"citation_sentiment_results":[{"citation_id":"CIT1","citation_markers":["[34]"],"citation_sentence":"Wu[34]等人提出的MSM-BD方法结合了用户头像、用户属性和推文文本等多模态特征，利用专门设计的编码器对各模态信息进行提取，并通过跨模态残差交叉注意力模块实现多模态特征融合。","sentiment":"中立","sentiment_code":"neutral","evidence_phrase":"提出的MSM-BD方法结合了","context":{"previous_sentence":"当前基于多模态相关的研究主要从特征融合和分类结果集成两个方向展开。","current_sentence":"Wu[34]等人提出的MSM-BD方法结合了用户头像、用户属性和推文文本等多模态特征，利用专门设计的编码器对各模态信息进行提取，并通过跨模态残差交叉注意力模块实现多模态特征融合。","next_sentence":"Gong[35]等人提出BotSAI框架，通过整合用户多模态信息提升检测准确性与跨模态表示一致性。"},"citation_metadata":{"reference_id":"REF34","citation_marker":"[34]","cited_authors":["Wu"],"work_name":"MSM-BD","method_category":"多模态特征融合"},"source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.96},{"citation_id":"CIT2","citation_markers":["[36]"],"citation_sentence":"Feng[36]等人提出了一种名为SATAR的自监督学习方法，该方法融合了文本语义信息与用户行为特征，构建无监督表示学习框架。","sentiment":"中立","sentiment_code":"neutral","evidence_phrase":"提出了一种名为SATAR的自监督学习方法","context":{"previous_sentence":"Gong[35]等人提出BotSAI框架，通过整合用户多模态信息提升检测准确性与跨模态表示一致性。","current_sentence":"Feng[36]等人提出了一种名为SATAR的自监督学习方法，该方法融合了文本语义信息与用户行为特征，构建无监督表示学习框架。","next_sentence":"Guo等人[37]的BGSRD模型融合了BERT文本语义信息和GCN图结构关系。"},"citation_metadata":{"reference_id":"REF36","citation_marker":"[36]","cited_authors":["Feng"],"work_name":"SATAR","method_category":"自监督多模态表示学习"},"source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.94},{"citation_id":"CIT3","citation_markers":["[37]"],"citation_sentence":"Guo等人[37]的BGSRD模型融合了BERT的文本语义信息和GCN的图结构关系，联合训练后显著提高检测准确率。","sentiment":"支持","sentiment_code":"support","evidence_phrase":"联合训练后显著提高检测准确率","context":{"previous_sentence":"Feng[36]等人提出SATAR自监督学习方法，融合文本语义信息与用户行为特征。","current_sentence":"Guo等人[37]的BGSRD模型融合了BERT的文本语义信息和GCN的图结构关系，联合训练后显著提高检测准确率。","next_sentence":"Liu等人[38]的BotMoE方法利用社区感知的专家混合层整合元数据、文本和网络结构特征。"},"citation_metadata":{"reference_id":"REF37","citation_marker":"[37]","cited_authors":["Guo"],"work_name":"BGSRD","method_category":"BERT与GCN联合建模"},"source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.98},{"citation_id":"CIT4","citation_markers":["[34-43]"],"citation_sentence":"尽管现有的基于多模态数据的研究方法在提升社交媒体机器人检测性能方面表现出了显著优势，但不同模态之间在稀疏性和表达能力上的差异日益突出，导致融合过程中面临信息不均衡等问题。","sentiment":"有局限性","sentiment_code":"limitation","evidence_phrase":"但不同模态之间在稀疏性和表达能力上的差异日益突出","context":{"previous_sentence":"Carley等[43]研发BotBuster系统，使用混合专家架构分析账户信息的特定片段。","current_sentence":"尽管现有的基于多模态数据的研究方法在提升社交媒体机器人检测性能方面表现出了显著优势，但不同模态之间在稀疏性和表达能力上的差异日益突出，导致融合过程中面临信息不均衡等问题。","next_sentence":"同时，此类模型通常结构复杂、算力需求较大，难以高效适应大规模检测任务。"},"citation_metadata":{"reference_id":"REF34_REF43","citation_marker":"[34-43]","cited_authors":["多篇多模态机器人检测研究"],"work_name":"多模态检测方法集合","method_category":"多模态特征融合与结果集成"},"source_position":{"page_number":17,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.97},{"citation_id":"CIT5","citation_markers":["[44]"],"citation_sentence":"Lyu[44]等人提出DCGNN模型，通过构建包含时间关系和社交关系的图结构，有效地利用社交图关系数据捕捉用户的爆发行为和静态特征，从而提高了社交机器人检测的准确性。","sentiment":"支持","sentiment_code":"support","evidence_phrase":"从而提高了社交机器人检测的准确性","context":{"previous_sentence":"基于用户图关系的方法能够捕捉社交网络中的复杂交互关系和结构特征。","current_sentence":"Lyu[44]等人提出DCGNN模型，通过构建包含时间关系和社交关系的图结构，有效地利用社交图关系数据捕捉用户的爆发行为和静态特征，从而提高了社交机器人检测的准确性。","next_sentence":"Guyan等人提出PEGNN[45]模型，利用图神经网络捕捉用户之间的复杂交互关系。"},"citation_metadata":{"reference_id":"REF44","citation_marker":"[44]","cited_authors":["Lyu"],"work_name":"DCGNN","method_category":"社交图关系建模"},"source_position":{"page_number":17,"source_section":"1.2.2 基于社交图关系数据建模的社交媒体机器人检测方法"},"confidence":0.97},{"citation_id":"CIT6","citation_markers":["[44-53]"],"citation_sentence":"上述基于社交图关系数据建模的方法在捕捉用户间复杂交互模式方面具有优势，但是社交图关系型数据的获取通常依赖平台API权限，受到访问限制和隐私保护政策制约，在实际应用中往往难以获得完整、高质量的社交网络结构。","sentiment":"有局限性","sentiment_code":"limitation","evidence_phrase":"但是社交图关系型数据的获取通常依赖平台API权限","context":{"previous_sentence":"Yang和Wu[53]等人提出seBot框架，通过结合社区结构和对抗性行为信息提高机器人检测性能。","current_sentence":"上述基于社交图关系数据建模的方法在捕捉用户间复杂交互模式方面具有优势，但是社交图关系型数据的获取通常依赖平台API权限，受到访问限制和隐私保护政策制约，在实际应用中往往难以获得完整、高质量的社交网络结构。","next_sentence":"这导致依赖图结构的检测模型在实际部署中难以获取充足的关键输入数据。"},"citation_metadata":{"reference_id":"REF44_REF53","citation_marker":"[44-53]","cited_authors":["多篇图关系建模研究"],"work_name":"社交图关系检测方法集合","method_category":"图神经网络与异构图建模"},"source_position":{"page_number":18,"source_section":"1.2.2 基于社交图关系数据建模的社交媒体机器人检测方法"},"confidence":0.98}],"citation_sentiment_statistics":{"citation_sentence_count":6,"support_count":2,"neutral_count":2,"limitation_count":2,"sentiment_distribution":[{"sentiment":"支持","count":2,"percentage":33.33},{"sentiment":"中立","count":2,"percentage":33.33},{"sentiment":"有局限性","count":2,"percentage":33.33}],"average_confidence":0.9667}},"meta":{"fixed_demo_output":true,"analysis_settings":{"language":"zh","citation_extraction_mode":"auto_extract","context_window":1,"parse_reference_metadata":true,"return_context":true,"return_position":true,"return_citation_metadata":true,"minimum_confidence":0.75},"request_id":"req_citation_sentiment_file_202607200001","elapsed_ms":1628}},"apiBatchFileResult":{"code":200,"message":"batch_completed","data":{"batch_id":"batch_citation_sentiment_files_202607200001","input_type":"files","total":3,"success_count":3,"failed_count":0,"results":[{"index":1,"file_name":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架.pdf","status":"success","code":200,"result":{"tool":"引用情感识别","input_type":"file","input":{"file_name":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架.pdf","file_format":"PDF","file_size":"3.17 MB","document_parse_status":"success","citation_extraction_status":"success","reference_metadata_match_status":"success"},"document":{"title":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架","language":"zh","page_count":83,"analysis_scope":"full_text"},"citation_sentiment_results":[{"citation_id":"CIT1","citation_markers":["[34]"],"citation_sentence":"Wu[34]等人提出的MSM-BD方法结合了用户头像、用户属性和推文文本等多模态特征，利用专门设计的编码器对各模态信息进行提取，并通过跨模态残差交叉注意力模块实现多模态特征融合。","sentiment":"中立","sentiment_code":"neutral","evidence_phrase":"提出的MSM-BD方法结合了","context":{"previous_sentence":"当前基于多模态相关的研究主要从特征融合和分类结果集成两个方向展开。","current_sentence":"Wu[34]等人提出的MSM-BD方法结合了用户头像、用户属性和推文文本等多模态特征，利用专门设计的编码器对各模态信息进行提取，并通过跨模态残差交叉注意力模块实现多模态特征融合。","next_sentence":"Gong[35]等人提出BotSAI框架，通过整合用户多模态信息提升检测准确性与跨模态表示一致性。"},"citation_metadata":{"reference_id":"REF34","citation_marker":"[34]","cited_authors":["Wu"],"work_name":"MSM-BD","method_category":"多模态特征融合"},"source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.96},{"citation_id":"CIT2","citation_markers":["[36]"],"citation_sentence":"Feng[36]等人提出了一种名为SATAR的自监督学习方法，该方法融合了文本语义信息与用户行为特征，构建无监督表示学习框架。","sentiment":"中立","sentiment_code":"neutral","evidence_phrase":"提出了一种名为SATAR的自监督学习方法","context":{"previous_sentence":"Gong[35]等人提出BotSAI框架，通过整合用户多模态信息提升检测准确性与跨模态表示一致性。","current_sentence":"Feng[36]等人提出了一种名为SATAR的自监督学习方法，该方法融合了文本语义信息与用户行为特征，构建无监督表示学习框架。","next_sentence":"Guo等人[37]的BGSRD模型融合了BERT文本语义信息和GCN图结构关系。"},"citation_metadata":{"reference_id":"REF36","citation_marker":"[36]","cited_authors":["Feng"],"work_name":"SATAR","method_category":"自监督多模态表示学习"},"source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.94},{"citation_id":"CIT3","citation_markers":["[37]"],"citation_sentence":"Guo等人[37]的BGSRD模型融合了BERT的文本语义信息和GCN的图结构关系，联合训练后显著提高检测准确率。","sentiment":"支持","sentiment_code":"support","evidence_phrase":"联合训练后显著提高检测准确率","context":{"previous_sentence":"Feng[36]等人提出SATAR自监督学习方法，融合文本语义信息与用户行为特征。","current_sentence":"Guo等人[37]的BGSRD模型融合了BERT的文本语义信息和GCN的图结构关系，联合训练后显著提高检测准确率。","next_sentence":"Liu等人[38]的BotMoE方法利用社区感知的专家混合层整合元数据、文本和网络结构特征。"},"citation_metadata":{"reference_id":"REF37","citation_marker":"[37]","cited_authors":["Guo"],"work_name":"BGSRD","method_category":"BERT与GCN联合建模"},"source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.98},{"citation_id":"CIT4","citation_markers":["[34-43]"],"citation_sentence":"尽管现有的基于多模态数据的研究方法在提升社交媒体机器人检测性能方面表现出了显著优势，但不同模态之间在稀疏性和表达能力上的差异日益突出，导致融合过程中面临信息不均衡等问题。","sentiment":"有局限性","sentiment_code":"limitation","evidence_phrase":"但不同模态之间在稀疏性和表达能力上的差异日益突出","context":{"previous_sentence":"Carley等[43]研发BotBuster系统，使用混合专家架构分析账户信息的特定片段。","current_sentence":"尽管现有的基于多模态数据的研究方法在提升社交媒体机器人检测性能方面表现出了显著优势，但不同模态之间在稀疏性和表达能力上的差异日益突出，导致融合过程中面临信息不均衡等问题。","next_sentence":"同时，此类模型通常结构复杂、算力需求较大，难以高效适应大规模检测任务。"},"citation_metadata":{"reference_id":"REF34_REF43","citation_marker":"[34-43]","cited_authors":["多篇多模态机器人检测研究"],"work_name":"多模态检测方法集合","method_category":"多模态特征融合与结果集成"},"source_position":{"page_number":17,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.97},{"citation_id":"CIT5","citation_markers":["[44]"],"citation_sentence":"Lyu[44]等人提出DCGNN模型，通过构建包含时间关系和社交关系的图结构，有效地利用社交图关系数据捕捉用户的爆发行为和静态特征，从而提高了社交机器人检测的准确性。","sentiment":"支持","sentiment_code":"support","evidence_phrase":"从而提高了社交机器人检测的准确性","context":{"previous_sentence":"基于用户图关系的方法能够捕捉社交网络中的复杂交互关系和结构特征。","current_sentence":"Lyu[44]等人提出DCGNN模型，通过构建包含时间关系和社交关系的图结构，有效地利用社交图关系数据捕捉用户的爆发行为和静态特征，从而提高了社交机器人检测的准确性。","next_sentence":"Guyan等人提出PEGNN[45]模型，利用图神经网络捕捉用户之间的复杂交互关系。"},"citation_metadata":{"reference_id":"REF44","citation_marker":"[44]","cited_authors":["Lyu"],"work_name":"DCGNN","method_category":"社交图关系建模"},"source_position":{"page_number":17,"source_section":"1.2.2 基于社交图关系数据建模的社交媒体机器人检测方法"},"confidence":0.97},{"citation_id":"CIT6","citation_markers":["[44-53]"],"citation_sentence":"上述基于社交图关系数据建模的方法在捕捉用户间复杂交互模式方面具有优势，但是社交图关系型数据的获取通常依赖平台API权限，受到访问限制和隐私保护政策制约，在实际应用中往往难以获得完整、高质量的社交网络结构。","sentiment":"有局限性","sentiment_code":"limitation","evidence_phrase":"但是社交图关系型数据的获取通常依赖平台API权限","context":{"previous_sentence":"Yang和Wu[53]等人提出seBot框架，通过结合社区结构和对抗性行为信息提高机器人检测性能。","current_sentence":"上述基于社交图关系数据建模的方法在捕捉用户间复杂交互模式方面具有优势，但是社交图关系型数据的获取通常依赖平台API权限，受到访问限制和隐私保护政策制约，在实际应用中往往难以获得完整、高质量的社交网络结构。","next_sentence":"这导致依赖图结构的检测模型在实际部署中难以获取充足的关键输入数据。"},"citation_metadata":{"reference_id":"REF44_REF53","citation_marker":"[44-53]","cited_authors":["多篇图关系建模研究"],"work_name":"社交图关系检测方法集合","method_category":"图神经网络与异构图建模"},"source_position":{"page_number":18,"source_section":"1.2.2 基于社交图关系数据建模的社交媒体机器人检测方法"},"confidence":0.98}],"citation_sentiment_statistics":{"citation_sentence_count":6,"support_count":2,"neutral_count":2,"limitation_count":2,"sentiment_distribution":[{"sentiment":"支持","count":2,"percentage":33.33},{"sentiment":"中立","count":2,"percentage":33.33},{"sentiment":"有局限性","count":2,"percentage":33.33}],"average_confidence":0.9667}}},{"index":2,"file_name":"引用情感识别_多模态方法引用片段.txt","status":"success","code":200,"result":{"tool":"引用情感识别","input_type":"file","input":{"file_name":"引用情感识别_多模态方法引用片段.txt","file_format":"TXT","file_size":"509 B","document_parse_status":"success","citation_extraction_status":"success","reference_metadata_match_status":"success"},"document":{"title":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架","language":"zh","page_count":null,"analysis_scope":"full_text"},"citation_sentiment_results":[{"citation_id":"CIT1","citation_markers":["[34]"],"citation_sentence":"Wu[34]等人提出的MSM-BD方法结合了用户头像、用户属性和推文文本等多模态特征，利用专门设计的编码器对各模态信息进行提取，并通过跨模态残差交叉注意力模块实现多模态特征融合。","sentiment":"中立","sentiment_code":"neutral","evidence_phrase":"提出的MSM-BD方法结合了","context":{"previous_sentence":"当前基于多模态相关的研究主要从特征融合和分类结果集成两个方向展开。","current_sentence":"Wu[34]等人提出的MSM-BD方法结合了用户头像、用户属性和推文文本等多模态特征，利用专门设计的编码器对各模态信息进行提取，并通过跨模态残差交叉注意力模块实现多模态特征融合。","next_sentence":"Gong[35]等人提出BotSAI框架，通过整合用户多模态信息提升检测准确性与跨模态表示一致性。"},"citation_metadata":{"reference_id":"REF34","citation_marker":"[34]","cited_authors":["Wu"],"work_name":"MSM-BD","method_category":"多模态特征融合"},"source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.96},{"citation_id":"CIT2","citation_markers":["[36]"],"citation_sentence":"Feng[36]等人提出了一种名为SATAR的自监督学习方法，该方法融合了文本语义信息与用户行为特征，构建无监督表示学习框架。","sentiment":"中立","sentiment_code":"neutral","evidence_phrase":"提出了一种名为SATAR的自监督学习方法","context":{"previous_sentence":"Gong[35]等人提出BotSAI框架，通过整合用户多模态信息提升检测准确性与跨模态表示一致性。","current_sentence":"Feng[36]等人提出了一种名为SATAR的自监督学习方法，该方法融合了文本语义信息与用户行为特征，构建无监督表示学习框架。","next_sentence":"Guo等人[37]的BGSRD模型融合了BERT文本语义信息和GCN图结构关系。"},"citation_metadata":{"reference_id":"REF36","citation_marker":"[36]","cited_authors":["Feng"],"work_name":"SATAR","method_category":"自监督多模态表示学习"},"source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.94},{"citation_id":"CIT3","citation_markers":["[37]"],"citation_sentence":"Guo等人[37]的BGSRD模型融合了BERT的文本语义信息和GCN的图结构关系，联合训练后显著提高检测准确率。","sentiment":"支持","sentiment_code":"support","evidence_phrase":"联合训练后显著提高检测准确率","context":{"previous_sentence":"Feng[36]等人提出SATAR自监督学习方法，融合文本语义信息与用户行为特征。","current_sentence":"Guo等人[37]的BGSRD模型融合了BERT的文本语义信息和GCN的图结构关系，联合训练后显著提高检测准确率。","next_sentence":"Liu等人[38]的BotMoE方法利用社区感知的专家混合层整合元数据、文本和网络结构特征。"},"citation_metadata":{"reference_id":"REF37","citation_marker":"[37]","cited_authors":["Guo"],"work_name":"BGSRD","method_category":"BERT与GCN联合建模"},"source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.98},{"citation_id":"CIT4","citation_markers":["[34-43]"],"citation_sentence":"尽管现有的基于多模态数据的研究方法在提升社交媒体机器人检测性能方面表现出了显著优势，但不同模态之间在稀疏性和表达能力上的差异日益突出，导致融合过程中面临信息不均衡等问题。","sentiment":"有局限性","sentiment_code":"limitation","evidence_phrase":"但不同模态之间在稀疏性和表达能力上的差异日益突出","context":{"previous_sentence":"Carley等[43]研发BotBuster系统，使用混合专家架构分析账户信息的特定片段。","current_sentence":"尽管现有的基于多模态数据的研究方法在提升社交媒体机器人检测性能方面表现出了显著优势，但不同模态之间在稀疏性和表达能力上的差异日益突出，导致融合过程中面临信息不均衡等问题。","next_sentence":"同时，此类模型通常结构复杂、算力需求较大，难以高效适应大规模检测任务。"},"citation_metadata":{"reference_id":"REF34_REF43","citation_marker":"[34-43]","cited_authors":["多篇多模态机器人检测研究"],"work_name":"多模态检测方法集合","method_category":"多模态特征融合与结果集成"},"source_position":{"page_number":17,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.97}],"citation_sentiment_statistics":{"citation_sentence_count":4,"support_count":1,"neutral_count":2,"limitation_count":1,"sentiment_distribution":[{"sentiment":"支持","count":1,"percentage":25.0},{"sentiment":"中立","count":2,"percentage":50.0},{"sentiment":"有局限性","count":1,"percentage":25.0}],"average_confidence":0.9625}}},{"index":3,"file_name":"引用情感识别_图关系方法引用片段.txt","status":"success","code":200,"result":{"tool":"引用情感识别","input_type":"file","input":{"file_name":"引用情感识别_图关系方法引用片段.txt","file_format":"TXT","file_size":"470 B","document_parse_status":"success","citation_extraction_status":"success","reference_metadata_match_status":"success"},"document":{"title":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架","language":"zh","page_count":null,"analysis_scope":"full_text"},"citation_sentiment_results":[{"citation_id":"CIT5","citation_markers":["[44]"],"citation_sentence":"Lyu[44]等人提出DCGNN模型，通过构建包含时间关系和社交关系的图结构，有效地利用社交图关系数据捕捉用户的爆发行为和静态特征，从而提高了社交机器人检测的准确性。","sentiment":"支持","sentiment_code":"support","evidence_phrase":"从而提高了社交机器人检测的准确性","context":{"previous_sentence":"基于用户图关系的方法能够捕捉社交网络中的复杂交互关系和结构特征。","current_sentence":"Lyu[44]等人提出DCGNN模型，通过构建包含时间关系和社交关系的图结构，有效地利用社交图关系数据捕捉用户的爆发行为和静态特征，从而提高了社交机器人检测的准确性。","next_sentence":"Guyan等人提出PEGNN[45]模型，利用图神经网络捕捉用户之间的复杂交互关系。"},"citation_metadata":{"reference_id":"REF44","citation_marker":"[44]","cited_authors":["Lyu"],"work_name":"DCGNN","method_category":"社交图关系建模"},"source_position":{"page_number":17,"source_section":"1.2.2 基于社交图关系数据建模的社交媒体机器人检测方法"},"confidence":0.97},{"citation_id":"CIT6","citation_markers":["[44-53]"],"citation_sentence":"上述基于社交图关系数据建模的方法在捕捉用户间复杂交互模式方面具有优势，但是社交图关系型数据的获取通常依赖平台API权限，受到访问限制和隐私保护政策制约，在实际应用中往往难以获得完整、高质量的社交网络结构。","sentiment":"有局限性","sentiment_code":"limitation","evidence_phrase":"但是社交图关系型数据的获取通常依赖平台API权限","context":{"previous_sentence":"Yang和Wu[53]等人提出seBot框架，通过结合社区结构和对抗性行为信息提高机器人检测性能。","current_sentence":"上述基于社交图关系数据建模的方法在捕捉用户间复杂交互模式方面具有优势，但是社交图关系型数据的获取通常依赖平台API权限，受到访问限制和隐私保护政策制约，在实际应用中往往难以获得完整、高质量的社交网络结构。","next_sentence":"这导致依赖图结构的检测模型在实际部署中难以获取充足的关键输入数据。"},"citation_metadata":{"reference_id":"REF44_REF53","citation_marker":"[44-53]","cited_authors":["多篇图关系建模研究"],"work_name":"社交图关系检测方法集合","method_category":"图神经网络与异构图建模"},"source_position":{"page_number":18,"source_section":"1.2.2 基于社交图关系数据建模的社交媒体机器人检测方法"},"confidence":0.98}],"citation_sentiment_statistics":{"citation_sentence_count":2,"support_count":1,"neutral_count":0,"limitation_count":1,"sentiment_distribution":[{"sentiment":"支持","count":1,"percentage":50.0},{"sentiment":"中立","count":0,"percentage":0.0},{"sentiment":"有局限性","count":1,"percentage":50.0}],"average_confidence":0.975}}}]},"meta":{"analysis_settings":{"language":"zh","citation_extraction_mode":"auto_extract","context_window":1,"parse_reference_metadata":true,"return_context":true,"return_position":true,"return_citation_metadata":true,"minimum_confidence":0.75},"max_concurrency":3,"continue_on_error":true,"elapsed_ms":3486}},"apiExampleDocument":{"title":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架","file_name":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架.pdf"}},
      "citation-intent": {"group":"引用句识别工具","title":"引用意图识别","documentType":"citation-intent","languageCode":"zh","languageName":"中文","description":"从科技文献全文文件中自动抽取引用句及其前后文，匹配引文元数据，并结合预处理后的训练集判断作者引用他人研究的动机。引用意图分为用于背景介绍、用于引入研究方法和用于结果比较三类。","features":"单文件识别、批量文件识别、全文引用句抽取、上下文提取、引文元数据匹配、预处理训练集校验、三类引用意图识别、判定证据提取、置信度评分、统计摘要","scenarios":"文献综述结构分析、方法传播研究、结果对比关系发现、引文网络分析、批量科研文献分析","endpoint":"/api/v1/citation/intent/file","fileEndpoint":"/api/v1/citation/intent/file","batchFileEndpoint":"/api/v1/citation/intent/files","inputModes":["file","batch"],"modeLabels":{"file":"单文件","batch":"批量文件"},"supportsFileUpload":true,"supportsBatchUpload":true,"acceptedFiles":[".pdf",".docx",".txt"],"maxFileSizeMB":50,"maxBatchFiles":20,"documentTarget":"科技文献全文中的引用句、上下文和引文元数据","fileProcessingHint":"上传一个PDF、DOCX或TXT文件，系统自动提取引用句和上下文并识别引用意图","batchProcessingHint":"逐文件抽取引用句、匹配引文元数据，并返回三类引用意图结果及统计摘要","params":[["file","file","conditional","单文件模式必填：PDF、DOCX或TXT科技文献全文"],["files","file[]","conditional","批量文件模式必填：最多20个PDF、DOCX或TXT文件"],["preprocessed_training_set","object[]","required","已完成清洗、标签统一和类别平衡的引用意图训练样本"],["analysis_settings","object","required","引用句抽取、上下文窗口、元数据匹配和结果返回要求"],["citation_extraction_mode","string","optional","auto_extract，默认从全文自动抽取引用句"],["context_window","integer","optional","引用句前后文窗口，默认1句"],["parse_reference_metadata","boolean","optional","是否从参考文献列表自动解析引文元数据，默认true"],["minimum_confidence","number","optional","最低置信度，默认0.75"],["return_context","boolean","optional","是否返回上下文片段，默认true"],["return_position","boolean","optional","是否返回来源章节和页码，默认true"],["return_citation_metadata","boolean","optional","是否返回引文元数据，默认true"],["return_training_evidence","boolean","optional","是否返回匹配训练样本，默认true"],["max_concurrency","integer","optional","批量任务并发数，默认3"],["continue_on_error","boolean","optional","单文件失败时是否继续处理，默认true"]],"payload":{"analysis_settings":{"language":"zh","citation_extraction_mode":"auto_extract","context_window":1,"parse_reference_metadata":true,"minimum_confidence":0.75,"return_context":true,"return_position":true,"return_citation_metadata":true,"return_training_evidence":true},"preprocessed_training_set":[{"sample_id":"TRAIN_BG_001","citation_sentence":"现有研究已广泛使用多模态特征融合开展社交媒体机器人检测[34-37]。","context":"该类方法通常联合利用用户文本、元数据和社交关系信息。","intent_label":"用于背景介绍"},{"sample_id":"TRAIN_BG_002","citation_sentence":"图神经网络已被用于建模社交平台中的用户交互关系[44-53]。","context":"相关研究为基于关系结构的机器人检测提供了重要基础。","intent_label":"用于背景介绍"},{"sample_id":"TRAIN_METHOD_001","citation_sentence":"本文采用Guo等人[37]提出的图卷积建模策略构建用户关系表示。","context":"该策略用于增强模型对用户结构依赖关系的建模能力。","intent_label":"用于引入研究方法"},{"sample_id":"TRAIN_METHOD_002","citation_sentence":"为提取文本语义特征，我们引入Feng等人[36]使用的预训练语言模型编码方法。","context":"编码结果随后与用户元数据特征进行联合融合。","intent_label":"用于引入研究方法"},{"sample_id":"TRAIN_COMPARE_001","citation_sentence":"与Lyu等人[44]提出的DCGNN相比，本文模型的F1值提高了2.8%。","context":"实验采用相同的数据划分和评价指标。","intent_label":"用于结果比较"},{"sample_id":"TRAIN_COMPARE_002","citation_sentence":"本文方法在准确率和召回率上均优于BotBuster[43]。","context":"对比结果表明，多视图集成能够提升检测稳定性。","intent_label":"用于结果比较"}]},"sampleFileName":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架.pdf","sampleFileSize":"3.17 MB","batchSampleFileNames":["基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架.pdf","引用意图识别_相关工作背景介绍.txt","引用意图识别_方法引入与结果比较.txt"],"demoFileResult":{"code":200,"message":"success","data":{"tool":"引用意图识别","input_type":"file","input":{"file_name":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架.pdf","file_format":"PDF","file_size":"3.17 MB","document_parse_status":"success","citation_extraction_status":"success","context_extraction_status":"success","reference_metadata_match_status":"success","training_set_validation_status":"success"},"document":{"title":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架","language":"zh","page_count":83,"analysis_scope":"full_text"},"citation_intent_results":[{"citation_id":"CIT_INT_001","citation_markers":["[34]"],"citation_sentence":"Wu[34]等人提出的MSM-BD方法结合用户头像、用户属性和推文文本等多模态特征，并通过跨模态残差交叉注意力模块实现特征融合。","context":{"previous_sentence":"当前基于多模态数据的研究主要从特征融合和分类结果集成两个方向展开。","current_sentence":"Wu[34]等人提出的MSM-BD方法结合用户头像、用户属性和推文文本等多模态特征，并通过跨模态残差交叉注意力模块实现特征融合。","next_sentence":"随后，多项研究继续从多模态编码和融合机制方面改进机器人检测模型。"},"citation_metadata":{"reference_id":"REF34","citation_marker":"[34]","authors":["Wu et al."],"work_name":"MSM-BD","year":2022},"intent":"用于背景介绍","intent_code":"background_introduction","evidence_phrase":"提出的MSM-BD方法结合","source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.96,"matched_training_examples":[{"sample_id":"TRAIN_BG_001","intent_label":"用于背景介绍","similarity":0.94}]},{"citation_id":"CIT_INT_002","citation_markers":["[36]"],"citation_sentence":"Feng[36]等人提出SATAR自监督学习方法，该方法融合文本语义信息与用户行为特征，构建无监督表示学习框架。","context":{"previous_sentence":"BotSAI框架通过整合用户多模态信息提升检测准确性。","current_sentence":"Feng[36]等人提出SATAR自监督学习方法，该方法融合文本语义信息与用户行为特征，构建无监督表示学习框架。","next_sentence":"Guo等人[37]进一步融合BERT语义信息和GCN图结构关系。"},"citation_metadata":{"reference_id":"REF36","citation_marker":"[36]","authors":["Feng et al."],"work_name":"SATAR","year":2022},"intent":"用于背景介绍","intent_code":"background_introduction","evidence_phrase":"提出SATAR自监督学习方法","source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.95,"matched_training_examples":[{"sample_id":"TRAIN_BG_001","intent_label":"用于背景介绍","similarity":0.91}]},{"citation_id":"CIT_INT_003","citation_markers":["[55]"],"citation_sentence":"本文采用Hinton等人[55]提出的知识蒸馏思想，将多个教师模型输出的软标签迁移至轻量学生模型。","context":{"previous_sentence":"为降低复杂多视图模型的计算开销，需要压缩模型参数并保留教师模型的判别知识。","current_sentence":"本文采用Hinton等人[55]提出的知识蒸馏思想，将多个教师模型输出的软标签迁移至轻量学生模型。","next_sentence":"在此基础上，进一步设计多教师权重分配和蒸馏损失函数。"},"citation_metadata":{"reference_id":"REF55","citation_marker":"[55]","authors":["Hinton et al."],"work_name":"Knowledge Distillation","year":2015},"intent":"用于引入研究方法","intent_code":"method_introduction","evidence_phrase":"本文采用Hinton等人[55]提出的知识蒸馏思想","source_position":{"page_number":38,"source_section":"3 多教师知识蒸馏模型"},"confidence":0.98,"matched_training_examples":[{"sample_id":"TRAIN_METHOD_001","intent_label":"用于引入研究方法","similarity":0.95},{"sample_id":"TRAIN_METHOD_002","intent_label":"用于引入研究方法","similarity":0.88}]},{"citation_id":"CIT_INT_004","citation_markers":["[37]"],"citation_sentence":"在文本语义编码阶段，本文引入Guo等人[37]使用的BERT表示方式提取用户推文特征。","context":{"previous_sentence":"用户文本包含能够区分真实用户和机器人的语义线索。","current_sentence":"在文本语义编码阶段，本文引入Guo等人[37]使用的BERT表示方式提取用户推文特征。","next_sentence":"随后将文本表示与用户属性视图进行联合建模。"},"citation_metadata":{"reference_id":"REF37","citation_marker":"[37]","authors":["Guo et al."],"work_name":"BGSRD","year":2023},"intent":"用于引入研究方法","intent_code":"method_introduction","evidence_phrase":"本文引入Guo等人[37]使用的BERT表示方式","source_position":{"page_number":31,"source_section":"2 多视图集成机器人检测模型"},"confidence":0.97,"matched_training_examples":[{"sample_id":"TRAIN_METHOD_002","intent_label":"用于引入研究方法","similarity":0.93}]},{"citation_id":"CIT_INT_005","citation_markers":["[44]"],"citation_sentence":"在Twibot-20数据集上，与Lyu等人[44]提出的DCGNN相比，本文方法的F1值提高了2.8%。","context":{"previous_sentence":"为验证模型有效性，实验选取多种具有代表性的机器人检测模型作为基线。","current_sentence":"在Twibot-20数据集上，与Lyu等人[44]提出的DCGNN相比，本文方法的F1值提高了2.8%。","next_sentence":"结果表明，多视图集成能够提升模型在复杂用户场景下的识别能力。"},"citation_metadata":{"reference_id":"REF44","citation_marker":"[44]","authors":["Lyu et al."],"work_name":"DCGNN","year":2022},"intent":"用于结果比较","intent_code":"result_comparison","evidence_phrase":"与Lyu等人[44]提出的DCGNN相比，本文方法的F1值提高了2.8%","source_position":{"page_number":56,"source_section":"4.4 实验结果与分析"},"confidence":0.98,"matched_training_examples":[{"sample_id":"TRAIN_COMPARE_001","intent_label":"用于结果比较","similarity":0.97}]},{"citation_id":"CIT_INT_006","citation_markers":["[43]"],"citation_sentence":"本文模型在准确率和召回率上均优于BotBuster[43]，说明多教师蒸馏能够有效保持复杂模型的检测性能。","context":{"previous_sentence":"进一步比较不同方法在资源受限条件下的性能表现。","current_sentence":"本文模型在准确率和召回率上均优于BotBuster[43]，说明多教师蒸馏能够有效保持复杂模型的检测性能。","next_sentence":"同时，学生模型的参数规模和推理时间均得到明显降低。"},"citation_metadata":{"reference_id":"REF43","citation_marker":"[43]","authors":["Carley et al."],"work_name":"BotBuster","year":2023},"intent":"用于结果比较","intent_code":"result_comparison","evidence_phrase":"在准确率和召回率上均优于BotBuster[43]","source_position":{"page_number":58,"source_section":"4.4 实验结果与分析"},"confidence":0.97,"matched_training_examples":[{"sample_id":"TRAIN_COMPARE_002","intent_label":"用于结果比较","similarity":0.96}]}],"citation_intent_statistics":{"citation_count":6,"background_introduction_count":2,"method_introduction_count":2,"result_comparison_count":2,"intent_distribution":[{"intent":"用于背景介绍","count":2,"percentage":33.33},{"intent":"用于引入研究方法","count":2,"percentage":33.33},{"intent":"用于结果比较","count":2,"percentage":33.33}],"average_confidence":0.9683},"training_set_summary":{"sample_count":6,"preprocessing_status":"completed","class_distribution":[{"intent":"用于背景介绍","count":2},{"intent":"用于引入研究方法","count":2},{"intent":"用于结果比较","count":2}]}},"meta":{"analysis_settings":{"language":"zh","citation_extraction_mode":"auto_extract","context_window":1,"parse_reference_metadata":true,"minimum_confidence":0.75,"return_context":true,"return_position":true,"return_citation_metadata":true,"return_training_evidence":true},"training_set_used":true,"training_set_sample_count":6,"request_id":"req_citation_intent_file_202607210001","elapsed_ms":1386}},"demoBatchFileResult":{"code":200,"message":"batch_completed","data":{"batch_id":"batch_citation_intent_files_202607210001","input_type":"files","total":3,"success_count":3,"failed_count":0,"results":[{"index":1,"file_name":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架.pdf","status":"success","code":200,"result":{"tool":"引用意图识别","input_type":"file","input":{"file_name":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架.pdf","file_format":"PDF","file_size":"3.17 MB","document_parse_status":"success","citation_extraction_status":"success","context_extraction_status":"success","reference_metadata_match_status":"success","training_set_validation_status":"success"},"document":{"title":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架","language":"zh","page_count":83,"analysis_scope":"full_text"},"citation_intent_results":[{"citation_id":"CIT_INT_001","citation_markers":["[34]"],"citation_sentence":"Wu[34]等人提出的MSM-BD方法结合用户头像、用户属性和推文文本等多模态特征，并通过跨模态残差交叉注意力模块实现特征融合。","context":{"previous_sentence":"当前基于多模态数据的研究主要从特征融合和分类结果集成两个方向展开。","current_sentence":"Wu[34]等人提出的MSM-BD方法结合用户头像、用户属性和推文文本等多模态特征，并通过跨模态残差交叉注意力模块实现特征融合。","next_sentence":"随后，多项研究继续从多模态编码和融合机制方面改进机器人检测模型。"},"citation_metadata":{"reference_id":"REF34","citation_marker":"[34]","authors":["Wu et al."],"work_name":"MSM-BD","year":2022},"intent":"用于背景介绍","intent_code":"background_introduction","evidence_phrase":"提出的MSM-BD方法结合","source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.96,"matched_training_examples":[{"sample_id":"TRAIN_BG_001","intent_label":"用于背景介绍","similarity":0.94}]},{"citation_id":"CIT_INT_002","citation_markers":["[36]"],"citation_sentence":"Feng[36]等人提出SATAR自监督学习方法，该方法融合文本语义信息与用户行为特征，构建无监督表示学习框架。","context":{"previous_sentence":"BotSAI框架通过整合用户多模态信息提升检测准确性。","current_sentence":"Feng[36]等人提出SATAR自监督学习方法，该方法融合文本语义信息与用户行为特征，构建无监督表示学习框架。","next_sentence":"Guo等人[37]进一步融合BERT语义信息和GCN图结构关系。"},"citation_metadata":{"reference_id":"REF36","citation_marker":"[36]","authors":["Feng et al."],"work_name":"SATAR","year":2022},"intent":"用于背景介绍","intent_code":"background_introduction","evidence_phrase":"提出SATAR自监督学习方法","source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.95,"matched_training_examples":[{"sample_id":"TRAIN_BG_001","intent_label":"用于背景介绍","similarity":0.91}]},{"citation_id":"CIT_INT_003","citation_markers":["[55]"],"citation_sentence":"本文采用Hinton等人[55]提出的知识蒸馏思想，将多个教师模型输出的软标签迁移至轻量学生模型。","context":{"previous_sentence":"为降低复杂多视图模型的计算开销，需要压缩模型参数并保留教师模型的判别知识。","current_sentence":"本文采用Hinton等人[55]提出的知识蒸馏思想，将多个教师模型输出的软标签迁移至轻量学生模型。","next_sentence":"在此基础上，进一步设计多教师权重分配和蒸馏损失函数。"},"citation_metadata":{"reference_id":"REF55","citation_marker":"[55]","authors":["Hinton et al."],"work_name":"Knowledge Distillation","year":2015},"intent":"用于引入研究方法","intent_code":"method_introduction","evidence_phrase":"本文采用Hinton等人[55]提出的知识蒸馏思想","source_position":{"page_number":38,"source_section":"3 多教师知识蒸馏模型"},"confidence":0.98,"matched_training_examples":[{"sample_id":"TRAIN_METHOD_001","intent_label":"用于引入研究方法","similarity":0.95},{"sample_id":"TRAIN_METHOD_002","intent_label":"用于引入研究方法","similarity":0.88}]},{"citation_id":"CIT_INT_004","citation_markers":["[37]"],"citation_sentence":"在文本语义编码阶段，本文引入Guo等人[37]使用的BERT表示方式提取用户推文特征。","context":{"previous_sentence":"用户文本包含能够区分真实用户和机器人的语义线索。","current_sentence":"在文本语义编码阶段，本文引入Guo等人[37]使用的BERT表示方式提取用户推文特征。","next_sentence":"随后将文本表示与用户属性视图进行联合建模。"},"citation_metadata":{"reference_id":"REF37","citation_marker":"[37]","authors":["Guo et al."],"work_name":"BGSRD","year":2023},"intent":"用于引入研究方法","intent_code":"method_introduction","evidence_phrase":"本文引入Guo等人[37]使用的BERT表示方式","source_position":{"page_number":31,"source_section":"2 多视图集成机器人检测模型"},"confidence":0.97,"matched_training_examples":[{"sample_id":"TRAIN_METHOD_002","intent_label":"用于引入研究方法","similarity":0.93}]},{"citation_id":"CIT_INT_005","citation_markers":["[44]"],"citation_sentence":"在Twibot-20数据集上，与Lyu等人[44]提出的DCGNN相比，本文方法的F1值提高了2.8%。","context":{"previous_sentence":"为验证模型有效性，实验选取多种具有代表性的机器人检测模型作为基线。","current_sentence":"在Twibot-20数据集上，与Lyu等人[44]提出的DCGNN相比，本文方法的F1值提高了2.8%。","next_sentence":"结果表明，多视图集成能够提升模型在复杂用户场景下的识别能力。"},"citation_metadata":{"reference_id":"REF44","citation_marker":"[44]","authors":["Lyu et al."],"work_name":"DCGNN","year":2022},"intent":"用于结果比较","intent_code":"result_comparison","evidence_phrase":"与Lyu等人[44]提出的DCGNN相比，本文方法的F1值提高了2.8%","source_position":{"page_number":56,"source_section":"4.4 实验结果与分析"},"confidence":0.98,"matched_training_examples":[{"sample_id":"TRAIN_COMPARE_001","intent_label":"用于结果比较","similarity":0.97}]},{"citation_id":"CIT_INT_006","citation_markers":["[43]"],"citation_sentence":"本文模型在准确率和召回率上均优于BotBuster[43]，说明多教师蒸馏能够有效保持复杂模型的检测性能。","context":{"previous_sentence":"进一步比较不同方法在资源受限条件下的性能表现。","current_sentence":"本文模型在准确率和召回率上均优于BotBuster[43]，说明多教师蒸馏能够有效保持复杂模型的检测性能。","next_sentence":"同时，学生模型的参数规模和推理时间均得到明显降低。"},"citation_metadata":{"reference_id":"REF43","citation_marker":"[43]","authors":["Carley et al."],"work_name":"BotBuster","year":2023},"intent":"用于结果比较","intent_code":"result_comparison","evidence_phrase":"在准确率和召回率上均优于BotBuster[43]","source_position":{"page_number":58,"source_section":"4.4 实验结果与分析"},"confidence":0.97,"matched_training_examples":[{"sample_id":"TRAIN_COMPARE_002","intent_label":"用于结果比较","similarity":0.96}]}],"citation_intent_statistics":{"citation_count":6,"background_introduction_count":2,"method_introduction_count":2,"result_comparison_count":2,"intent_distribution":[{"intent":"用于背景介绍","count":2,"percentage":33.33},{"intent":"用于引入研究方法","count":2,"percentage":33.33},{"intent":"用于结果比较","count":2,"percentage":33.33}],"average_confidence":0.9683},"training_set_summary":{"sample_count":6,"preprocessing_status":"completed","class_distribution":[{"intent":"用于背景介绍","count":2},{"intent":"用于引入研究方法","count":2},{"intent":"用于结果比较","count":2}]}}},{"index":2,"file_name":"引用意图识别_相关工作背景介绍.txt","status":"success","code":200,"result":{"tool":"引用意图识别","input_type":"file","input":{"file_name":"引用意图识别_相关工作背景介绍.txt","file_format":"TXT","file_size":"322 B","document_parse_status":"success","citation_extraction_status":"success","context_extraction_status":"success","reference_metadata_match_status":"success","training_set_validation_status":"success"},"document":{"title":"社交媒体机器人检测相关工作引用片段","language":"zh","page_count":null,"analysis_scope":"full_text"},"citation_intent_results":[{"citation_id":"CIT_INT_001","citation_markers":["[34]"],"citation_sentence":"Wu[34]等人提出的MSM-BD方法结合用户头像、用户属性和推文文本等多模态特征，并通过跨模态残差交叉注意力模块实现特征融合。","context":{"previous_sentence":"当前基于多模态数据的研究主要从特征融合和分类结果集成两个方向展开。","current_sentence":"Wu[34]等人提出的MSM-BD方法结合用户头像、用户属性和推文文本等多模态特征，并通过跨模态残差交叉注意力模块实现特征融合。","next_sentence":"随后，多项研究继续从多模态编码和融合机制方面改进机器人检测模型。"},"citation_metadata":{"reference_id":"REF34","citation_marker":"[34]","authors":["Wu et al."],"work_name":"MSM-BD","year":2022},"intent":"用于背景介绍","intent_code":"background_introduction","evidence_phrase":"提出的MSM-BD方法结合","source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.96,"matched_training_examples":[{"sample_id":"TRAIN_BG_001","intent_label":"用于背景介绍","similarity":0.94}]},{"citation_id":"CIT_INT_002","citation_markers":["[36]"],"citation_sentence":"Feng[36]等人提出SATAR自监督学习方法，该方法融合文本语义信息与用户行为特征，构建无监督表示学习框架。","context":{"previous_sentence":"BotSAI框架通过整合用户多模态信息提升检测准确性。","current_sentence":"Feng[36]等人提出SATAR自监督学习方法，该方法融合文本语义信息与用户行为特征，构建无监督表示学习框架。","next_sentence":"Guo等人[37]进一步融合BERT语义信息和GCN图结构关系。"},"citation_metadata":{"reference_id":"REF36","citation_marker":"[36]","authors":["Feng et al."],"work_name":"SATAR","year":2022},"intent":"用于背景介绍","intent_code":"background_introduction","evidence_phrase":"提出SATAR自监督学习方法","source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.95,"matched_training_examples":[{"sample_id":"TRAIN_BG_001","intent_label":"用于背景介绍","similarity":0.91}]}],"citation_intent_statistics":{"citation_count":2,"background_introduction_count":2,"method_introduction_count":0,"result_comparison_count":0,"intent_distribution":[{"intent":"用于背景介绍","count":2,"percentage":100.0},{"intent":"用于引入研究方法","count":0,"percentage":0.0},{"intent":"用于结果比较","count":0,"percentage":0.0}],"average_confidence":0.955},"training_set_summary":{"sample_count":6,"preprocessing_status":"completed","class_distribution":[{"intent":"用于背景介绍","count":2},{"intent":"用于引入研究方法","count":2},{"intent":"用于结果比较","count":2}]}}},{"index":3,"file_name":"引用意图识别_方法引入与结果比较.txt","status":"success","code":200,"result":{"tool":"引用意图识别","input_type":"file","input":{"file_name":"引用意图识别_方法引入与结果比较.txt","file_format":"TXT","file_size":"269 B","document_parse_status":"success","citation_extraction_status":"success","context_extraction_status":"success","reference_metadata_match_status":"success","training_set_validation_status":"success"},"document":{"title":"社交媒体机器人检测方法与实验引用片段","language":"zh","page_count":null,"analysis_scope":"full_text"},"citation_intent_results":[{"citation_id":"CIT_INT_003","citation_markers":["[55]"],"citation_sentence":"本文采用Hinton等人[55]提出的知识蒸馏思想，将多个教师模型输出的软标签迁移至轻量学生模型。","context":{"previous_sentence":"为降低复杂多视图模型的计算开销，需要压缩模型参数并保留教师模型的判别知识。","current_sentence":"本文采用Hinton等人[55]提出的知识蒸馏思想，将多个教师模型输出的软标签迁移至轻量学生模型。","next_sentence":"在此基础上，进一步设计多教师权重分配和蒸馏损失函数。"},"citation_metadata":{"reference_id":"REF55","citation_marker":"[55]","authors":["Hinton et al."],"work_name":"Knowledge Distillation","year":2015},"intent":"用于引入研究方法","intent_code":"method_introduction","evidence_phrase":"本文采用Hinton等人[55]提出的知识蒸馏思想","source_position":{"page_number":38,"source_section":"3 多教师知识蒸馏模型"},"confidence":0.98,"matched_training_examples":[{"sample_id":"TRAIN_METHOD_001","intent_label":"用于引入研究方法","similarity":0.95},{"sample_id":"TRAIN_METHOD_002","intent_label":"用于引入研究方法","similarity":0.88}]},{"citation_id":"CIT_INT_004","citation_markers":["[37]"],"citation_sentence":"在文本语义编码阶段，本文引入Guo等人[37]使用的BERT表示方式提取用户推文特征。","context":{"previous_sentence":"用户文本包含能够区分真实用户和机器人的语义线索。","current_sentence":"在文本语义编码阶段，本文引入Guo等人[37]使用的BERT表示方式提取用户推文特征。","next_sentence":"随后将文本表示与用户属性视图进行联合建模。"},"citation_metadata":{"reference_id":"REF37","citation_marker":"[37]","authors":["Guo et al."],"work_name":"BGSRD","year":2023},"intent":"用于引入研究方法","intent_code":"method_introduction","evidence_phrase":"本文引入Guo等人[37]使用的BERT表示方式","source_position":{"page_number":31,"source_section":"2 多视图集成机器人检测模型"},"confidence":0.97,"matched_training_examples":[{"sample_id":"TRAIN_METHOD_002","intent_label":"用于引入研究方法","similarity":0.93}]},{"citation_id":"CIT_INT_005","citation_markers":["[44]"],"citation_sentence":"在Twibot-20数据集上，与Lyu等人[44]提出的DCGNN相比，本文方法的F1值提高了2.8%。","context":{"previous_sentence":"为验证模型有效性，实验选取多种具有代表性的机器人检测模型作为基线。","current_sentence":"在Twibot-20数据集上，与Lyu等人[44]提出的DCGNN相比，本文方法的F1值提高了2.8%。","next_sentence":"结果表明，多视图集成能够提升模型在复杂用户场景下的识别能力。"},"citation_metadata":{"reference_id":"REF44","citation_marker":"[44]","authors":["Lyu et al."],"work_name":"DCGNN","year":2022},"intent":"用于结果比较","intent_code":"result_comparison","evidence_phrase":"与Lyu等人[44]提出的DCGNN相比，本文方法的F1值提高了2.8%","source_position":{"page_number":56,"source_section":"4.4 实验结果与分析"},"confidence":0.98,"matched_training_examples":[{"sample_id":"TRAIN_COMPARE_001","intent_label":"用于结果比较","similarity":0.97}]},{"citation_id":"CIT_INT_006","citation_markers":["[43]"],"citation_sentence":"本文模型在准确率和召回率上均优于BotBuster[43]，说明多教师蒸馏能够有效保持复杂模型的检测性能。","context":{"previous_sentence":"进一步比较不同方法在资源受限条件下的性能表现。","current_sentence":"本文模型在准确率和召回率上均优于BotBuster[43]，说明多教师蒸馏能够有效保持复杂模型的检测性能。","next_sentence":"同时，学生模型的参数规模和推理时间均得到明显降低。"},"citation_metadata":{"reference_id":"REF43","citation_marker":"[43]","authors":["Carley et al."],"work_name":"BotBuster","year":2023},"intent":"用于结果比较","intent_code":"result_comparison","evidence_phrase":"在准确率和召回率上均优于BotBuster[43]","source_position":{"page_number":58,"source_section":"4.4 实验结果与分析"},"confidence":0.97,"matched_training_examples":[{"sample_id":"TRAIN_COMPARE_002","intent_label":"用于结果比较","similarity":0.96}]}],"citation_intent_statistics":{"citation_count":4,"background_introduction_count":0,"method_introduction_count":2,"result_comparison_count":2,"intent_distribution":[{"intent":"用于背景介绍","count":0,"percentage":0.0},{"intent":"用于引入研究方法","count":2,"percentage":50.0},{"intent":"用于结果比较","count":2,"percentage":50.0}],"average_confidence":0.975},"training_set_summary":{"sample_count":6,"preprocessing_status":"completed","class_distribution":[{"intent":"用于背景介绍","count":2},{"intent":"用于引入研究方法","count":2},{"intent":"用于结果比较","count":2}]}}}]},"meta":{"analysis_settings":{"language":"zh","citation_extraction_mode":"auto_extract","context_window":1,"parse_reference_metadata":true,"minimum_confidence":0.75,"return_context":true,"return_position":true,"return_citation_metadata":true,"return_training_evidence":true},"training_set_sample_count":6,"max_concurrency":3,"continue_on_error":true,"elapsed_ms":3268}},"response":{"code":200,"message":"batch_completed","data":{"batch_id":"batch_citation_intent_files_202607210001","input_type":"files","total":3,"success_count":3,"failed_count":0,"results":[{"index":1,"file_name":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架.pdf","status":"success","code":200,"result":{"tool":"引用意图识别","input_type":"file","input":{"file_name":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架.pdf","file_format":"PDF","file_size":"3.17 MB","document_parse_status":"success","citation_extraction_status":"success","context_extraction_status":"success","reference_metadata_match_status":"success","training_set_validation_status":"success"},"document":{"title":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架","language":"zh","page_count":83,"analysis_scope":"full_text"},"citation_intent_results":[{"citation_id":"CIT_INT_001","citation_markers":["[34]"],"citation_sentence":"Wu[34]等人提出的MSM-BD方法结合用户头像、用户属性和推文文本等多模态特征，并通过跨模态残差交叉注意力模块实现特征融合。","context":{"previous_sentence":"当前基于多模态数据的研究主要从特征融合和分类结果集成两个方向展开。","current_sentence":"Wu[34]等人提出的MSM-BD方法结合用户头像、用户属性和推文文本等多模态特征，并通过跨模态残差交叉注意力模块实现特征融合。","next_sentence":"随后，多项研究继续从多模态编码和融合机制方面改进机器人检测模型。"},"citation_metadata":{"reference_id":"REF34","citation_marker":"[34]","authors":["Wu et al."],"work_name":"MSM-BD","year":2022},"intent":"用于背景介绍","intent_code":"background_introduction","evidence_phrase":"提出的MSM-BD方法结合","source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.96,"matched_training_examples":[{"sample_id":"TRAIN_BG_001","intent_label":"用于背景介绍","similarity":0.94}]},{"citation_id":"CIT_INT_002","citation_markers":["[36]"],"citation_sentence":"Feng[36]等人提出SATAR自监督学习方法，该方法融合文本语义信息与用户行为特征，构建无监督表示学习框架。","context":{"previous_sentence":"BotSAI框架通过整合用户多模态信息提升检测准确性。","current_sentence":"Feng[36]等人提出SATAR自监督学习方法，该方法融合文本语义信息与用户行为特征，构建无监督表示学习框架。","next_sentence":"Guo等人[37]进一步融合BERT语义信息和GCN图结构关系。"},"citation_metadata":{"reference_id":"REF36","citation_marker":"[36]","authors":["Feng et al."],"work_name":"SATAR","year":2022},"intent":"用于背景介绍","intent_code":"background_introduction","evidence_phrase":"提出SATAR自监督学习方法","source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.95,"matched_training_examples":[{"sample_id":"TRAIN_BG_001","intent_label":"用于背景介绍","similarity":0.91}]},{"citation_id":"CIT_INT_003","citation_markers":["[55]"],"citation_sentence":"本文采用Hinton等人[55]提出的知识蒸馏思想，将多个教师模型输出的软标签迁移至轻量学生模型。","context":{"previous_sentence":"为降低复杂多视图模型的计算开销，需要压缩模型参数并保留教师模型的判别知识。","current_sentence":"本文采用Hinton等人[55]提出的知识蒸馏思想，将多个教师模型输出的软标签迁移至轻量学生模型。","next_sentence":"在此基础上，进一步设计多教师权重分配和蒸馏损失函数。"},"citation_metadata":{"reference_id":"REF55","citation_marker":"[55]","authors":["Hinton et al."],"work_name":"Knowledge Distillation","year":2015},"intent":"用于引入研究方法","intent_code":"method_introduction","evidence_phrase":"本文采用Hinton等人[55]提出的知识蒸馏思想","source_position":{"page_number":38,"source_section":"3 多教师知识蒸馏模型"},"confidence":0.98,"matched_training_examples":[{"sample_id":"TRAIN_METHOD_001","intent_label":"用于引入研究方法","similarity":0.95},{"sample_id":"TRAIN_METHOD_002","intent_label":"用于引入研究方法","similarity":0.88}]},{"citation_id":"CIT_INT_004","citation_markers":["[37]"],"citation_sentence":"在文本语义编码阶段，本文引入Guo等人[37]使用的BERT表示方式提取用户推文特征。","context":{"previous_sentence":"用户文本包含能够区分真实用户和机器人的语义线索。","current_sentence":"在文本语义编码阶段，本文引入Guo等人[37]使用的BERT表示方式提取用户推文特征。","next_sentence":"随后将文本表示与用户属性视图进行联合建模。"},"citation_metadata":{"reference_id":"REF37","citation_marker":"[37]","authors":["Guo et al."],"work_name":"BGSRD","year":2023},"intent":"用于引入研究方法","intent_code":"method_introduction","evidence_phrase":"本文引入Guo等人[37]使用的BERT表示方式","source_position":{"page_number":31,"source_section":"2 多视图集成机器人检测模型"},"confidence":0.97,"matched_training_examples":[{"sample_id":"TRAIN_METHOD_002","intent_label":"用于引入研究方法","similarity":0.93}]},{"citation_id":"CIT_INT_005","citation_markers":["[44]"],"citation_sentence":"在Twibot-20数据集上，与Lyu等人[44]提出的DCGNN相比，本文方法的F1值提高了2.8%。","context":{"previous_sentence":"为验证模型有效性，实验选取多种具有代表性的机器人检测模型作为基线。","current_sentence":"在Twibot-20数据集上，与Lyu等人[44]提出的DCGNN相比，本文方法的F1值提高了2.8%。","next_sentence":"结果表明，多视图集成能够提升模型在复杂用户场景下的识别能力。"},"citation_metadata":{"reference_id":"REF44","citation_marker":"[44]","authors":["Lyu et al."],"work_name":"DCGNN","year":2022},"intent":"用于结果比较","intent_code":"result_comparison","evidence_phrase":"与Lyu等人[44]提出的DCGNN相比，本文方法的F1值提高了2.8%","source_position":{"page_number":56,"source_section":"4.4 实验结果与分析"},"confidence":0.98,"matched_training_examples":[{"sample_id":"TRAIN_COMPARE_001","intent_label":"用于结果比较","similarity":0.97}]},{"citation_id":"CIT_INT_006","citation_markers":["[43]"],"citation_sentence":"本文模型在准确率和召回率上均优于BotBuster[43]，说明多教师蒸馏能够有效保持复杂模型的检测性能。","context":{"previous_sentence":"进一步比较不同方法在资源受限条件下的性能表现。","current_sentence":"本文模型在准确率和召回率上均优于BotBuster[43]，说明多教师蒸馏能够有效保持复杂模型的检测性能。","next_sentence":"同时，学生模型的参数规模和推理时间均得到明显降低。"},"citation_metadata":{"reference_id":"REF43","citation_marker":"[43]","authors":["Carley et al."],"work_name":"BotBuster","year":2023},"intent":"用于结果比较","intent_code":"result_comparison","evidence_phrase":"在准确率和召回率上均优于BotBuster[43]","source_position":{"page_number":58,"source_section":"4.4 实验结果与分析"},"confidence":0.97,"matched_training_examples":[{"sample_id":"TRAIN_COMPARE_002","intent_label":"用于结果比较","similarity":0.96}]}],"citation_intent_statistics":{"citation_count":6,"background_introduction_count":2,"method_introduction_count":2,"result_comparison_count":2,"intent_distribution":[{"intent":"用于背景介绍","count":2,"percentage":33.33},{"intent":"用于引入研究方法","count":2,"percentage":33.33},{"intent":"用于结果比较","count":2,"percentage":33.33}],"average_confidence":0.9683},"training_set_summary":{"sample_count":6,"preprocessing_status":"completed","class_distribution":[{"intent":"用于背景介绍","count":2},{"intent":"用于引入研究方法","count":2},{"intent":"用于结果比较","count":2}]}}},{"index":2,"file_name":"引用意图识别_相关工作背景介绍.txt","status":"success","code":200,"result":{"tool":"引用意图识别","input_type":"file","input":{"file_name":"引用意图识别_相关工作背景介绍.txt","file_format":"TXT","file_size":"322 B","document_parse_status":"success","citation_extraction_status":"success","context_extraction_status":"success","reference_metadata_match_status":"success","training_set_validation_status":"success"},"document":{"title":"社交媒体机器人检测相关工作引用片段","language":"zh","page_count":null,"analysis_scope":"full_text"},"citation_intent_results":[{"citation_id":"CIT_INT_001","citation_markers":["[34]"],"citation_sentence":"Wu[34]等人提出的MSM-BD方法结合用户头像、用户属性和推文文本等多模态特征，并通过跨模态残差交叉注意力模块实现特征融合。","context":{"previous_sentence":"当前基于多模态数据的研究主要从特征融合和分类结果集成两个方向展开。","current_sentence":"Wu[34]等人提出的MSM-BD方法结合用户头像、用户属性和推文文本等多模态特征，并通过跨模态残差交叉注意力模块实现特征融合。","next_sentence":"随后，多项研究继续从多模态编码和融合机制方面改进机器人检测模型。"},"citation_metadata":{"reference_id":"REF34","citation_marker":"[34]","authors":["Wu et al."],"work_name":"MSM-BD","year":2022},"intent":"用于背景介绍","intent_code":"background_introduction","evidence_phrase":"提出的MSM-BD方法结合","source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.96,"matched_training_examples":[{"sample_id":"TRAIN_BG_001","intent_label":"用于背景介绍","similarity":0.94}]},{"citation_id":"CIT_INT_002","citation_markers":["[36]"],"citation_sentence":"Feng[36]等人提出SATAR自监督学习方法，该方法融合文本语义信息与用户行为特征，构建无监督表示学习框架。","context":{"previous_sentence":"BotSAI框架通过整合用户多模态信息提升检测准确性。","current_sentence":"Feng[36]等人提出SATAR自监督学习方法，该方法融合文本语义信息与用户行为特征，构建无监督表示学习框架。","next_sentence":"Guo等人[37]进一步融合BERT语义信息和GCN图结构关系。"},"citation_metadata":{"reference_id":"REF36","citation_marker":"[36]","authors":["Feng et al."],"work_name":"SATAR","year":2022},"intent":"用于背景介绍","intent_code":"background_introduction","evidence_phrase":"提出SATAR自监督学习方法","source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.95,"matched_training_examples":[{"sample_id":"TRAIN_BG_001","intent_label":"用于背景介绍","similarity":0.91}]}],"citation_intent_statistics":{"citation_count":2,"background_introduction_count":2,"method_introduction_count":0,"result_comparison_count":0,"intent_distribution":[{"intent":"用于背景介绍","count":2,"percentage":100.0},{"intent":"用于引入研究方法","count":0,"percentage":0.0},{"intent":"用于结果比较","count":0,"percentage":0.0}],"average_confidence":0.955},"training_set_summary":{"sample_count":6,"preprocessing_status":"completed","class_distribution":[{"intent":"用于背景介绍","count":2},{"intent":"用于引入研究方法","count":2},{"intent":"用于结果比较","count":2}]}}},{"index":3,"file_name":"引用意图识别_方法引入与结果比较.txt","status":"success","code":200,"result":{"tool":"引用意图识别","input_type":"file","input":{"file_name":"引用意图识别_方法引入与结果比较.txt","file_format":"TXT","file_size":"269 B","document_parse_status":"success","citation_extraction_status":"success","context_extraction_status":"success","reference_metadata_match_status":"success","training_set_validation_status":"success"},"document":{"title":"社交媒体机器人检测方法与实验引用片段","language":"zh","page_count":null,"analysis_scope":"full_text"},"citation_intent_results":[{"citation_id":"CIT_INT_003","citation_markers":["[55]"],"citation_sentence":"本文采用Hinton等人[55]提出的知识蒸馏思想，将多个教师模型输出的软标签迁移至轻量学生模型。","context":{"previous_sentence":"为降低复杂多视图模型的计算开销，需要压缩模型参数并保留教师模型的判别知识。","current_sentence":"本文采用Hinton等人[55]提出的知识蒸馏思想，将多个教师模型输出的软标签迁移至轻量学生模型。","next_sentence":"在此基础上，进一步设计多教师权重分配和蒸馏损失函数。"},"citation_metadata":{"reference_id":"REF55","citation_marker":"[55]","authors":["Hinton et al."],"work_name":"Knowledge Distillation","year":2015},"intent":"用于引入研究方法","intent_code":"method_introduction","evidence_phrase":"本文采用Hinton等人[55]提出的知识蒸馏思想","source_position":{"page_number":38,"source_section":"3 多教师知识蒸馏模型"},"confidence":0.98,"matched_training_examples":[{"sample_id":"TRAIN_METHOD_001","intent_label":"用于引入研究方法","similarity":0.95},{"sample_id":"TRAIN_METHOD_002","intent_label":"用于引入研究方法","similarity":0.88}]},{"citation_id":"CIT_INT_004","citation_markers":["[37]"],"citation_sentence":"在文本语义编码阶段，本文引入Guo等人[37]使用的BERT表示方式提取用户推文特征。","context":{"previous_sentence":"用户文本包含能够区分真实用户和机器人的语义线索。","current_sentence":"在文本语义编码阶段，本文引入Guo等人[37]使用的BERT表示方式提取用户推文特征。","next_sentence":"随后将文本表示与用户属性视图进行联合建模。"},"citation_metadata":{"reference_id":"REF37","citation_marker":"[37]","authors":["Guo et al."],"work_name":"BGSRD","year":2023},"intent":"用于引入研究方法","intent_code":"method_introduction","evidence_phrase":"本文引入Guo等人[37]使用的BERT表示方式","source_position":{"page_number":31,"source_section":"2 多视图集成机器人检测模型"},"confidence":0.97,"matched_training_examples":[{"sample_id":"TRAIN_METHOD_002","intent_label":"用于引入研究方法","similarity":0.93}]},{"citation_id":"CIT_INT_005","citation_markers":["[44]"],"citation_sentence":"在Twibot-20数据集上，与Lyu等人[44]提出的DCGNN相比，本文方法的F1值提高了2.8%。","context":{"previous_sentence":"为验证模型有效性，实验选取多种具有代表性的机器人检测模型作为基线。","current_sentence":"在Twibot-20数据集上，与Lyu等人[44]提出的DCGNN相比，本文方法的F1值提高了2.8%。","next_sentence":"结果表明，多视图集成能够提升模型在复杂用户场景下的识别能力。"},"citation_metadata":{"reference_id":"REF44","citation_marker":"[44]","authors":["Lyu et al."],"work_name":"DCGNN","year":2022},"intent":"用于结果比较","intent_code":"result_comparison","evidence_phrase":"与Lyu等人[44]提出的DCGNN相比，本文方法的F1值提高了2.8%","source_position":{"page_number":56,"source_section":"4.4 实验结果与分析"},"confidence":0.98,"matched_training_examples":[{"sample_id":"TRAIN_COMPARE_001","intent_label":"用于结果比较","similarity":0.97}]},{"citation_id":"CIT_INT_006","citation_markers":["[43]"],"citation_sentence":"本文模型在准确率和召回率上均优于BotBuster[43]，说明多教师蒸馏能够有效保持复杂模型的检测性能。","context":{"previous_sentence":"进一步比较不同方法在资源受限条件下的性能表现。","current_sentence":"本文模型在准确率和召回率上均优于BotBuster[43]，说明多教师蒸馏能够有效保持复杂模型的检测性能。","next_sentence":"同时，学生模型的参数规模和推理时间均得到明显降低。"},"citation_metadata":{"reference_id":"REF43","citation_marker":"[43]","authors":["Carley et al."],"work_name":"BotBuster","year":2023},"intent":"用于结果比较","intent_code":"result_comparison","evidence_phrase":"在准确率和召回率上均优于BotBuster[43]","source_position":{"page_number":58,"source_section":"4.4 实验结果与分析"},"confidence":0.97,"matched_training_examples":[{"sample_id":"TRAIN_COMPARE_002","intent_label":"用于结果比较","similarity":0.96}]}],"citation_intent_statistics":{"citation_count":4,"background_introduction_count":0,"method_introduction_count":2,"result_comparison_count":2,"intent_distribution":[{"intent":"用于背景介绍","count":0,"percentage":0.0},{"intent":"用于引入研究方法","count":2,"percentage":50.0},{"intent":"用于结果比较","count":2,"percentage":50.0}],"average_confidence":0.975},"training_set_summary":{"sample_count":6,"preprocessing_status":"completed","class_distribution":[{"intent":"用于背景介绍","count":2},{"intent":"用于引入研究方法","count":2},{"intent":"用于结果比较","count":2}]}}}]},"meta":{"analysis_settings":{"language":"zh","citation_extraction_mode":"auto_extract","context_window":1,"parse_reference_metadata":true,"minimum_confidence":0.75,"return_context":true,"return_position":true,"return_citation_metadata":true,"return_training_evidence":true},"training_set_sample_count":6,"max_concurrency":3,"continue_on_error":true,"elapsed_ms":3268}},"demoFileFixtures":[{"file_name":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架.pdf","size_bytes":3322216,"sha256":"4c51e28c11e4954d05e192a41337eb0e7d606c0b9097aeafa16ba858711b91c0","fnv1a32":"20540fb6","result":{"code":200,"message":"success","data":{"tool":"引用意图识别","input_type":"file","input":{"file_name":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架.pdf","file_format":"PDF","file_size":"3.17 MB","document_parse_status":"success","citation_extraction_status":"success","context_extraction_status":"success","reference_metadata_match_status":"success","training_set_validation_status":"success"},"document":{"title":"基于多视图集成与多教师知识蒸馏的社交媒体机器人检测框架","language":"zh","page_count":83,"analysis_scope":"full_text"},"citation_intent_results":[{"citation_id":"CIT_INT_001","citation_markers":["[34]"],"citation_sentence":"Wu[34]等人提出的MSM-BD方法结合用户头像、用户属性和推文文本等多模态特征，并通过跨模态残差交叉注意力模块实现特征融合。","context":{"previous_sentence":"当前基于多模态数据的研究主要从特征融合和分类结果集成两个方向展开。","current_sentence":"Wu[34]等人提出的MSM-BD方法结合用户头像、用户属性和推文文本等多模态特征，并通过跨模态残差交叉注意力模块实现特征融合。","next_sentence":"随后，多项研究继续从多模态编码和融合机制方面改进机器人检测模型。"},"citation_metadata":{"reference_id":"REF34","citation_marker":"[34]","authors":["Wu et al."],"work_name":"MSM-BD","year":2022},"intent":"用于背景介绍","intent_code":"background_introduction","evidence_phrase":"提出的MSM-BD方法结合","source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.96,"matched_training_examples":[{"sample_id":"TRAIN_BG_001","intent_label":"用于背景介绍","similarity":0.94}]},{"citation_id":"CIT_INT_002","citation_markers":["[36]"],"citation_sentence":"Feng[36]等人提出SATAR自监督学习方法，该方法融合文本语义信息与用户行为特征，构建无监督表示学习框架。","context":{"previous_sentence":"BotSAI框架通过整合用户多模态信息提升检测准确性。","current_sentence":"Feng[36]等人提出SATAR自监督学习方法，该方法融合文本语义信息与用户行为特征，构建无监督表示学习框架。","next_sentence":"Guo等人[37]进一步融合BERT语义信息和GCN图结构关系。"},"citation_metadata":{"reference_id":"REF36","citation_marker":"[36]","authors":["Feng et al."],"work_name":"SATAR","year":2022},"intent":"用于背景介绍","intent_code":"background_introduction","evidence_phrase":"提出SATAR自监督学习方法","source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.95,"matched_training_examples":[{"sample_id":"TRAIN_BG_001","intent_label":"用于背景介绍","similarity":0.91}]},{"citation_id":"CIT_INT_003","citation_markers":["[55]"],"citation_sentence":"本文采用Hinton等人[55]提出的知识蒸馏思想，将多个教师模型输出的软标签迁移至轻量学生模型。","context":{"previous_sentence":"为降低复杂多视图模型的计算开销，需要压缩模型参数并保留教师模型的判别知识。","current_sentence":"本文采用Hinton等人[55]提出的知识蒸馏思想，将多个教师模型输出的软标签迁移至轻量学生模型。","next_sentence":"在此基础上，进一步设计多教师权重分配和蒸馏损失函数。"},"citation_metadata":{"reference_id":"REF55","citation_marker":"[55]","authors":["Hinton et al."],"work_name":"Knowledge Distillation","year":2015},"intent":"用于引入研究方法","intent_code":"method_introduction","evidence_phrase":"本文采用Hinton等人[55]提出的知识蒸馏思想","source_position":{"page_number":38,"source_section":"3 多教师知识蒸馏模型"},"confidence":0.98,"matched_training_examples":[{"sample_id":"TRAIN_METHOD_001","intent_label":"用于引入研究方法","similarity":0.95},{"sample_id":"TRAIN_METHOD_002","intent_label":"用于引入研究方法","similarity":0.88}]},{"citation_id":"CIT_INT_004","citation_markers":["[37]"],"citation_sentence":"在文本语义编码阶段，本文引入Guo等人[37]使用的BERT表示方式提取用户推文特征。","context":{"previous_sentence":"用户文本包含能够区分真实用户和机器人的语义线索。","current_sentence":"在文本语义编码阶段，本文引入Guo等人[37]使用的BERT表示方式提取用户推文特征。","next_sentence":"随后将文本表示与用户属性视图进行联合建模。"},"citation_metadata":{"reference_id":"REF37","citation_marker":"[37]","authors":["Guo et al."],"work_name":"BGSRD","year":2023},"intent":"用于引入研究方法","intent_code":"method_introduction","evidence_phrase":"本文引入Guo等人[37]使用的BERT表示方式","source_position":{"page_number":31,"source_section":"2 多视图集成机器人检测模型"},"confidence":0.97,"matched_training_examples":[{"sample_id":"TRAIN_METHOD_002","intent_label":"用于引入研究方法","similarity":0.93}]},{"citation_id":"CIT_INT_005","citation_markers":["[44]"],"citation_sentence":"在Twibot-20数据集上，与Lyu等人[44]提出的DCGNN相比，本文方法的F1值提高了2.8%。","context":{"previous_sentence":"为验证模型有效性，实验选取多种具有代表性的机器人检测模型作为基线。","current_sentence":"在Twibot-20数据集上，与Lyu等人[44]提出的DCGNN相比，本文方法的F1值提高了2.8%。","next_sentence":"结果表明，多视图集成能够提升模型在复杂用户场景下的识别能力。"},"citation_metadata":{"reference_id":"REF44","citation_marker":"[44]","authors":["Lyu et al."],"work_name":"DCGNN","year":2022},"intent":"用于结果比较","intent_code":"result_comparison","evidence_phrase":"与Lyu等人[44]提出的DCGNN相比，本文方法的F1值提高了2.8%","source_position":{"page_number":56,"source_section":"4.4 实验结果与分析"},"confidence":0.98,"matched_training_examples":[{"sample_id":"TRAIN_COMPARE_001","intent_label":"用于结果比较","similarity":0.97}]},{"citation_id":"CIT_INT_006","citation_markers":["[43]"],"citation_sentence":"本文模型在准确率和召回率上均优于BotBuster[43]，说明多教师蒸馏能够有效保持复杂模型的检测性能。","context":{"previous_sentence":"进一步比较不同方法在资源受限条件下的性能表现。","current_sentence":"本文模型在准确率和召回率上均优于BotBuster[43]，说明多教师蒸馏能够有效保持复杂模型的检测性能。","next_sentence":"同时，学生模型的参数规模和推理时间均得到明显降低。"},"citation_metadata":{"reference_id":"REF43","citation_marker":"[43]","authors":["Carley et al."],"work_name":"BotBuster","year":2023},"intent":"用于结果比较","intent_code":"result_comparison","evidence_phrase":"在准确率和召回率上均优于BotBuster[43]","source_position":{"page_number":58,"source_section":"4.4 实验结果与分析"},"confidence":0.97,"matched_training_examples":[{"sample_id":"TRAIN_COMPARE_002","intent_label":"用于结果比较","similarity":0.96}]}],"citation_intent_statistics":{"citation_count":6,"background_introduction_count":2,"method_introduction_count":2,"result_comparison_count":2,"intent_distribution":[{"intent":"用于背景介绍","count":2,"percentage":33.33},{"intent":"用于引入研究方法","count":2,"percentage":33.33},{"intent":"用于结果比较","count":2,"percentage":33.33}],"average_confidence":0.9683},"training_set_summary":{"sample_count":6,"preprocessing_status":"completed","class_distribution":[{"intent":"用于背景介绍","count":2},{"intent":"用于引入研究方法","count":2},{"intent":"用于结果比较","count":2}]}},"meta":{"analysis_settings":{"language":"zh","citation_extraction_mode":"auto_extract","context_window":1,"parse_reference_metadata":true,"minimum_confidence":0.75,"return_context":true,"return_position":true,"return_citation_metadata":true,"return_training_evidence":true},"training_set_used":true,"training_set_sample_count":6,"request_id":"req_citation_intent_file_202607210001","elapsed_ms":1386}}},{"file_name":"引用意图识别_相关工作背景介绍.txt","size_bytes":322,"sha256":"7938ec488d65704d44df7f989773fa72f4af5a10e20dad6c1307075267bf00cb","fnv1a32":"b5246cc7","result":{"code":200,"message":"success","data":{"tool":"引用意图识别","input_type":"file","input":{"file_name":"引用意图识别_相关工作背景介绍.txt","file_format":"TXT","file_size":"322 B","document_parse_status":"success","citation_extraction_status":"success","context_extraction_status":"success","reference_metadata_match_status":"success","training_set_validation_status":"success"},"document":{"title":"社交媒体机器人检测相关工作引用片段","language":"zh","page_count":null,"analysis_scope":"full_text"},"citation_intent_results":[{"citation_id":"CIT_INT_001","citation_markers":["[34]"],"citation_sentence":"Wu[34]等人提出的MSM-BD方法结合用户头像、用户属性和推文文本等多模态特征，并通过跨模态残差交叉注意力模块实现特征融合。","context":{"previous_sentence":"当前基于多模态数据的研究主要从特征融合和分类结果集成两个方向展开。","current_sentence":"Wu[34]等人提出的MSM-BD方法结合用户头像、用户属性和推文文本等多模态特征，并通过跨模态残差交叉注意力模块实现特征融合。","next_sentence":"随后，多项研究继续从多模态编码和融合机制方面改进机器人检测模型。"},"citation_metadata":{"reference_id":"REF34","citation_marker":"[34]","authors":["Wu et al."],"work_name":"MSM-BD","year":2022},"intent":"用于背景介绍","intent_code":"background_introduction","evidence_phrase":"提出的MSM-BD方法结合","source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.96,"matched_training_examples":[{"sample_id":"TRAIN_BG_001","intent_label":"用于背景介绍","similarity":0.94}]},{"citation_id":"CIT_INT_002","citation_markers":["[36]"],"citation_sentence":"Feng[36]等人提出SATAR自监督学习方法，该方法融合文本语义信息与用户行为特征，构建无监督表示学习框架。","context":{"previous_sentence":"BotSAI框架通过整合用户多模态信息提升检测准确性。","current_sentence":"Feng[36]等人提出SATAR自监督学习方法，该方法融合文本语义信息与用户行为特征，构建无监督表示学习框架。","next_sentence":"Guo等人[37]进一步融合BERT语义信息和GCN图结构关系。"},"citation_metadata":{"reference_id":"REF36","citation_marker":"[36]","authors":["Feng et al."],"work_name":"SATAR","year":2022},"intent":"用于背景介绍","intent_code":"background_introduction","evidence_phrase":"提出SATAR自监督学习方法","source_position":{"page_number":16,"source_section":"1.2.1 基于多模态数据建模的社交媒体机器人检测方法"},"confidence":0.95,"matched_training_examples":[{"sample_id":"TRAIN_BG_001","intent_label":"用于背景介绍","similarity":0.91}]}],"citation_intent_statistics":{"citation_count":2,"background_introduction_count":2,"method_introduction_count":0,"result_comparison_count":0,"intent_distribution":[{"intent":"用于背景介绍","count":2,"percentage":100.0},{"intent":"用于引入研究方法","count":0,"percentage":0.0},{"intent":"用于结果比较","count":0,"percentage":0.0}],"average_confidence":0.955},"training_set_summary":{"sample_count":6,"preprocessing_status":"completed","class_distribution":[{"intent":"用于背景介绍","count":2},{"intent":"用于引入研究方法","count":2},{"intent":"用于结果比较","count":2}]}},"meta":{"analysis_settings":{"language":"zh","citation_extraction_mode":"auto_extract","context_window":1,"parse_reference_metadata":true,"minimum_confidence":0.75,"return_context":true,"return_position":true,"return_citation_metadata":true,"return_training_evidence":true},"training_set_used":true,"training_set_sample_count":6,"request_id":"req_citation_intent_background_txt_202607210001","elapsed_ms":1386}}},{"file_name":"引用意图识别_方法引入与结果比较.txt","size_bytes":269,"sha256":"3c6048fd4766146f79c2b3b276001839e634ceb5839b0682483035d5271e6b0c","fnv1a32":"a511788c","result":{"code":200,"message":"success","data":{"tool":"引用意图识别","input_type":"file","input":{"file_name":"引用意图识别_方法引入与结果比较.txt","file_format":"TXT","file_size":"269 B","document_parse_status":"success","citation_extraction_status":"success","context_extraction_status":"success","reference_metadata_match_status":"success","training_set_validation_status":"success"},"document":{"title":"社交媒体机器人检测方法与实验引用片段","language":"zh","page_count":null,"analysis_scope":"full_text"},"citation_intent_results":[{"citation_id":"CIT_INT_003","citation_markers":["[55]"],"citation_sentence":"本文采用Hinton等人[55]提出的知识蒸馏思想，将多个教师模型输出的软标签迁移至轻量学生模型。","context":{"previous_sentence":"为降低复杂多视图模型的计算开销，需要压缩模型参数并保留教师模型的判别知识。","current_sentence":"本文采用Hinton等人[55]提出的知识蒸馏思想，将多个教师模型输出的软标签迁移至轻量学生模型。","next_sentence":"在此基础上，进一步设计多教师权重分配和蒸馏损失函数。"},"citation_metadata":{"reference_id":"REF55","citation_marker":"[55]","authors":["Hinton et al."],"work_name":"Knowledge Distillation","year":2015},"intent":"用于引入研究方法","intent_code":"method_introduction","evidence_phrase":"本文采用Hinton等人[55]提出的知识蒸馏思想","source_position":{"page_number":38,"source_section":"3 多教师知识蒸馏模型"},"confidence":0.98,"matched_training_examples":[{"sample_id":"TRAIN_METHOD_001","intent_label":"用于引入研究方法","similarity":0.95},{"sample_id":"TRAIN_METHOD_002","intent_label":"用于引入研究方法","similarity":0.88}]},{"citation_id":"CIT_INT_004","citation_markers":["[37]"],"citation_sentence":"在文本语义编码阶段，本文引入Guo等人[37]使用的BERT表示方式提取用户推文特征。","context":{"previous_sentence":"用户文本包含能够区分真实用户和机器人的语义线索。","current_sentence":"在文本语义编码阶段，本文引入Guo等人[37]使用的BERT表示方式提取用户推文特征。","next_sentence":"随后将文本表示与用户属性视图进行联合建模。"},"citation_metadata":{"reference_id":"REF37","citation_marker":"[37]","authors":["Guo et al."],"work_name":"BGSRD","year":2023},"intent":"用于引入研究方法","intent_code":"method_introduction","evidence_phrase":"本文引入Guo等人[37]使用的BERT表示方式","source_position":{"page_number":31,"source_section":"2 多视图集成机器人检测模型"},"confidence":0.97,"matched_training_examples":[{"sample_id":"TRAIN_METHOD_002","intent_label":"用于引入研究方法","similarity":0.93}]},{"citation_id":"CIT_INT_005","citation_markers":["[44]"],"citation_sentence":"在Twibot-20数据集上，与Lyu等人[44]提出的DCGNN相比，本文方法的F1值提高了2.8%。","context":{"previous_sentence":"为验证模型有效性，实验选取多种具有代表性的机器人检测模型作为基线。","current_sentence":"在Twibot-20数据集上，与Lyu等人[44]提出的DCGNN相比，本文方法的F1值提高了2.8%。","next_sentence":"结果表明，多视图集成能够提升模型在复杂用户场景下的识别能力。"},"citation_metadata":{"reference_id":"REF44","citation_marker":"[44]","authors":["Lyu et al."],"work_name":"DCGNN","year":2022},"intent":"用于结果比较","intent_code":"result_comparison","evidence_phrase":"与Lyu等人[44]提出的DCGNN相比，本文方法的F1值提高了2.8%","source_position":{"page_number":56,"source_section":"4.4 实验结果与分析"},"confidence":0.98,"matched_training_examples":[{"sample_id":"TRAIN_COMPARE_001","intent_label":"用于结果比较","similarity":0.97}]},{"citation_id":"CIT_INT_006","citation_markers":["[43]"],"citation_sentence":"本文模型在准确率和召回率上均优于BotBuster[43]，说明多教师蒸馏能够有效保持复杂模型的检测性能。","context":{"previous_sentence":"进一步比较不同方法在资源受限条件下的性能表现。","current_sentence":"本文模型在准确率和召回率上均优于BotBuster[43]，说明多教师蒸馏能够有效保持复杂模型的检测性能。","next_sentence":"同时，学生模型的参数规模和推理时间均得到明显降低。"},"citation_metadata":{"reference_id":"REF43","citation_marker":"[43]","authors":["Carley et al."],"work_name":"BotBuster","year":2023},"intent":"用于结果比较","intent_code":"result_comparison","evidence_phrase":"在准确率和召回率上均优于BotBuster[43]","source_position":{"page_number":58,"source_section":"4.4 实验结果与分析"},"confidence":0.97,"matched_training_examples":[{"sample_id":"TRAIN_COMPARE_002","intent_label":"用于结果比较","similarity":0.96}]}],"citation_intent_statistics":{"citation_count":4,"background_introduction_count":0,"method_introduction_count":2,"result_comparison_count":2,"intent_distribution":[{"intent":"用于背景介绍","count":0,"percentage":0.0},{"intent":"用于引入研究方法","count":2,"percentage":50.0},{"intent":"用于结果比较","count":2,"percentage":50.0}],"average_confidence":0.975},"training_set_summary":{"sample_count":6,"preprocessing_status":"completed","class_distribution":[{"intent":"用于背景介绍","count":2},{"intent":"用于引入研究方法","count":2},{"intent":"用于结果比较","count":2}]}},"meta":{"analysis_settings":{"language":"zh","citation_extraction_mode":"auto_extract","context_window":1,"parse_reference_metadata":true,"minimum_confidence":0.75,"return_context":true,"return_position":true,"return_citation_metadata":true,"return_training_evidence":true},"training_set_used":true,"training_set_sample_count":6,"request_id":"req_citation_intent_comparison_txt_202607210001","elapsed_ms":1386}}}]},
      "definition-detect": {
        group: "概念定义句识别工具", title: "概念定义句识别工具",
        description: "识别包含概念定义表述的句子，并抽取被定义的核心概念词，形成“概念—定义”结构化映射。",
        features: "定义句二分类、定义模式识别、概念词抽取、映射关系输出",
        scenarios: "领域术语库建设、知识图谱本体构建、科技文献概念梳理",
        endpoint: "/api/v1/definition",
        params: [["text","string",true,"科技文献全文片段"],["domain","string",false,"可选领域标签"],["return_mapping","boolean",false,"是否返回概念定义映射"],["return_position","boolean",false,"是否返回文本位置"]],
        payload: { text: "多模态学习是指联合建模两种及以上模态信息的机器学习方法。", domain: "computer_science", return_mapping: true, return_position: true },
        response: { code: 200, message: "success", data: { definitions: [{ concept: "多模态学习", definition: "联合建模两种及以上模态信息的机器学习方法", confidence: 0.98 }] } }
      },
      "general-ner": {
        group: "命名实体识别工具", title: "中英文通用领域命名实体识别",
        description: "识别中英文科技文本中的人名、地名、机构名和事件等通用实体，并返回实体位置与上下文。",
        features: "中英文混合识别、通用实体分类、实体位置标注、统一编码",
        scenarios: "文献元数据补全、机构与人物画像、跨语言实体检索",
        endpoint: "/api/v1/ner/general",
        params: [["text","string",true,"中英文科技文献文本"],["language","string",false,"zh/en/auto"],["entity_types","array",false,"需识别的实体类型"],["normalize","boolean",false,"是否进行实体标准化"]],
        payload: { text: "燕山大学与University of Cambridge开展联合研究。", language: "auto", entity_types: ["PERSON","ORG","LOC","EVENT"], normalize: true },
        response: { code: 200, message: "success", data: { entities: [{ text: "燕山大学", type: "ORG", start: 0, end: 4 },{ text: "University of Cambridge", type: "ORG", start: 5, end: 28 }] } }
      },
      "research-ner": {
        group: "命名实体识别工具", title: "中英文通用科研实体识别",
        description: "识别科研方法、数据资料、仪器设备、理论原理和研究问题等通用科研实体。",
        features: "科研要素识别、BIO 序列标注、跨领域适配、标准词表映射",
        scenarios: "科研知识抽取、文献要素标引、科技知识图谱构建",
        endpoint: "/api/v1/ner/research",
        params: [["text","string",true,"论文摘要或技术报告文本"],["language","string",false,"zh/en/auto"],["entity_types","array",false,"科研实体类别"],["return_context","boolean",false,"是否返回上下文"]],
        payload: { text: "本文采用Transformer模型，并在ETTh1数据集上进行实验。", language: "zh", entity_types: ["METHOD","DATASET","DEVICE","THEORY"], return_context: true },
        response: { code: 200, message: "success", data: { entities: [{ text: "Transformer模型", type: "METHOD" },{ text: "ETTh1数据集", type: "DATASET" }] } }
      },
      "domain-ner": {
        group: "命名实体识别工具", title: "专业领域科研实体识别",
        description: "面向医学、化工、物理等领域，识别疾病、药物、化合物、理论、现象与规律等专业实体。",
        features: "领域模型适配、专业本体映射、细粒度实体分类、知识库 ID 对齐",
        scenarios: "医学知识图谱、化工知识抽取、物理学术语识别",
        endpoint: "/api/v1/ner/domain",
        params: [["text","string",true,"专业领域科技文本"],["domain","string",true,"medicine/chemistry/physics"],["ontology","string",false,"本体名称"],["return_kb_id","boolean",false,"是否返回知识库 ID"]],
        payload: { text: "阿司匹林可用于缓解轻度疼痛并抑制血小板聚集。", domain: "medicine", ontology: "medical_ontology", return_kb_id: true },
        response: { code: 200, message: "success", data: { entities: [{ text: "阿司匹林", type: "DRUG", kb_id: "MESH:D001241" },{ text: "疼痛", type: "DISEASE_OR_SYMPTOM" }] } }
      },
      "relation-extract": {
        group: "命名实体识别工具", title: "实体关系识别",
        description: "在实体识别结果基础上，抽取实体对之间的语义关系，并输出可用于知识图谱的关系三元组。",
        features: "开放关系抽取、依存句法分析、实体对配对、关系三元组输出",
        scenarios: "知识图谱构建、科研关系网络分析、跨领域知识融合",
        endpoint: "/api/v1/relation",
        params: [["text","string",true,"原始句子或文本片段"],["entities","array",false,"预识别实体列表"],["domain","string",false,"领域标签"],["return_evidence","boolean",false,"是否返回证据片段"]],
        payload: { text: "阿司匹林能够抑制血小板聚集。", entities: [{ text: "阿司匹林", type: "DRUG" },{ text: "血小板聚集", type: "BIOLOGICAL_PROCESS" }], return_evidence: true },
        response: { code: 200, message: "success", data: { triples: [{ subject: "阿司匹林", relation: "抑制", object: "血小板聚集", confidence: 0.96 }] } }
      },
      "deep-cluster": {
        group: "深度聚类工具", title: "深度聚类工具",
        description: "基于句子级语义向量和文本相似度，将多篇科技文献自动聚合为若干主题类簇。",
        features: "批量文本处理、语义向量编码、多算法聚类、类簇统计分析",
        scenarios: "主题发现、研究热点分析、领域趋势挖掘",
        endpoint: "/api/v1/cluster/deep",
        params: [["documents","array",true,"多篇科技文献及其元数据"],["algorithm","string",false,"kmeans/hdbscan/hierarchical"],["cluster_count","integer",false,"指定类簇数量"],["language","string",false,"zh/en/auto"]],
        payload: { documents: [{ id: "doc_001", title: "时序预测研究", abstract: "……" },{ id: "doc_002", title: "异常检测研究", abstract: "……" }], algorithm: "hdbscan", cluster_count: 6, language: "zh" },
        response: { code: 200, message: "success", data: { clusters: [{ cluster_id: 1, size: 38, representative_terms: ["时间序列","预测","Transformer"] },{ cluster_id: 2, size: 24, representative_terms: ["异常检测","联邦学习"] }] } }
      },
      "cluster-label": {
        group: "聚类标签生成工具", title: "聚类标签生成工具",
        description: "根据深度聚类输出的类簇内容，生成简短、具有概括性和区分度的主题标签。",
        features: "词频与短语组合、共现模式分析、候选标签排序、差异化优化",
        scenarios: "聚类结果解释、科研主题标注、热点可视化展示",
        endpoint: "/api/v1/deep-cluster/tasks/{task_id}/labels",
        params: [["已完成聚类任务","resource",true,"从技术路线或应用场景任务列表中选择；任务资源由系统内部映射"]],
        payload: {},
        response: { code: 200, message: "success", data: { labels: [{ cluster_id: 1, label: "多变量时间序列预测", confidence: 0.94, alternatives: ["时序建模","Transformer预测"] }] } }
      },
      "structured-review": {
        group: "结构化自动综述工具", title: "结构化自动综述工具",
        description: "将文献集组织为“研究问题—研究方法—研究进展”三层树形结构，并支持从综述节点反向定位原始文献证据。",
        features: "研究问题聚合、方法归纳、进展总结、三层树形展示、溯源询证",
        scenarios: "领域综述编写、技术趋势分析、科研证据检索",
        endpoint: "/api/v1/review/structured",
        params: [["documents","array",true,"科技文献集"],["topic","string",false,"研究主题或关键词"],["language","string",false,"zh/en/auto"],["enable_traceability","boolean",false,"是否启用证据溯源"]],
        payload: { topic: "多变量时间序列分析", documents: [{ id: "doc_001", abstract: "……" },{ id: "doc_002", abstract: "……" }], language: "zh", enable_traceability: true },
        response: { code: 200, message: "success", data: { tree: [{ research_question: "如何建模跨变量依赖？", methods: [{ method: "图神经网络", progresses: [{ summary: "通过动态邻接建模提升预测性能", source_ids: ["doc_001"] }] }] }], traceability: true } }
      }
    }

const param = (name, type, required, description) => [name, type, required, description]
export const requirements = {
    "zh-abstract-move": {
      params: [
        param("text", "string", "conditional", "单文本模式：中文科技文献摘要原文"),
        param("texts", "object[]", "conditional", "批量文本模式：多篇中文摘要"),
        param("file", "file", "conditional", "单文件模式：PDF、DOCX 或 TXT 文献文件"),
        param("files", "file[]", "conditional", "批量文件模式：多个 PDF、DOCX 或 TXT 文献文件")
      ],
      automatic: "系统固定按中文摘要处理，并自动完成摘要定位、分句、五类语步识别、同类语步聚合、置信度计算与批量调度。"
    },
    "en-abstract-move": {
      params: [
        param("text", "string", "conditional", "单文本模式：英文科技文献摘要原文"),
        param("texts", "object[]", "conditional", "批量文本模式：多篇英文摘要"),
        param("file", "file", "conditional", "单文件模式：PDF、DOCX 或 TXT 文献文件"),
        param("files", "file[]", "conditional", "批量文件模式：多个 PDF、DOCX 或 TXT 文献文件")
      ],
      automatic: "系统固定按英文摘要处理，并自动完成摘要定位、分句、五类语步识别、同类语步聚合、置信度计算与批量调度。"
    },
    "fund-move": {
      params: [
        param("file", "file", "conditional", "单文件模式：中文基金项目申请书"),
        param("files", "file[]", "conditional", "批量文件模式：多份中文基金项目申请书")
      ],
      automatic: "系统自动解析基金申请书章节，识别固定五类语步，聚合同类内容，并返回来源章节。"
    },
    "zh-classify": {
      params: [
        param("text", "string", "conditional", "单文本模式：直接输入中文科技文献文本"),
        param("texts", "object[]", "conditional", "批量文本模式：每条包含 id 和 text，最多20条"),
        param("file", "file", "conditional", "单文件模式：系统自动提取文献文本与元数据"),
        param("files", "file[]", "conditional", "批量文件模式：系统逐篇提取文献文本与元数据")
      ],
      automatic: "系统自动完成语言校验、中图分类候选召回、路径一致性校验、跨学科判断、置信度计算和批量任务调度。"
    },
    "en-classify": {
      params: [
        param("text", "string", "conditional", "单文本模式：直接输入英文科技文献文本"),
        param("texts", "object[]", "conditional", "批量文本模式：每条包含 id 和 text，最多20条"),
        param("file", "file", "conditional", "单文件模式：系统自动提取英文文献文本与元数据"),
        param("files", "file[]", "conditional", "批量文件模式：系统逐篇提取英文文献文本与元数据")
      ],
      automatic: "系统自动完成语言检测、跨语言中图映射、候选召回、路径校验、跨学科判断和置信度计算。"
    },
    "domain-classify": {
      params: [
        param("domain", "string", "required", "用户选择需要细分的专业领域"),
        param("text", "string", "conditional", "单文本模式：直接输入科技文献文本"),
        param("texts", "object[]", "conditional", "批量文本模式：每条包含 id 和 text，最多20条"),
        param("file", "file", "conditional", "单文件模式：系统自动提取文献文本与元数据"),
        param("files", "file[]", "conditional", "批量文件模式：系统逐篇提取文献文本与元数据")
      ],
      keep: ["domain"],
      automatic: "用户只选择目标专业领域；系统自动完成文献文本解析、领域匹配校验、层级分类、置信度计算和批量调度。"
    },
    "zh-keyword": {
      params: [
        param("abstract", "string", "conditional", "单文本模式：中文科技文献摘要"),
        param("texts", "object[]", "conditional", "批量文本模式：多篇中文摘要"),
        param("file", "file", "conditional", "单文件模式：系统自动定位摘要"),
        param("files", "file[]", "conditional", "批量文件模式：系统逐篇定位摘要")
      ],
      automatic: "系统自动识别研究领域、调用领域术语资源，并根据置信度自适应输出 5—8 个关键词，同时完成术语边界、规范化与顺序处理。"
    },
    "en-keyword": {
      params: [
        param("abstract", "string", "conditional", "单文本模式：英文科技文献摘要"),
        param("texts", "object[]", "conditional", "批量文本模式：多篇英文摘要"),
        param("file", "file", "conditional", "单文件模式：系统自动定位英文摘要"),
        param("files", "file[]", "conditional", "批量文件模式：系统逐篇定位英文摘要")
      ],
      automatic: "系统自动识别研究领域、调用英文领域术语资源和标准术语映射规则，并按置信度自适应输出 5—8 个关键词。"
    },
    "rq-detect": {
      params: [
        param("file", "file", "conditional", "单文件模式：PDF、DOCX 或 TXT 科技文献全文"),
        param("files", "file[]", "conditional", "批量文件模式：多篇科技文献全文")
      ],
      automatic: "系统自动完成语言检测、全文解析、章节层级提取、重点章节定位、自动分句、显式与隐式研究问题识别、主子问题组织以及章节和页码溯源。"
    },
    "citation-sentiment": {
      params: [
        param("citation_sentence", "string", "conditional", "单文本模式：包含引文标记的引用句"),
        param("previous_context", "string", "optional", "单文本模式：引用句上文，可为空"),
        param("next_context", "string", "optional", "单文本模式：引用句下文，可为空"),
        param("citations", "object[]", "conditional", "批量文本模式：多条引用句及其上下文"),
        param("file", "file", "conditional", "单文件模式：包含正文和参考文献的科技文献"),
        param("files", "file[]", "conditional", "批量文件模式：多篇包含引文的科技文献")
      ],
      automatic: "系统自动检测文档语言，抽取引用句及上下文，解析参考文献元数据，匹配引文标记并识别支持、中立和有局限性三类情感。"
    },
    "citation-intent": {
      params: [
        param("citation_sentence", "string", "conditional", "单文本模式：包含引文标记的引用句"),
        param("previous_context", "string", "optional", "单文本模式：引用句上文，可为空"),
        param("next_context", "string", "optional", "单文本模式：引用句下文，可为空"),
        param("citations", "object[]", "conditional", "批量文本模式：多条引用句及其上下文"),
        param("file", "file", "conditional", "单文件模式：包含正文和参考文献的科技文献"),
        param("files", "file[]", "conditional", "批量文件模式：多篇包含引文的科技文献")
      ],
      automatic: "系统自动抽取引用句、上下文和引文元数据，并调用内部已训练的引用意图模型及版本化训练资源完成意图判定。"
    },
    "definition-detect": {
      params: [
        param("text", "string", "conditional", "单文本模式：科技文献全文片段"),
        param("texts", "object[]", "conditional", "批量文本模式：多篇科技文献片段"),
        param("file", "file", "conditional", "单文件模式：科技文献全文文件"),
        param("files", "file[]", "conditional", "批量文件模式：多个科技文献全文文件")
      ],
      automatic: "系统自动识别学科领域，完成章节和句子定位、概念边界识别、概念规范化、重复定义合并以及概念—定义映射。"
    },
    "general-ner": {
      params: [
        param("text", "string", "conditional", "单文本模式：中英文科技文本"),
        param("texts", "object[]", "conditional", "批量文本模式：多条中英文科技文本"),
        param("file", "file", "conditional", "单文件模式：科技文献文件"),
        param("files", "file[]", "conditional", "批量文件模式：多篇科技文献文件")
      ],
      automatic: "系统自动检测语言，识别人名、机构、地点、事件等全部通用实体，并完成实体规范化、别名合并和跨语言映射。"
    },
    "research-ner": {
      params: [
        param("text", "string", "conditional", "单文本模式：论文摘要或技术报告文本"),
        param("texts", "object[]", "conditional", "批量文本模式：多条科研文本"),
        param("file", "file", "conditional", "单文件模式：科技文献文件"),
        param("files", "file[]", "conditional", "批量文件模式：多篇科技文献文件")
      ],
      automatic: "系统自动检测语言与科研语境，识别方法、模型、数据集、设备、理论、指标和任务等科研实体，并返回上下文和来源位置。"
    },
    "domain-ner": {
      params: [
        param("text", "string", "conditional", "单文本模式：专业领域科技文本"),
        param("texts", "object[]", "conditional", "批量文本模式：多条专业科技文本"),
        param("file", "file", "conditional", "单文件模式：专业科技文献文件"),
        param("files", "file[]", "conditional", "批量文件模式：多篇专业科技文献文件")
      ],
      automatic: "系统根据文本自动识别专业领域，选择相应领域本体和知识库，完成细粒度实体识别、规范化及知识库 ID 对齐。"
    },
    "relation-extract": {
      params: [
        param("text", "string", "conditional", "普通模式：原始句子或科技文本"),
        param("texts", "object[]", "conditional", "普通批量模式：多条科技文本"),
        param("file", "file", "conditional", "普通文件模式：科技文献文件"),
        param("files", "file[]", "conditional", "普通批量文件模式：多篇科技文献"),
        param("upstream_entity_record_id", "string", "conditional", "上游结构化模式：前置实体识别历史记录编号"),
        param("upstream_dependency_record_id", "string", "conditional", "上游结构化模式：前置依存句法分析历史记录编号")
      ],
      automatic: "普通模式下系统自动识别实体、生成实体对、分析依存结构并抽取关系；上游结构化模式只选择前置历史记录，不要求手工填写实体列表。"
    },
    "deep-cluster": {
      params: [
        param("cluster_dimension", "string", "required", "technology 或 application_scenario，决定按技术路线或应用场景聚类"),
        param("documents", "object[]", "conditional", "多篇文本模式：每篇包含 id 和 text，可选 publication_year"),
        param("files", "file[]", "conditional", "多篇文件模式：系统自动解析文献 text 和发表时间"),
        param("algorithm", "string", "optional", "聚类算法：auto、hdbscan、kmeans 或 hierarchical，默认auto"),
        param("cluster_count", "integer", "conditional", "类簇数量；K-Means或层次聚类时可指定"),
        param("minimum_cluster_size", "integer", "optional", "最小类簇规模，默认2"),
        param("similarity_metric", "string", "optional", "相似度度量，默认cosine")
      ],
      keep: ["cluster_dimension", "algorithm", "cluster_count", "minimum_cluster_size", "similarity_metric"],
      automatic: "系统自动完成文本语义特征提取、向量编码、聚类质量统计、文献归属、二维投影和主题趋势计算；聚类算法及主要聚类参数由用户按需配置。"
    },
    "cluster-label": {
      params: [
        param("已完成聚类任务", "resource", "required", "先按技术路线或应用场景筛选，再从已完成任务列表中选择；任务编号由系统内部映射到接口路径")
      ],
      automatic: "系统从所选深度聚类任务读取类簇结果，并自动检测标签语言和类簇主题，自适应确定标签长度、候选标签数量和差异度阈值。"
    },
    "structured-review": {
      params: [
        param("documents", "object[]", "required", "用于生成综述的科技文献集合"),
        param("topic", "string", "optional", "可选：用户希望聚焦的研究主题；为空时系统自动归纳")
      ],
      keep: ["topic"],
      automatic: "系统自动检测语言、归纳主题、组织研究问题—研究方法—研究进展三层结构，并始终保留原始文献证据溯源。"
    }
  }

export const deepClusterDemoDocuments = [
    {
      id: "DOC001",
      title: "面向工业能耗预测的层次超图时间序列Transformer",
      publication_year: 2022,
      text: "针对工业能耗序列中跨变量耦合与长期依赖难以建模的问题，本文构建层次超图时间序列Transformer，通过多尺度分块、自注意力和超边聚合学习设备变量之间的动态关系，用于工业园区负荷预测与能源调度。"
    },
    {
      id: "DOC002",
      title: "面向跨机构工业物联网的联邦时间序列异常检测",
      publication_year: 2023,
      text: "本文提出资源感知的联邦时间序列异常检测框架，利用多分辨率变换、频域分块和参数高效大模型适配实现跨机构协同训练，在不共享原始数据的条件下识别工业物联网设备异常。"
    },
    {
      id: "DOC003",
      title: "融合多尺度特征与难样本重加权的工业表面缺陷检测",
      publication_year: 2022,
      text: "针对裂纹、划痕与孔洞尺度差异大且背景纹理复杂的问题，本文构建多尺度特征金字塔和局部注意力增强网络，并使用难样本重加权提升微小缺陷识别能力，服务于智能制造质量检测。"
    },
    {
      id: "DOC004",
      title: "多源遥感协同编码的城市地表覆盖精细分类",
      publication_year: 2024,
      text: "本文联合高分辨率光学影像、合成孔径雷达和地形辅助信息，通过跨模态对齐与区域上下文建模完成建筑、道路、植被和水体分类，用于城市空间监测和土地利用调查。"
    },
    {
      id: "DOC005",
      title: "视觉语言模型解释可信度提升与反事实一致性验证",
      publication_year: 2025,
      text: "面向视觉语言模型解释幻觉问题，本文动态构建上下文干扰概念集合，执行文本图像双向解耦、反事实遮挡验证和多解释一致性校验，为医疗影像辅助分析等高风险场景输出可信解释热力图。"
    },
    {
      id: "DOC006",
      title: "基于科技知识图谱的专家合作关系推理",
      publication_year: 2023,
      text: "本文融合论文、专利、项目和机构数据构建科技专家知识图谱，利用路径分析、关系传递和图表示学习识别直接关系、间接关系与合作成果，为科技人才发现和科研合作推荐提供支持。"
    },
    {
      id: "DOC007",
      title: "面向疾病诊疗的生物医学知识图谱关系补全",
      publication_year: 2024,
      text: "本文通过实体标准化、关系抽取和图神经网络表示学习构建疾病、药物和症状知识图谱，并利用路径约束关系补全发现潜在药物适应证，服务于临床知识检索和辅助诊疗。"
    },
    {
      id: "DOC008",
      title: "碳包覆多孔硅复合负极的结构设计与循环性能优化",
      publication_year: 2023,
      text: "针对硅基负极充放电过程中的体积膨胀问题，本文设计碳包覆多孔硅复合结构，通过纳米孔隙缓冲和导电碳网络改善电子传输，为高能量密度锂离子电池提供材料设计方案。"
    },
    {
      id: "DOC009",
      title: "面向碳捕集的多孔吸附材料构效关系分析",
      publication_year: 2025,
      text: "本文结合分子模拟、孔结构表征和机器学习回归分析多孔吸附材料的构效关系，筛选具有高二氧化碳选择性和循环稳定性的候选材料，用于工业烟气碳捕集与环境治理。"
    },
    {
      id: "DOC010",
      title: "大模型增强的跨语言专利语义检索与技术路线发现",
      publication_year: 2025,
      text: "本文利用大语言模型生成专利技术摘要和检索查询，通过跨语言向量对齐、分类路径约束和检索结果重排序识别相似技术方案，为专利查新、技术路线分析和科技情报服务提供支持。"
    },
    {
      id: "DOC011",
      title: "图神经网络驱动的催化剂性能预测与候选筛选",
      publication_year: 2026,
      text: "本文将催化剂晶体结构表示为原子图，通过消息传递网络学习局部配位环境和电子结构特征，预测催化活性与稳定性并筛选候选材料，用于绿色化工和能源催化材料研发。"
    },
    {
      id: "DOC012",
      title: "面向科技文献的研究问题识别与结构化综述生成",
      publication_year: 2026,
      text: "本文从科技文献中识别研究空白、技术难点、主问题和子问题，并结合语步识别、关键词抽取与大模型审核构建研究问题方法进展三层结构，为科研情报分析和自动综述生成提供能力。"
    }
  ]

export const deepClusterRuntime = {
  "group": "深度聚类工具",
  "title": "深度聚类工具",
  "description": "将用户上传的多篇科技文献按句子切分并进行语义特征编码与相似度计算，可从技术路线或应用场景两个维度自动聚合形成类簇，输出类簇结果、类簇特征统计和主题趋势分析。",
  "features": "批量文献输入、句子级语义特征、技术路线聚类、应用场景聚类、类簇质量评估、文献归属溯源、二维语义投影、主题趋势分析",
  "scenarios": "技术路线发现、应用场景归类、科研主题发现、研究热点分析、文献知识结构化、领域趋势挖掘",
  "endpoint": "/api/v1/cluster/deep/texts",
  "params": [
    [
      "input_type",
      "string",
      "required",
      "输入方式，取值为 texts 或 files"
    ],
    [
      "documents",
      "object[]",
      "conditional",
      "input_type=texts 时必填；每篇包含 id、text，可选 publication_year，建议至少4篇"
    ],
    [
      "files",
      "file[]",
      "conditional",
      "input_type=files 时必填；支持PDF、DOCX、TXT，系统自动解析文献 text 和发表时间"
    ],
    [
      "cluster_dimension",
      "string",
      "required",
      "聚类维度：technology 技术路线或 application_scenario 应用场景"
    ],
    [
      "algorithm",
      "string",
      "optional",
      "聚类算法：auto、hdbscan、kmeans 或 hierarchical，默认auto"
    ],
    [
      "cluster_count",
      "integer",
      "conditional",
      "类簇数量；K-Means或层次聚类时可指定，auto/HDBSCAN时可为空"
    ],
    [
      "minimum_cluster_size",
      "integer",
      "optional",
      "最小类簇规模，默认2"
    ],
    [
      "similarity_metric",
      "string",
      "optional",
      "相似度度量，默认cosine"
    ]
  ],
  "payload": {
    "input_type": "texts",
    "documents": [
      {
        "id": "DOC001",
        "text": "针对工业能耗序列中跨变量耦合与长期依赖难以建模的问题，本文构建层次超图时间序列Transformer，通过多尺度分块、自注意力和超边聚合学习设备变量之间的动态关系，用于工业园区负荷预测与能源调度。",
        "publication_year": 2022
      },
      {
        "id": "DOC002",
        "text": "本文提出资源感知的联邦时间序列异常检测框架，利用多分辨率变换、频域分块和参数高效大模型适配实现跨机构协同训练，在不共享原始数据的条件下识别工业物联网设备异常。",
        "publication_year": 2023
      },
      {
        "id": "DOC003",
        "text": "针对裂纹、划痕与孔洞尺度差异大且背景纹理复杂的问题，本文构建多尺度特征金字塔和局部注意力增强网络，并使用难样本重加权提升微小缺陷识别能力，服务于智能制造质量检测。",
        "publication_year": 2022
      },
      {
        "id": "DOC004",
        "text": "本文联合高分辨率光学影像、合成孔径雷达和地形辅助信息，通过跨模态对齐与区域上下文建模完成建筑、道路、植被和水体分类，用于城市空间监测和土地利用调查。",
        "publication_year": 2024
      },
      {
        "id": "DOC005",
        "text": "面向视觉语言模型解释幻觉问题，本文动态构建上下文干扰概念集合，执行文本图像双向解耦、反事实遮挡验证和多解释一致性校验，为医疗影像辅助分析等高风险场景输出可信解释热力图。",
        "publication_year": 2025
      },
      {
        "id": "DOC006",
        "text": "本文融合论文、专利、项目和机构数据构建科技专家知识图谱，利用路径分析、关系传递和图表示学习识别直接关系、间接关系与合作成果，为科技人才发现和科研合作推荐提供支持。",
        "publication_year": 2023
      },
      {
        "id": "DOC007",
        "text": "本文通过实体标准化、关系抽取和图神经网络表示学习构建疾病、药物和症状知识图谱，并利用路径约束关系补全发现潜在药物适应证，服务于临床知识检索和辅助诊疗。",
        "publication_year": 2024
      },
      {
        "id": "DOC008",
        "text": "针对硅基负极充放电过程中的体积膨胀问题，本文设计碳包覆多孔硅复合结构，通过纳米孔隙缓冲和导电碳网络改善电子传输，为高能量密度锂离子电池提供材料设计方案。",
        "publication_year": 2023
      },
      {
        "id": "DOC009",
        "text": "本文结合分子模拟、孔结构表征和机器学习回归分析多孔吸附材料的构效关系，筛选具有高二氧化碳选择性和循环稳定性的候选材料，用于工业烟气碳捕集与环境治理。",
        "publication_year": 2025
      },
      {
        "id": "DOC010",
        "text": "本文利用大语言模型生成专利技术摘要和检索查询，通过跨语言向量对齐、分类路径约束和检索结果重排序识别相似技术方案，为专利查新、技术路线分析和科技情报服务提供支持。",
        "publication_year": 2025
      },
      {
        "id": "DOC011",
        "text": "本文将催化剂晶体结构表示为原子图，通过消息传递网络学习局部配位环境和电子结构特征，预测催化活性与稳定性并筛选候选材料，用于绿色化工和能源催化材料研发。",
        "publication_year": 2026
      },
      {
        "id": "DOC012",
        "text": "本文从科技文献中识别研究空白、技术难点、主问题和子问题，并结合语步识别、关键词抽取与大模型审核构建研究问题方法进展三层结构，为科研情报分析和自动综述生成提供能力。",
        "publication_year": 2026
      }
    ],
    "cluster_dimension": "technology",
    "algorithm": "auto",
    "cluster_count": null,
    "minimum_cluster_size": 2,
    "similarity_metric": "cosine"
  },
  "response": {
    "code": 0,
    "message": "clustering_completed",
    "data": {
      "tool": "深度聚类工具",
      "input_type": "texts",
      "cluster_dimension": "technology",
      "cluster_dimension_name": "技术路线",
      "input_summary": {
        "document_count": 12,
        "parsed_sentence_count": 72,
        "file_names": [],
        "extracted_fields": [
          "title",
          "abstract",
          "keywords",
          "publication_year"
        ],
        "year_range": [
          2022,
          2026
        ]
      },
      "clustering_quality": {
        "cluster_count": 5,
        "noise_document_count": 0,
        "silhouette_score": 0.825,
        "average_intra_cluster_similarity": 0.894,
        "average_inter_cluster_separation": 0.856
      },
      "clusters": [
        {
          "cluster_id": "TECH-01",
          "size": 2,
          "ratio": 0.1667,
          "representative_terms": [
            "时间序列",
            "多尺度分块",
            "联邦学习",
            "异常检测"
          ],
          "representative_sentences": [
            "通过多尺度分块与关系建模学习跨变量动态依赖。"
          ],
          "feature_statistics": {
            "intra_cluster_similarity": 0.91,
            "inter_cluster_separation": 0.86,
            "semantic_density": 0.89,
            "average_sentence_count": 6
          },
          "representative_documents": [
            {
              "document_id": "DOC001",
              "title": "面向工业能耗预测的层次超图时间序列Transformer",
              "publication_year": 2022
            },
            {
              "document_id": "DOC002",
              "title": "面向跨机构工业物联网的联邦时间序列异常检测",
              "publication_year": 2023
            }
          ]
        },
        {
          "cluster_id": "TECH-02",
          "size": 3,
          "ratio": 0.25,
          "representative_terms": [
            "多尺度特征",
            "跨模态对齐",
            "视觉语言模型",
            "上下文建模"
          ],
          "representative_sentences": [
            "利用多尺度视觉表示和跨模态语义对齐增强复杂场景感知。"
          ],
          "feature_statistics": {
            "intra_cluster_similarity": 0.88,
            "inter_cluster_separation": 0.82,
            "semantic_density": 0.85,
            "average_sentence_count": 6
          },
          "representative_documents": [
            {
              "document_id": "DOC003",
              "title": "融合多尺度特征与难样本重加权的工业表面缺陷检测",
              "publication_year": 2022
            },
            {
              "document_id": "DOC004",
              "title": "多源遥感协同编码的城市地表覆盖精细分类",
              "publication_year": 2024
            },
            {
              "document_id": "DOC005",
              "title": "视觉语言模型解释可信度提升与反事实一致性验证",
              "publication_year": 2025
            }
          ]
        },
        {
          "cluster_id": "TECH-03",
          "size": 2,
          "ratio": 0.1667,
          "representative_terms": [
            "知识图谱",
            "关系抽取",
            "路径推理",
            "图表示学习"
          ],
          "representative_sentences": [
            "通过实体关系建模和路径约束完成知识关联与关系补全。"
          ],
          "feature_statistics": {
            "intra_cluster_similarity": 0.93,
            "inter_cluster_separation": 0.89,
            "semantic_density": 0.91,
            "average_sentence_count": 6
          },
          "representative_documents": [
            {
              "document_id": "DOC006",
              "title": "基于科技知识图谱的专家合作关系推理",
              "publication_year": 2023
            },
            {
              "document_id": "DOC007",
              "title": "面向疾病诊疗的生物医学知识图谱关系补全",
              "publication_year": 2024
            }
          ]
        },
        {
          "cluster_id": "TECH-04",
          "size": 3,
          "ratio": 0.25,
          "representative_terms": [
            "材料结构",
            "构效关系",
            "性能预测",
            "候选筛选"
          ],
          "representative_sentences": [
            "结合结构表征与机器学习建立材料构效关系并筛选候选体系。"
          ],
          "feature_statistics": {
            "intra_cluster_similarity": 0.87,
            "inter_cluster_separation": 0.84,
            "semantic_density": 0.85,
            "average_sentence_count": 6
          },
          "representative_documents": [
            {
              "document_id": "DOC008",
              "title": "碳包覆多孔硅复合负极的结构设计与循环性能优化",
              "publication_year": 2023
            },
            {
              "document_id": "DOC009",
              "title": "面向碳捕集的多孔吸附材料构效关系分析",
              "publication_year": 2025
            },
            {
              "document_id": "DOC011",
              "title": "图神经网络驱动的催化剂性能预测与候选筛选",
              "publication_year": 2026
            }
          ]
        },
        {
          "cluster_id": "TECH-05",
          "size": 2,
          "ratio": 0.1667,
          "representative_terms": [
            "大语言模型",
            "语义检索",
            "研究问题识别",
            "结构化生成"
          ],
          "representative_sentences": [
            "利用大模型完成科技文本语义理解、知识组织和结构化生成。"
          ],
          "feature_statistics": {
            "intra_cluster_similarity": 0.9,
            "inter_cluster_separation": 0.87,
            "semantic_density": 0.89,
            "average_sentence_count": 6
          },
          "representative_documents": [
            {
              "document_id": "DOC010",
              "title": "大模型增强的跨语言专利语义检索与技术路线发现",
              "publication_year": 2025
            },
            {
              "document_id": "DOC012",
              "title": "面向科技文献的研究问题识别与结构化综述生成",
              "publication_year": 2026
            }
          ]
        }
      ],
      "document_assignments": [
        {
          "document_id": "DOC001",
          "title": "面向工业能耗预测的层次超图时间序列Transformer",
          "publication_year": 2022,
          "cluster_id": "TECH-01",
          "similarity_to_centroid": 0.82,
          "key_evidence": "方法结构、算法机制与数据处理流程相近"
        },
        {
          "document_id": "DOC002",
          "title": "面向跨机构工业物联网的联邦时间序列异常检测",
          "publication_year": 2023,
          "cluster_id": "TECH-01",
          "similarity_to_centroid": 0.838,
          "key_evidence": "方法结构、算法机制与数据处理流程相近"
        },
        {
          "document_id": "DOC003",
          "title": "融合多尺度特征与难样本重加权的工业表面缺陷检测",
          "publication_year": 2022,
          "cluster_id": "TECH-02",
          "similarity_to_centroid": 0.856,
          "key_evidence": "方法结构、算法机制与数据处理流程相近"
        },
        {
          "document_id": "DOC004",
          "title": "多源遥感协同编码的城市地表覆盖精细分类",
          "publication_year": 2024,
          "cluster_id": "TECH-02",
          "similarity_to_centroid": 0.874,
          "key_evidence": "方法结构、算法机制与数据处理流程相近"
        },
        {
          "document_id": "DOC005",
          "title": "视觉语言模型解释可信度提升与反事实一致性验证",
          "publication_year": 2025,
          "cluster_id": "TECH-02",
          "similarity_to_centroid": 0.892,
          "key_evidence": "方法结构、算法机制与数据处理流程相近"
        },
        {
          "document_id": "DOC006",
          "title": "基于科技知识图谱的专家合作关系推理",
          "publication_year": 2023,
          "cluster_id": "TECH-03",
          "similarity_to_centroid": 0.91,
          "key_evidence": "方法结构、算法机制与数据处理流程相近"
        },
        {
          "document_id": "DOC007",
          "title": "面向疾病诊疗的生物医学知识图谱关系补全",
          "publication_year": 2024,
          "cluster_id": "TECH-03",
          "similarity_to_centroid": 0.928,
          "key_evidence": "方法结构、算法机制与数据处理流程相近"
        },
        {
          "document_id": "DOC008",
          "title": "碳包覆多孔硅复合负极的结构设计与循环性能优化",
          "publication_year": 2023,
          "cluster_id": "TECH-04",
          "similarity_to_centroid": 0.946,
          "key_evidence": "方法结构、算法机制与数据处理流程相近"
        },
        {
          "document_id": "DOC009",
          "title": "面向碳捕集的多孔吸附材料构效关系分析",
          "publication_year": 2025,
          "cluster_id": "TECH-04",
          "similarity_to_centroid": 0.82,
          "key_evidence": "方法结构、算法机制与数据处理流程相近"
        },
        {
          "document_id": "DOC010",
          "title": "大模型增强的跨语言专利语义检索与技术路线发现",
          "publication_year": 2025,
          "cluster_id": "TECH-05",
          "similarity_to_centroid": 0.838,
          "key_evidence": "方法结构、算法机制与数据处理流程相近"
        },
        {
          "document_id": "DOC011",
          "title": "图神经网络驱动的催化剂性能预测与候选筛选",
          "publication_year": 2026,
          "cluster_id": "TECH-04",
          "similarity_to_centroid": 0.856,
          "key_evidence": "方法结构、算法机制与数据处理流程相近"
        },
        {
          "document_id": "DOC012",
          "title": "面向科技文献的研究问题识别与结构化综述生成",
          "publication_year": 2026,
          "cluster_id": "TECH-05",
          "similarity_to_centroid": 0.874,
          "key_evidence": "方法结构、算法机制与数据处理流程相近"
        }
      ],
      "semantic_projection": [
        {
          "document_id": "DOC001",
          "title": "面向工业能耗预测的层次超图时间序列Transformer",
          "cluster_id": "TECH-01",
          "x": 13,
          "y": 22
        },
        {
          "document_id": "DOC002",
          "title": "面向跨机构工业物联网的联邦时间序列异常检测",
          "cluster_id": "TECH-01",
          "x": 22,
          "y": 27
        },
        {
          "document_id": "DOC003",
          "title": "融合多尺度特征与难样本重加权的工业表面缺陷检测",
          "cluster_id": "TECH-02",
          "x": 65,
          "y": 19
        },
        {
          "document_id": "DOC004",
          "title": "多源遥感协同编码的城市地表覆盖精细分类",
          "cluster_id": "TECH-02",
          "x": 74,
          "y": 24
        },
        {
          "document_id": "DOC005",
          "title": "视觉语言模型解释可信度提升与反事实一致性验证",
          "cluster_id": "TECH-02",
          "x": 68,
          "y": 27
        },
        {
          "document_id": "DOC006",
          "title": "基于科技知识图谱的专家合作关系推理",
          "cluster_id": "TECH-03",
          "x": 45,
          "y": 45
        },
        {
          "document_id": "DOC007",
          "title": "面向疾病诊疗的生物医学知识图谱关系补全",
          "cluster_id": "TECH-03",
          "x": 54,
          "y": 50
        },
        {
          "document_id": "DOC008",
          "title": "碳包覆多孔硅复合负极的结构设计与循环性能优化",
          "cluster_id": "TECH-04",
          "x": 17,
          "y": 72
        },
        {
          "document_id": "DOC009",
          "title": "面向碳捕集的多孔吸附材料构效关系分析",
          "cluster_id": "TECH-04",
          "x": 26,
          "y": 77
        },
        {
          "document_id": "DOC011",
          "title": "图神经网络驱动的催化剂性能预测与候选筛选",
          "cluster_id": "TECH-04",
          "x": 20,
          "y": 80
        },
        {
          "document_id": "DOC010",
          "title": "大模型增强的跨语言专利语义检索与技术路线发现",
          "cluster_id": "TECH-05",
          "x": 71,
          "y": 69
        },
        {
          "document_id": "DOC012",
          "title": "面向科技文献的研究问题识别与结构化综述生成",
          "cluster_id": "TECH-05",
          "x": 80,
          "y": 74
        }
      ],
      "theme_trend_analysis": {
        "years": [
          2022,
          2023,
          2024,
          2025,
          2026
        ],
        "series": [
          {
            "cluster_id": "TECH-01",
            "representative_terms": [
              "时间序列",
              "多尺度分块",
              "联邦学习",
              "异常检测"
            ],
            "yearly_counts": [
              1,
              1,
              0,
              0,
              0
            ],
            "trend_score": 0.58
          },
          {
            "cluster_id": "TECH-02",
            "representative_terms": [
              "多尺度特征",
              "跨模态对齐",
              "视觉语言模型",
              "上下文建模"
            ],
            "yearly_counts": [
              1,
              0,
              1,
              1,
              0
            ],
            "trend_score": 0.69
          },
          {
            "cluster_id": "TECH-03",
            "representative_terms": [
              "知识图谱",
              "关系抽取",
              "路径推理",
              "图表示学习"
            ],
            "yearly_counts": [
              0,
              1,
              1,
              0,
              0
            ],
            "trend_score": 0.58
          },
          {
            "cluster_id": "TECH-04",
            "representative_terms": [
              "材料结构",
              "构效关系",
              "性能预测",
              "候选筛选"
            ],
            "yearly_counts": [
              0,
              1,
              0,
              1,
              1
            ],
            "trend_score": 0.69
          },
          {
            "cluster_id": "TECH-05",
            "representative_terms": [
              "大语言模型",
              "语义检索",
              "研究问题识别",
              "结构化生成"
            ],
            "yearly_counts": [
              0,
              0,
              0,
              1,
              1
            ],
            "trend_score": 0.58
          }
        ],
        "rising_cluster_id": "TECH-04",
        "emerging_cluster_id": "TECH-05",
        "stable_cluster_id": "TECH-02",
        "summary": "技术类簇由传统视觉与时间序列建模相关短语，逐步扩展到大模型语义理解、图推理和跨模态可信分析相关短语。"
      },
      "training_evaluation": {
        "dataset_version": "MED-CLUSTER-DEMO-2026.07",
        "evidence_status": "prototype_demo_configuration",
        "notice": "以下规模和指标仅用于静态原型展示，不代表真实训练数据、模型评测结论或生产性能。接入项目数据后应替换为可审计的数据版本、划分策略和评测报告。",
        "datasets": [
          {
            "name": "医学文献训练集",
            "version": "MED-TRAIN-DEMO-V1",
            "size": 12000,
            "unit": "篇",
            "purpose": "句子编码与聚类模型训练",
            "status": "演示配置"
          },
          {
            "name": "人工标注样本",
            "version": "MED-ANNOTATED-DEMO-V1",
            "size": 3200,
            "unit": "篇",
            "purpose": "类簇归属与主题一致性监督",
            "status": "演示配置"
          },
          {
            "name": "在线评测集",
            "version": "MED-ONLINE-EVAL-DEMO-V1",
            "size": 800,
            "unit": "篇",
            "purpose": "按时间顺序模拟在线评测",
            "status": "演示配置"
          },
          {
            "name": "随机评测集",
            "version": "MED-RANDOM-EVAL-DEMO-V1",
            "size": 800,
            "unit": "篇",
            "purpose": "随机抽样稳定性评测",
            "status": "演示配置"
          }
        ],
        "metrics": {
          "silhouette_score": 0.712,
          "normalized_mutual_information": 0.781,
          "adjusted_rand_index": 0.736,
          "expert_agreement": 0.846
        },
        "correction_loop": {
          "supported_operations": [
            "move_document",
            "merge_clusters",
            "split_cluster"
          ],
          "correction_count": 0,
          "update_status": "not_submitted",
          "incremental_version": "pending"
        }
      },
      "manual_correction": {
        "supported_operations": [
          "move_document",
          "merge_clusters",
          "split_cluster"
        ],
        "correction_count": 0,
        "update_status": "not_submitted",
        "incremental_version": "pending"
      }
    },
    "meta": {
      "feature_level": "sentence",
      "feature_source_strategy": "provided_title_abstract_keywords_publication_time",
      "sentence_weighting_strategy": "method_model_algorithm_pipeline_weighting",
      "algorithm": "auto_hdbscan_with_quality_selection",
      "similarity_metric": "cosine",
      "request_id": "req_deep_cluster_technology_1786704241360",
      "elapsed_ms": 1738,
      "prototype_demo": true,
      "prototype_data_notice": "以下规模和指标仅用于静态原型展示，不代表真实训练数据、模型评测结论或生产性能。接入项目数据后应替换为可审计的数据版本、划分策略和评测报告。",
      "supported_result_formats": [
        "json",
        "csv"
      ]
    }
  },
  "documentType": "deep-cluster",
  "languageCode": "zh",
  "languageName": "中文",
  "batchTextEndpoint": "/api/v1/cluster/deep/texts",
  "batchFileEndpoint": "/api/v1/cluster/deep/files",
  "inputModes": [
    "batch-text",
    "batch"
  ],
  "modeLabels": {
    "batch-text": "批量文本",
    "batch": "批量文件"
  },
  "supportsFileUpload": true,
  "supportsBatchUpload": true,
  "acceptedFiles": [
    ".pdf",
    ".docx",
    ".txt"
  ],
  "maxBatchFiles": 50,
  "maxFileSizeMB": 80,
  "documentTarget": "多篇科技文献",
  "demoDocuments": [
    {
      "id": "DOC001",
      "title": "面向工业能耗预测的层次超图时间序列Transformer",
      "publication_year": 2022,
      "abstract": "针对工业能耗序列中跨变量耦合与长期依赖难以建模的问题，本文构建层次超图时间序列Transformer，通过多尺度分块、自注意力和超边聚合学习设备变量之间的动态关系，用于工业园区负荷预测与能源调度。",
      "keywords": [
        "时间序列预测",
        "层次超图",
        "Transformer",
        "工业能耗"
      ]
    },
    {
      "id": "DOC002",
      "title": "面向跨机构工业物联网的联邦时间序列异常检测",
      "publication_year": 2023,
      "abstract": "本文提出资源感知的联邦时间序列异常检测框架，利用多分辨率变换、频域分块和参数高效大模型适配实现跨机构协同训练，在不共享原始数据的条件下识别工业物联网设备异常。",
      "keywords": [
        "联邦学习",
        "异常检测",
        "工业物联网",
        "多分辨率变换"
      ]
    },
    {
      "id": "DOC003",
      "title": "融合多尺度特征与难样本重加权的工业表面缺陷检测",
      "publication_year": 2022,
      "abstract": "针对裂纹、划痕与孔洞尺度差异大且背景纹理复杂的问题，本文构建多尺度特征金字塔和局部注意力增强网络，并使用难样本重加权提升微小缺陷识别能力，服务于智能制造质量检测。",
      "keywords": [
        "表面缺陷检测",
        "多尺度特征",
        "难样本重加权",
        "智能制造"
      ]
    },
    {
      "id": "DOC004",
      "title": "多源遥感协同编码的城市地表覆盖精细分类",
      "publication_year": 2024,
      "abstract": "本文联合高分辨率光学影像、合成孔径雷达和地形辅助信息，通过跨模态对齐与区域上下文建模完成建筑、道路、植被和水体分类，用于城市空间监测和土地利用调查。",
      "keywords": [
        "多源遥感",
        "跨模态对齐",
        "地表覆盖分类",
        "城市监测"
      ]
    },
    {
      "id": "DOC005",
      "title": "视觉语言模型解释可信度提升与反事实一致性验证",
      "publication_year": 2025,
      "abstract": "面向视觉语言模型解释幻觉问题，本文动态构建上下文干扰概念集合，执行文本图像双向解耦、反事实遮挡验证和多解释一致性校验，为医疗影像辅助分析等高风险场景输出可信解释热力图。",
      "keywords": [
        "视觉语言模型",
        "解释可信度",
        "反事实一致性",
        "医疗影像"
      ]
    },
    {
      "id": "DOC006",
      "title": "基于科技知识图谱的专家合作关系推理",
      "publication_year": 2023,
      "abstract": "本文融合论文、专利、项目和机构数据构建科技专家知识图谱，利用路径分析、关系传递和图表示学习识别直接关系、间接关系与合作成果，为科技人才发现和科研合作推荐提供支持。",
      "keywords": [
        "科技知识图谱",
        "专家关系",
        "路径推理",
        "合作推荐"
      ]
    },
    {
      "id": "DOC007",
      "title": "面向疾病诊疗的生物医学知识图谱关系补全",
      "publication_year": 2024,
      "abstract": "本文通过实体标准化、关系抽取和图神经网络表示学习构建疾病、药物和症状知识图谱，并利用路径约束关系补全发现潜在药物适应证，服务于临床知识检索和辅助诊疗。",
      "keywords": [
        "生物医学知识图谱",
        "关系补全",
        "图神经网络",
        "辅助诊疗"
      ]
    },
    {
      "id": "DOC008",
      "title": "碳包覆多孔硅复合负极的结构设计与循环性能优化",
      "publication_year": 2023,
      "abstract": "针对硅基负极充放电过程中的体积膨胀问题，本文设计碳包覆多孔硅复合结构，通过纳米孔隙缓冲和导电碳网络改善电子传输，为高能量密度锂离子电池提供材料设计方案。",
      "keywords": [
        "硅基负极",
        "多孔结构",
        "碳包覆",
        "锂离子电池"
      ]
    },
    {
      "id": "DOC009",
      "title": "面向碳捕集的多孔吸附材料构效关系分析",
      "publication_year": 2025,
      "abstract": "本文结合分子模拟、孔结构表征和机器学习回归分析多孔吸附材料的构效关系，筛选具有高二氧化碳选择性和循环稳定性的候选材料，用于工业烟气碳捕集与环境治理。",
      "keywords": [
        "碳捕集",
        "多孔吸附材料",
        "构效关系",
        "机器学习"
      ]
    },
    {
      "id": "DOC010",
      "title": "大模型增强的跨语言专利语义检索与技术路线发现",
      "publication_year": 2025,
      "abstract": "本文利用大语言模型生成专利技术摘要和检索查询，通过跨语言向量对齐、分类路径约束和检索结果重排序识别相似技术方案，为专利查新、技术路线分析和科技情报服务提供支持。",
      "keywords": [
        "大语言模型",
        "跨语言检索",
        "专利分析",
        "技术路线发现"
      ]
    },
    {
      "id": "DOC011",
      "title": "图神经网络驱动的催化剂性能预测与候选筛选",
      "publication_year": 2026,
      "abstract": "本文将催化剂晶体结构表示为原子图，通过消息传递网络学习局部配位环境和电子结构特征，预测催化活性与稳定性并筛选候选材料，用于绿色化工和能源催化材料研发。",
      "keywords": [
        "图神经网络",
        "催化剂",
        "性能预测",
        "候选筛选"
      ]
    },
    {
      "id": "DOC012",
      "title": "面向科技文献的研究问题识别与结构化综述生成",
      "publication_year": 2026,
      "abstract": "本文从科技文献中识别研究空白、技术难点、主问题和子问题，并结合语步识别、关键词抽取与大模型审核构建研究问题方法进展三层结构，为科研情报分析和自动综述生成提供能力。",
      "keywords": [
        "研究问题识别",
        "语步识别",
        "结构化综述",
        "科研情报"
      ]
    }
  ],
  "batchSampleFileNames": [
    "industrial_timeseries_transformer.pdf",
    "federated_anomaly_detection.pdf",
    "surface_defect_detection.pdf",
    "multisource_remote_sensing.pdf",
    "vlm_explanation_reliability.pdf",
    "expert_knowledge_graph.pdf"
  ],
  "demoBatchTextResult": {
    "code": 0,
    "message": "clustering_completed",
    "data": {
      "tool": "深度聚类工具",
      "input_type": "texts",
      "cluster_dimension": "technology",
      "cluster_dimension_name": "技术路线",
      "input_summary": {
        "document_count": 12,
        "parsed_sentence_count": 72,
        "file_names": [],
        "extracted_fields": [
          "title",
          "abstract",
          "keywords",
          "publication_year"
        ],
        "year_range": [
          2022,
          2026
        ]
      },
      "clustering_quality": {
        "cluster_count": 5,
        "noise_document_count": 0,
        "silhouette_score": 0.825,
        "average_intra_cluster_similarity": 0.894,
        "average_inter_cluster_separation": 0.856
      },
      "clusters": [
        {
          "cluster_id": "TECH-01",
          "size": 2,
          "ratio": 0.1667,
          "representative_terms": [
            "时间序列",
            "多尺度分块",
            "联邦学习",
            "异常检测"
          ],
          "representative_sentences": [
            "通过多尺度分块与关系建模学习跨变量动态依赖。"
          ],
          "feature_statistics": {
            "intra_cluster_similarity": 0.91,
            "inter_cluster_separation": 0.86,
            "semantic_density": 0.89,
            "average_sentence_count": 6
          },
          "representative_documents": [
            {
              "document_id": "DOC001",
              "title": "面向工业能耗预测的层次超图时间序列Transformer",
              "publication_year": 2022
            },
            {
              "document_id": "DOC002",
              "title": "面向跨机构工业物联网的联邦时间序列异常检测",
              "publication_year": 2023
            }
          ]
        },
        {
          "cluster_id": "TECH-02",
          "size": 3,
          "ratio": 0.25,
          "representative_terms": [
            "多尺度特征",
            "跨模态对齐",
            "视觉语言模型",
            "上下文建模"
          ],
          "representative_sentences": [
            "利用多尺度视觉表示和跨模态语义对齐增强复杂场景感知。"
          ],
          "feature_statistics": {
            "intra_cluster_similarity": 0.88,
            "inter_cluster_separation": 0.82,
            "semantic_density": 0.85,
            "average_sentence_count": 6
          },
          "representative_documents": [
            {
              "document_id": "DOC003",
              "title": "融合多尺度特征与难样本重加权的工业表面缺陷检测",
              "publication_year": 2022
            },
            {
              "document_id": "DOC004",
              "title": "多源遥感协同编码的城市地表覆盖精细分类",
              "publication_year": 2024
            },
            {
              "document_id": "DOC005",
              "title": "视觉语言模型解释可信度提升与反事实一致性验证",
              "publication_year": 2025
            }
          ]
        },
        {
          "cluster_id": "TECH-03",
          "size": 2,
          "ratio": 0.1667,
          "representative_terms": [
            "知识图谱",
            "关系抽取",
            "路径推理",
            "图表示学习"
          ],
          "representative_sentences": [
            "通过实体关系建模和路径约束完成知识关联与关系补全。"
          ],
          "feature_statistics": {
            "intra_cluster_similarity": 0.93,
            "inter_cluster_separation": 0.89,
            "semantic_density": 0.91,
            "average_sentence_count": 6
          },
          "representative_documents": [
            {
              "document_id": "DOC006",
              "title": "基于科技知识图谱的专家合作关系推理",
              "publication_year": 2023
            },
            {
              "document_id": "DOC007",
              "title": "面向疾病诊疗的生物医学知识图谱关系补全",
              "publication_year": 2024
            }
          ]
        },
        {
          "cluster_id": "TECH-04",
          "size": 3,
          "ratio": 0.25,
          "representative_terms": [
            "材料结构",
            "构效关系",
            "性能预测",
            "候选筛选"
          ],
          "representative_sentences": [
            "结合结构表征与机器学习建立材料构效关系并筛选候选体系。"
          ],
          "feature_statistics": {
            "intra_cluster_similarity": 0.87,
            "inter_cluster_separation": 0.84,
            "semantic_density": 0.85,
            "average_sentence_count": 6
          },
          "representative_documents": [
            {
              "document_id": "DOC008",
              "title": "碳包覆多孔硅复合负极的结构设计与循环性能优化",
              "publication_year": 2023
            },
            {
              "document_id": "DOC009",
              "title": "面向碳捕集的多孔吸附材料构效关系分析",
              "publication_year": 2025
            },
            {
              "document_id": "DOC011",
              "title": "图神经网络驱动的催化剂性能预测与候选筛选",
              "publication_year": 2026
            }
          ]
        },
        {
          "cluster_id": "TECH-05",
          "size": 2,
          "ratio": 0.1667,
          "representative_terms": [
            "大语言模型",
            "语义检索",
            "研究问题识别",
            "结构化生成"
          ],
          "representative_sentences": [
            "利用大模型完成科技文本语义理解、知识组织和结构化生成。"
          ],
          "feature_statistics": {
            "intra_cluster_similarity": 0.9,
            "inter_cluster_separation": 0.87,
            "semantic_density": 0.89,
            "average_sentence_count": 6
          },
          "representative_documents": [
            {
              "document_id": "DOC010",
              "title": "大模型增强的跨语言专利语义检索与技术路线发现",
              "publication_year": 2025
            },
            {
              "document_id": "DOC012",
              "title": "面向科技文献的研究问题识别与结构化综述生成",
              "publication_year": 2026
            }
          ]
        }
      ],
      "document_assignments": [
        {
          "document_id": "DOC001",
          "title": "面向工业能耗预测的层次超图时间序列Transformer",
          "publication_year": 2022,
          "cluster_id": "TECH-01",
          "similarity_to_centroid": 0.82,
          "key_evidence": "方法结构、算法机制与数据处理流程相近"
        },
        {
          "document_id": "DOC002",
          "title": "面向跨机构工业物联网的联邦时间序列异常检测",
          "publication_year": 2023,
          "cluster_id": "TECH-01",
          "similarity_to_centroid": 0.838,
          "key_evidence": "方法结构、算法机制与数据处理流程相近"
        },
        {
          "document_id": "DOC003",
          "title": "融合多尺度特征与难样本重加权的工业表面缺陷检测",
          "publication_year": 2022,
          "cluster_id": "TECH-02",
          "similarity_to_centroid": 0.856,
          "key_evidence": "方法结构、算法机制与数据处理流程相近"
        },
        {
          "document_id": "DOC004",
          "title": "多源遥感协同编码的城市地表覆盖精细分类",
          "publication_year": 2024,
          "cluster_id": "TECH-02",
          "similarity_to_centroid": 0.874,
          "key_evidence": "方法结构、算法机制与数据处理流程相近"
        },
        {
          "document_id": "DOC005",
          "title": "视觉语言模型解释可信度提升与反事实一致性验证",
          "publication_year": 2025,
          "cluster_id": "TECH-02",
          "similarity_to_centroid": 0.892,
          "key_evidence": "方法结构、算法机制与数据处理流程相近"
        },
        {
          "document_id": "DOC006",
          "title": "基于科技知识图谱的专家合作关系推理",
          "publication_year": 2023,
          "cluster_id": "TECH-03",
          "similarity_to_centroid": 0.91,
          "key_evidence": "方法结构、算法机制与数据处理流程相近"
        },
        {
          "document_id": "DOC007",
          "title": "面向疾病诊疗的生物医学知识图谱关系补全",
          "publication_year": 2024,
          "cluster_id": "TECH-03",
          "similarity_to_centroid": 0.928,
          "key_evidence": "方法结构、算法机制与数据处理流程相近"
        },
        {
          "document_id": "DOC008",
          "title": "碳包覆多孔硅复合负极的结构设计与循环性能优化",
          "publication_year": 2023,
          "cluster_id": "TECH-04",
          "similarity_to_centroid": 0.946,
          "key_evidence": "方法结构、算法机制与数据处理流程相近"
        },
        {
          "document_id": "DOC009",
          "title": "面向碳捕集的多孔吸附材料构效关系分析",
          "publication_year": 2025,
          "cluster_id": "TECH-04",
          "similarity_to_centroid": 0.82,
          "key_evidence": "方法结构、算法机制与数据处理流程相近"
        },
        {
          "document_id": "DOC010",
          "title": "大模型增强的跨语言专利语义检索与技术路线发现",
          "publication_year": 2025,
          "cluster_id": "TECH-05",
          "similarity_to_centroid": 0.838,
          "key_evidence": "方法结构、算法机制与数据处理流程相近"
        },
        {
          "document_id": "DOC011",
          "title": "图神经网络驱动的催化剂性能预测与候选筛选",
          "publication_year": 2026,
          "cluster_id": "TECH-04",
          "similarity_to_centroid": 0.856,
          "key_evidence": "方法结构、算法机制与数据处理流程相近"
        },
        {
          "document_id": "DOC012",
          "title": "面向科技文献的研究问题识别与结构化综述生成",
          "publication_year": 2026,
          "cluster_id": "TECH-05",
          "similarity_to_centroid": 0.874,
          "key_evidence": "方法结构、算法机制与数据处理流程相近"
        }
      ],
      "semantic_projection": [
        {
          "document_id": "DOC001",
          "title": "面向工业能耗预测的层次超图时间序列Transformer",
          "cluster_id": "TECH-01",
          "x": 13,
          "y": 22
        },
        {
          "document_id": "DOC002",
          "title": "面向跨机构工业物联网的联邦时间序列异常检测",
          "cluster_id": "TECH-01",
          "x": 22,
          "y": 27
        },
        {
          "document_id": "DOC003",
          "title": "融合多尺度特征与难样本重加权的工业表面缺陷检测",
          "cluster_id": "TECH-02",
          "x": 65,
          "y": 19
        },
        {
          "document_id": "DOC004",
          "title": "多源遥感协同编码的城市地表覆盖精细分类",
          "cluster_id": "TECH-02",
          "x": 74,
          "y": 24
        },
        {
          "document_id": "DOC005",
          "title": "视觉语言模型解释可信度提升与反事实一致性验证",
          "cluster_id": "TECH-02",
          "x": 68,
          "y": 27
        },
        {
          "document_id": "DOC006",
          "title": "基于科技知识图谱的专家合作关系推理",
          "cluster_id": "TECH-03",
          "x": 45,
          "y": 45
        },
        {
          "document_id": "DOC007",
          "title": "面向疾病诊疗的生物医学知识图谱关系补全",
          "cluster_id": "TECH-03",
          "x": 54,
          "y": 50
        },
        {
          "document_id": "DOC008",
          "title": "碳包覆多孔硅复合负极的结构设计与循环性能优化",
          "cluster_id": "TECH-04",
          "x": 17,
          "y": 72
        },
        {
          "document_id": "DOC009",
          "title": "面向碳捕集的多孔吸附材料构效关系分析",
          "cluster_id": "TECH-04",
          "x": 26,
          "y": 77
        },
        {
          "document_id": "DOC011",
          "title": "图神经网络驱动的催化剂性能预测与候选筛选",
          "cluster_id": "TECH-04",
          "x": 20,
          "y": 80
        },
        {
          "document_id": "DOC010",
          "title": "大模型增强的跨语言专利语义检索与技术路线发现",
          "cluster_id": "TECH-05",
          "x": 71,
          "y": 69
        },
        {
          "document_id": "DOC012",
          "title": "面向科技文献的研究问题识别与结构化综述生成",
          "cluster_id": "TECH-05",
          "x": 80,
          "y": 74
        }
      ],
      "theme_trend_analysis": {
        "years": [
          2022,
          2023,
          2024,
          2025,
          2026
        ],
        "series": [
          {
            "cluster_id": "TECH-01",
            "representative_terms": [
              "时间序列",
              "多尺度分块",
              "联邦学习",
              "异常检测"
            ],
            "yearly_counts": [
              1,
              1,
              0,
              0,
              0
            ],
            "trend_score": 0.58
          },
          {
            "cluster_id": "TECH-02",
            "representative_terms": [
              "多尺度特征",
              "跨模态对齐",
              "视觉语言模型",
              "上下文建模"
            ],
            "yearly_counts": [
              1,
              0,
              1,
              1,
              0
            ],
            "trend_score": 0.69
          },
          {
            "cluster_id": "TECH-03",
            "representative_terms": [
              "知识图谱",
              "关系抽取",
              "路径推理",
              "图表示学习"
            ],
            "yearly_counts": [
              0,
              1,
              1,
              0,
              0
            ],
            "trend_score": 0.58
          },
          {
            "cluster_id": "TECH-04",
            "representative_terms": [
              "材料结构",
              "构效关系",
              "性能预测",
              "候选筛选"
            ],
            "yearly_counts": [
              0,
              1,
              0,
              1,
              1
            ],
            "trend_score": 0.69
          },
          {
            "cluster_id": "TECH-05",
            "representative_terms": [
              "大语言模型",
              "语义检索",
              "研究问题识别",
              "结构化生成"
            ],
            "yearly_counts": [
              0,
              0,
              0,
              1,
              1
            ],
            "trend_score": 0.58
          }
        ],
        "rising_cluster_id": "TECH-04",
        "emerging_cluster_id": "TECH-05",
        "stable_cluster_id": "TECH-02",
        "summary": "技术类簇由传统视觉与时间序列建模相关短语，逐步扩展到大模型语义理解、图推理和跨模态可信分析相关短语。"
      },
      "training_evaluation": {
        "dataset_version": "MED-CLUSTER-DEMO-2026.07",
        "evidence_status": "prototype_demo_configuration",
        "notice": "以下规模和指标仅用于静态原型展示，不代表真实训练数据、模型评测结论或生产性能。接入项目数据后应替换为可审计的数据版本、划分策略和评测报告。",
        "datasets": [
          {
            "name": "医学文献训练集",
            "version": "MED-TRAIN-DEMO-V1",
            "size": 12000,
            "unit": "篇",
            "purpose": "句子编码与聚类模型训练",
            "status": "演示配置"
          },
          {
            "name": "人工标注样本",
            "version": "MED-ANNOTATED-DEMO-V1",
            "size": 3200,
            "unit": "篇",
            "purpose": "类簇归属与主题一致性监督",
            "status": "演示配置"
          },
          {
            "name": "在线评测集",
            "version": "MED-ONLINE-EVAL-DEMO-V1",
            "size": 800,
            "unit": "篇",
            "purpose": "按时间顺序模拟在线评测",
            "status": "演示配置"
          },
          {
            "name": "随机评测集",
            "version": "MED-RANDOM-EVAL-DEMO-V1",
            "size": 800,
            "unit": "篇",
            "purpose": "随机抽样稳定性评测",
            "status": "演示配置"
          }
        ],
        "metrics": {
          "silhouette_score": 0.712,
          "normalized_mutual_information": 0.781,
          "adjusted_rand_index": 0.736,
          "expert_agreement": 0.846
        },
        "correction_loop": {
          "supported_operations": [
            "move_document",
            "merge_clusters",
            "split_cluster"
          ],
          "correction_count": 0,
          "update_status": "not_submitted",
          "incremental_version": "pending"
        }
      },
      "manual_correction": {
        "supported_operations": [
          "move_document",
          "merge_clusters",
          "split_cluster"
        ],
        "correction_count": 0,
        "update_status": "not_submitted",
        "incremental_version": "pending"
      }
    },
    "meta": {
      "feature_level": "sentence",
      "feature_source_strategy": "provided_title_abstract_keywords_publication_time",
      "sentence_weighting_strategy": "method_model_algorithm_pipeline_weighting",
      "algorithm": "auto_hdbscan_with_quality_selection",
      "similarity_metric": "cosine",
      "request_id": "req_deep_cluster_technology_1786704241360",
      "elapsed_ms": 1738,
      "prototype_demo": true,
      "prototype_data_notice": "以下规模和指标仅用于静态原型展示，不代表真实训练数据、模型评测结论或生产性能。接入项目数据后应替换为可审计的数据版本、划分策略和评测报告。",
      "supported_result_formats": [
        "json",
        "csv"
      ]
    }
  },
  "demoBatchFileResult": {
    "code": 0,
    "message": "clustering_completed",
    "data": {
      "tool": "深度聚类工具",
      "input_type": "files",
      "cluster_dimension": "technology",
      "cluster_dimension_name": "技术路线",
      "input_summary": {
        "document_count": 6,
        "parsed_sentence_count": 48,
        "file_names": [
          "industrial_timeseries_transformer.pdf",
          "federated_anomaly_detection.pdf",
          "surface_defect_detection.pdf",
          "multisource_remote_sensing.pdf",
          "vlm_explanation_reliability.pdf",
          "expert_knowledge_graph.pdf"
        ],
        "extracted_fields": [
          "title",
          "abstract",
          "keywords",
          "key_sections",
          "publication_year"
        ],
        "year_range": [
          2022,
          2025
        ]
      },
      "clustering_quality": {
        "cluster_count": 5,
        "noise_document_count": 0,
        "silhouette_score": 0.828,
        "average_intra_cluster_similarity": 0.9,
        "average_inter_cluster_separation": 0.856
      },
      "clusters": [
        {
          "cluster_id": "TECH-01",
          "size": 2,
          "ratio": 0.3333,
          "representative_terms": [
            "时间序列",
            "多尺度分块",
            "联邦学习",
            "异常检测"
          ],
          "representative_sentences": [
            "通过多尺度分块与关系建模学习跨变量动态依赖。"
          ],
          "feature_statistics": {
            "intra_cluster_similarity": 0.91,
            "inter_cluster_separation": 0.86,
            "semantic_density": 0.89,
            "average_sentence_count": 8
          },
          "representative_documents": [
            {
              "document_id": "FILE001",
              "title": "industrial_timeseries_transformer",
              "publication_year": 2022
            },
            {
              "document_id": "FILE006",
              "title": "expert_knowledge_graph",
              "publication_year": 2023
            }
          ]
        },
        {
          "cluster_id": "TECH-02",
          "size": 1,
          "ratio": 0.1667,
          "representative_terms": [
            "多尺度特征",
            "跨模态对齐",
            "视觉语言模型",
            "上下文建模"
          ],
          "representative_sentences": [
            "利用多尺度视觉表示和跨模态语义对齐增强复杂场景感知。"
          ],
          "feature_statistics": {
            "intra_cluster_similarity": 0.88,
            "inter_cluster_separation": 0.82,
            "semantic_density": 0.85,
            "average_sentence_count": 8
          },
          "representative_documents": [
            {
              "document_id": "FILE002",
              "title": "federated_anomaly_detection",
              "publication_year": 2023
            }
          ]
        },
        {
          "cluster_id": "TECH-03",
          "size": 1,
          "ratio": 0.1667,
          "representative_terms": [
            "知识图谱",
            "关系抽取",
            "路径推理",
            "图表示学习"
          ],
          "representative_sentences": [
            "通过实体关系建模和路径约束完成知识关联与关系补全。"
          ],
          "feature_statistics": {
            "intra_cluster_similarity": 0.93,
            "inter_cluster_separation": 0.89,
            "semantic_density": 0.91,
            "average_sentence_count": 8
          },
          "representative_documents": [
            {
              "document_id": "FILE003",
              "title": "surface_defect_detection",
              "publication_year": 2022
            }
          ]
        },
        {
          "cluster_id": "TECH-04",
          "size": 1,
          "ratio": 0.1667,
          "representative_terms": [
            "材料结构",
            "构效关系",
            "性能预测",
            "候选筛选"
          ],
          "representative_sentences": [
            "结合结构表征与机器学习建立材料构效关系并筛选候选体系。"
          ],
          "feature_statistics": {
            "intra_cluster_similarity": 0.87,
            "inter_cluster_separation": 0.84,
            "semantic_density": 0.85,
            "average_sentence_count": 8
          },
          "representative_documents": [
            {
              "document_id": "FILE004",
              "title": "multisource_remote_sensing",
              "publication_year": 2024
            }
          ]
        },
        {
          "cluster_id": "TECH-05",
          "size": 1,
          "ratio": 0.1667,
          "representative_terms": [
            "大语言模型",
            "语义检索",
            "研究问题识别",
            "结构化生成"
          ],
          "representative_sentences": [
            "利用大模型完成科技文本语义理解、知识组织和结构化生成。"
          ],
          "feature_statistics": {
            "intra_cluster_similarity": 0.9,
            "inter_cluster_separation": 0.87,
            "semantic_density": 0.89,
            "average_sentence_count": 8
          },
          "representative_documents": [
            {
              "document_id": "FILE005",
              "title": "vlm_explanation_reliability",
              "publication_year": 2025
            }
          ]
        }
      ],
      "document_assignments": [
        {
          "document_id": "FILE001",
          "title": "industrial_timeseries_transformer",
          "publication_year": 2022,
          "cluster_id": "TECH-01",
          "similarity_to_centroid": 0.82,
          "key_evidence": "方法结构、算法机制与数据处理流程相近"
        },
        {
          "document_id": "FILE002",
          "title": "federated_anomaly_detection",
          "publication_year": 2023,
          "cluster_id": "TECH-02",
          "similarity_to_centroid": 0.838,
          "key_evidence": "方法结构、算法机制与数据处理流程相近"
        },
        {
          "document_id": "FILE003",
          "title": "surface_defect_detection",
          "publication_year": 2022,
          "cluster_id": "TECH-03",
          "similarity_to_centroid": 0.856,
          "key_evidence": "方法结构、算法机制与数据处理流程相近"
        },
        {
          "document_id": "FILE004",
          "title": "multisource_remote_sensing",
          "publication_year": 2024,
          "cluster_id": "TECH-04",
          "similarity_to_centroid": 0.874,
          "key_evidence": "方法结构、算法机制与数据处理流程相近"
        },
        {
          "document_id": "FILE005",
          "title": "vlm_explanation_reliability",
          "publication_year": 2025,
          "cluster_id": "TECH-05",
          "similarity_to_centroid": 0.892,
          "key_evidence": "方法结构、算法机制与数据处理流程相近"
        },
        {
          "document_id": "FILE006",
          "title": "expert_knowledge_graph",
          "publication_year": 2023,
          "cluster_id": "TECH-01",
          "similarity_to_centroid": 0.91,
          "key_evidence": "方法结构、算法机制与数据处理流程相近"
        }
      ],
      "semantic_projection": [],
      "theme_trend_analysis": {
        "years": [
          2022,
          2023,
          2024,
          2025,
          2026
        ],
        "series": [
          {
            "cluster_id": "TECH-01",
            "representative_terms": [
              "时间序列",
              "多尺度分块",
              "联邦学习",
              "异常检测"
            ],
            "yearly_counts": [
              1,
              1,
              0,
              0,
              0
            ],
            "trend_score": 0.58
          },
          {
            "cluster_id": "TECH-02",
            "representative_terms": [
              "多尺度特征",
              "跨模态对齐",
              "视觉语言模型",
              "上下文建模"
            ],
            "yearly_counts": [
              0,
              1,
              0,
              0,
              0
            ],
            "trend_score": 0.47
          },
          {
            "cluster_id": "TECH-03",
            "representative_terms": [
              "知识图谱",
              "关系抽取",
              "路径推理",
              "图表示学习"
            ],
            "yearly_counts": [
              1,
              0,
              0,
              0,
              0
            ],
            "trend_score": 0.47
          },
          {
            "cluster_id": "TECH-04",
            "representative_terms": [
              "材料结构",
              "构效关系",
              "性能预测",
              "候选筛选"
            ],
            "yearly_counts": [
              0,
              0,
              1,
              0,
              0
            ],
            "trend_score": 0.47
          },
          {
            "cluster_id": "TECH-05",
            "representative_terms": [
              "大语言模型",
              "语义检索",
              "研究问题识别",
              "结构化生成"
            ],
            "yearly_counts": [
              0,
              0,
              0,
              1,
              0
            ],
            "trend_score": 0.47
          }
        ],
        "rising_cluster_id": "TECH-05",
        "emerging_cluster_id": "TECH-05",
        "stable_cluster_id": "TECH-02",
        "summary": "技术类簇由传统视觉与时间序列建模相关短语，逐步扩展到大模型语义理解、图推理和跨模态可信分析相关短语。"
      },
      "training_evaluation": {
        "dataset_version": "MED-CLUSTER-DEMO-2026.07",
        "evidence_status": "prototype_demo_configuration",
        "notice": "以下规模和指标仅用于静态原型展示，不代表真实训练数据、模型评测结论或生产性能。接入项目数据后应替换为可审计的数据版本、划分策略和评测报告。",
        "datasets": [
          {
            "name": "医学文献训练集",
            "version": "MED-TRAIN-DEMO-V1",
            "size": 12000,
            "unit": "篇",
            "purpose": "句子编码与聚类模型训练",
            "status": "演示配置"
          },
          {
            "name": "人工标注样本",
            "version": "MED-ANNOTATED-DEMO-V1",
            "size": 3200,
            "unit": "篇",
            "purpose": "类簇归属与主题一致性监督",
            "status": "演示配置"
          },
          {
            "name": "在线评测集",
            "version": "MED-ONLINE-EVAL-DEMO-V1",
            "size": 800,
            "unit": "篇",
            "purpose": "按时间顺序模拟在线评测",
            "status": "演示配置"
          },
          {
            "name": "随机评测集",
            "version": "MED-RANDOM-EVAL-DEMO-V1",
            "size": 800,
            "unit": "篇",
            "purpose": "随机抽样稳定性评测",
            "status": "演示配置"
          }
        ],
        "metrics": {
          "silhouette_score": 0.712,
          "normalized_mutual_information": 0.781,
          "adjusted_rand_index": 0.736,
          "expert_agreement": 0.846
        },
        "correction_loop": {
          "supported_operations": [
            "move_document",
            "merge_clusters",
            "split_cluster"
          ],
          "correction_count": 0,
          "update_status": "not_submitted",
          "incremental_version": "pending"
        }
      },
      "manual_correction": {
        "supported_operations": [
          "move_document",
          "merge_clusters",
          "split_cluster"
        ],
        "correction_count": 0,
        "update_status": "not_submitted",
        "incremental_version": "pending"
      }
    },
    "meta": {
      "feature_level": "sentence",
      "feature_source_strategy": "auto_parse_title_abstract_keywords_key_sections_publication_time",
      "sentence_weighting_strategy": "method_model_algorithm_pipeline_weighting",
      "algorithm": "auto_hdbscan_with_quality_selection",
      "similarity_metric": "cosine",
      "request_id": "req_deep_cluster_technology_1786704241361",
      "elapsed_ms": 2846,
      "prototype_demo": true,
      "prototype_data_notice": "以下规模和指标仅用于静态原型展示，不代表真实训练数据、模型评测结论或生产性能。接入项目数据后应替换为可审计的数据版本、划分策略和评测报告。",
      "supported_result_formats": [
        "json",
        "csv"
      ]
    }
  }
}

export const clusterLabelRuntimeResponses = {
  "demoDocuments": [
    {
      "id": "DOC001",
      "title": "面向工业设备的多尺度时间序列异常检测",
      "abstract": "研究采用多尺度分块、频域建模和联邦学习识别工业设备时间序列中的异常状态。",
      "keywords": [
        "时间序列",
        "异常检测",
        "多尺度分块",
        "联邦学习"
      ],
      "publication_year": 2024
    },
    {
      "id": "DOC002",
      "title": "基于层次超图的多变量时序建模",
      "abstract": "研究利用层次超图和注意力机制建模多变量时间序列中的高阶依赖关系。",
      "keywords": [
        "层次超图",
        "多变量时序",
        "注意力机制"
      ],
      "publication_year": 2025
    },
    {
      "id": "DOC003",
      "title": "视觉语言模型解释可信度提升方法",
      "abstract": "研究通过上下文解耦、反事实验证和多解释一致性校验提高视觉语言模型解释可信度。",
      "keywords": [
        "视觉语言模型",
        "反事实验证",
        "解释可信度"
      ],
      "publication_year": 2026
    },
    {
      "id": "DOC004",
      "title": "面向科研关系发现的知识图谱推理",
      "abstract": "研究通过实体关系抽取、图路径分析和关系传递发现专家与成果之间的隐含关联。",
      "keywords": [
        "知识图谱",
        "关系抽取",
        "路径推理"
      ],
      "publication_year": 2025
    },
    {
      "id": "DOC005",
      "title": "材料构效关系驱动的性能预测",
      "abstract": "研究结合材料结构表征、机器学习和高通量计算预测材料性能并筛选候选材料。",
      "keywords": [
        "材料结构",
        "构效关系",
        "性能预测",
        "高通量计算"
      ],
      "publication_year": 2024
    },
    {
      "id": "DOC006",
      "title": "大语言模型驱动的科研语义检索",
      "abstract": "研究利用大语言模型完成科研文本语义检索、研究问题识别和结构化综述生成。",
      "keywords": [
        "大语言模型",
        "语义检索",
        "研究问题识别"
      ],
      "publication_year": 2026
    }
  ],
  "batchText": {
    "code": 0,
    "message": "success",
    "data": {
      "tool": "聚类标签生成工具",
      "source_mode": "batch-text",
      "source": {
        "source_type": "batch_text",
        "document_count": 6,
        "cluster_dimension": "technology",
        "cluster_dimension_name": "技术路线",
        "internal_deep_cluster": true,
        "clustering_strategy": "model_internal_default",
        "clustering_strategy_name": "本功能内部调用模型默认深度聚类"
      },
      "internal_clustering": {
        "used": true,
        "strategy": "model_internal_default",
        "exposed_to_user": false
      },
      "parameters": {
        "label_length": {
          "min": 4,
          "max": 12,
          "unit": "adaptive"
        },
        "output_language": "auto",
        "distinctiveness_threshold": 0.75
      },
      "generation_strategy": "adaptive_label_generation",
      "cluster_count": 2,
      "generated_label_count": 2,
      "no_candidate_cluster_count": 0,
      "labels": [
        {
          "cluster_id": "CLUSTER-01",
          "status": "generated",
          "recommended_label": "多尺度时序异常检测",
          "candidate_labels": [
            {
              "label": "多尺度时序异常检测",
              "rank": 1,
              "confidence": 0.96,
              "distinctiveness": 0.93
            },
            {
              "label": "联邦时序建模",
              "rank": 2,
              "confidence": 0.91,
              "distinctiveness": 0.89
            },
            {
              "label": "时序异常识别",
              "rank": 3,
              "confidence": 0.86,
              "distinctiveness": 0.85
            }
          ],
          "confidence": 0.96,
          "distinctiveness": 0.93,
          "representativeness": 0.94,
          "difference_explanation": "推荐标签覆盖类簇核心术语，并满足当前类簇间差异阈值。",
          "evidence": {
            "keywords": [
              "时间序列",
              "异常检测",
              "多尺度分块",
              "联邦学习",
              "视觉语言模型"
            ],
            "named_entities": [
              "时间序列",
              "异常检测",
              "多尺度分块"
            ],
            "center_sentence": "研究采用多尺度分块、频域建模和联邦学习识别工业设备时间序列中的异常状态。",
            "text_count": 3
          },
          "linked_document_ids": [
            "DOC001",
            "DOC003",
            "DOC005"
          ]
        },
        {
          "cluster_id": "CLUSTER-02",
          "status": "generated",
          "recommended_label": "跨模态视觉语义对齐",
          "candidate_labels": [
            {
              "label": "跨模态视觉语义对齐",
              "rank": 1,
              "confidence": 0.94,
              "distinctiveness": 0.92
            },
            {
              "label": "多尺度视觉理解",
              "rank": 2,
              "confidence": 0.89,
              "distinctiveness": 0.88
            },
            {
              "label": "视觉语言建模",
              "rank": 3,
              "confidence": 0.84,
              "distinctiveness": 0.84
            }
          ],
          "confidence": 0.94,
          "distinctiveness": 0.92,
          "representativeness": 0.93,
          "difference_explanation": "推荐标签覆盖类簇核心术语，并满足当前类簇间差异阈值。",
          "evidence": {
            "keywords": [
              "层次超图",
              "多变量时序",
              "注意力机制",
              "知识图谱",
              "关系抽取"
            ],
            "named_entities": [
              "层次超图",
              "多变量时序",
              "注意力机制"
            ],
            "center_sentence": "研究利用层次超图和注意力机制建模多变量时间序列中的高阶依赖关系。",
            "text_count": 3
          },
          "linked_document_ids": [
            "DOC002",
            "DOC004",
            "DOC006"
          ]
        }
      ],
      "statistics": {
        "average_confidence": 0.95,
        "average_distinctiveness": 0.93,
        "duplicate_candidate_count": 0,
        "filtered_candidate_count": 0
      }
    },
    "meta": {
      "request_id": "req_cluster_label_1786704241363",
      "processing_stages": [
        "input_validation",
        "document_parse",
        "internal_deep_cluster",
        "semantic_statistics",
        "candidate_generation",
        "difference_filter",
        "result_build"
      ],
      "elapsed_ms": 1260
    }
  },
  "batchFile": {
    "code": 0,
    "message": "success",
    "data": {
      "tool": "聚类标签生成工具",
      "source_mode": "batch",
      "source": {
        "source_type": "batch_files",
        "file_count": 6,
        "cluster_dimension": "technology",
        "cluster_dimension_name": "技术路线",
        "internal_deep_cluster": true,
        "clustering_strategy": "model_internal_default",
        "clustering_strategy_name": "本功能内部调用模型默认深度聚类"
      },
      "internal_clustering": {
        "used": true,
        "strategy": "model_internal_default",
        "exposed_to_user": false
      },
      "parameters": {
        "label_length": {
          "min": 4,
          "max": 12,
          "unit": "adaptive"
        },
        "output_language": "auto",
        "distinctiveness_threshold": 0.75
      },
      "generation_strategy": "adaptive_label_generation",
      "cluster_count": 2,
      "generated_label_count": 2,
      "no_candidate_cluster_count": 0,
      "labels": [
        {
          "cluster_id": "CLUSTER-01",
          "status": "generated",
          "recommended_label": "多尺度时序异常检测",
          "candidate_labels": [
            {
              "label": "多尺度时序异常检测",
              "rank": 1,
              "confidence": 0.96,
              "distinctiveness": 0.93
            },
            {
              "label": "联邦时序建模",
              "rank": 2,
              "confidence": 0.91,
              "distinctiveness": 0.89
            },
            {
              "label": "时序异常识别",
              "rank": 3,
              "confidence": 0.86,
              "distinctiveness": 0.85
            }
          ],
          "confidence": 0.96,
          "distinctiveness": 0.93,
          "representativeness": 0.94,
          "difference_explanation": "推荐标签覆盖类簇核心术语，并满足当前类簇间差异阈值。",
          "evidence": {
            "keywords": [
              "industrial",
              "timeseries",
              "anomaly",
              "vision",
              "language"
            ],
            "named_entities": [
              "industrial",
              "timeseries",
              "anomaly"
            ],
            "center_sentence": "系统解析文件“industrial_timeseries_anomaly.pdf”，提取标题、摘要、关键词和正文语义后参与默认深度聚类。",
            "text_count": 3
          },
          "linked_document_ids": [
            "FILE-DOC-001",
            "FILE-DOC-003",
            "FILE-DOC-005"
          ]
        },
        {
          "cluster_id": "CLUSTER-02",
          "status": "generated",
          "recommended_label": "跨模态视觉语义对齐",
          "candidate_labels": [
            {
              "label": "跨模态视觉语义对齐",
              "rank": 1,
              "confidence": 0.94,
              "distinctiveness": 0.92
            },
            {
              "label": "多尺度视觉理解",
              "rank": 2,
              "confidence": 0.89,
              "distinctiveness": 0.88
            },
            {
              "label": "视觉语言建模",
              "rank": 3,
              "confidence": 0.84,
              "distinctiveness": 0.84
            }
          ],
          "confidence": 0.94,
          "distinctiveness": 0.92,
          "representativeness": 0.93,
          "difference_explanation": "推荐标签覆盖类簇核心术语，并满足当前类簇间差异阈值。",
          "evidence": {
            "keywords": [
              "hypergraph",
              "sequence",
              "modeling",
              "knowledge",
              "graph"
            ],
            "named_entities": [
              "hypergraph",
              "sequence",
              "modeling"
            ],
            "center_sentence": "系统解析文件“hypergraph_sequence_modeling.pdf”，提取标题、摘要、关键词和正文语义后参与默认深度聚类。",
            "text_count": 3
          },
          "linked_document_ids": [
            "FILE-DOC-002",
            "FILE-DOC-004",
            "FILE-DOC-006"
          ]
        }
      ],
      "statistics": {
        "average_confidence": 0.95,
        "average_distinctiveness": 0.93,
        "duplicate_candidate_count": 0,
        "filtered_candidate_count": 0
      }
    },
    "meta": {
      "request_id": "req_cluster_label_1786704241363",
      "processing_stages": [
        "input_validation",
        "document_parse",
        "internal_deep_cluster",
        "semantic_statistics",
        "candidate_generation",
        "difference_filter",
        "result_build"
      ],
      "elapsed_ms": 1260
    }
  },
  "history": {
    "code": 0,
    "message": "success",
    "data": {
      "tool": "聚类标签生成工具",
      "source_mode": "existing-result",
      "source": {
        "source_type": "database_cluster_task",
        "cluster_task_id": "CLUSTER_DEFAULT_20260726001",
        "cluster_result_id": "CLUSTER_DEFAULT_20260726001_RESULT",
        "result_name": "跨领域科技文献默认语义聚类",
        "database_table": "deep_cluster_results",
        "storage_status": "已入库",
        "document_count": 12,
        "cluster_dimension": "technology",
        "cluster_dimension_name": "技术路线",
        "internal_deep_cluster": false,
        "clustering_strategy": "model_internal_default",
        "clustering_strategy_name": "已有模型默认语义聚类结果"
      },
      "internal_clustering": {
        "used": false,
        "strategy": null,
        "exposed_to_user": false
      },
      "parameters": {
        "label_length": {
          "min": 4,
          "max": 12,
          "unit": "adaptive"
        },
        "output_language": "auto",
        "distinctiveness_threshold": 0.75
      },
      "generation_strategy": "adaptive_label_generation",
      "cluster_count": 5,
      "generated_label_count": 5,
      "no_candidate_cluster_count": 0,
      "labels": [
        {
          "cluster_id": "CLUSTER-01",
          "status": "generated",
          "recommended_label": "多尺度时序异常检测",
          "candidate_labels": [
            {
              "label": "多尺度时序异常检测",
              "rank": 1,
              "confidence": 0.96,
              "distinctiveness": 0.93
            },
            {
              "label": "联邦时序建模",
              "rank": 2,
              "confidence": 0.91,
              "distinctiveness": 0.89
            },
            {
              "label": "时序异常识别",
              "rank": 3,
              "confidence": 0.86,
              "distinctiveness": 0.85
            }
          ],
          "confidence": 0.96,
          "distinctiveness": 0.93,
          "representativeness": 0.94,
          "difference_explanation": "推荐标签覆盖类簇核心术语，并满足当前类簇间差异阈值。",
          "evidence": {
            "keywords": [
              "时间序列建模",
              "多尺度分块",
              "联邦学习",
              "异常检测"
            ],
            "named_entities": [
              "时间序列建模",
              "多尺度分块",
              "联邦学习"
            ],
            "center_sentence": "多尺度时间序列建模用于捕获局部与长期动态模式。",
            "text_count": 2
          },
          "linked_document_ids": [
            "DOC001",
            "DOC002"
          ]
        },
        {
          "cluster_id": "CLUSTER-02",
          "status": "generated",
          "recommended_label": "跨模态视觉语义对齐",
          "candidate_labels": [
            {
              "label": "跨模态视觉语义对齐",
              "rank": 1,
              "confidence": 0.94,
              "distinctiveness": 0.92
            },
            {
              "label": "多尺度视觉理解",
              "rank": 2,
              "confidence": 0.89,
              "distinctiveness": 0.88
            },
            {
              "label": "视觉语言建模",
              "rank": 3,
              "confidence": 0.84,
              "distinctiveness": 0.84
            }
          ],
          "confidence": 0.94,
          "distinctiveness": 0.92,
          "representativeness": 0.93,
          "difference_explanation": "推荐标签覆盖类簇核心术语，并满足当前类簇间差异阈值。",
          "evidence": {
            "keywords": [
              "多尺度特征",
              "跨模态对齐",
              "视觉语言模型",
              "上下文建模"
            ],
            "named_entities": [
              "多尺度特征",
              "跨模态对齐",
              "视觉语言模型"
            ],
            "center_sentence": "多尺度视觉特征用于同时建模全局语义和局部细节。",
            "text_count": 2
          },
          "linked_document_ids": [
            "DOC003",
            "DOC004",
            "DOC005"
          ]
        },
        {
          "cluster_id": "CLUSTER-03",
          "status": "generated",
          "recommended_label": "知识图谱关系推理",
          "candidate_labels": [
            {
              "label": "知识图谱关系推理",
              "rank": 1,
              "confidence": 0.92,
              "distinctiveness": 0.9
            },
            {
              "label": "实体关系抽取",
              "rank": 2,
              "confidence": 0.87,
              "distinctiveness": 0.86
            },
            {
              "label": "图路径知识发现",
              "rank": 3,
              "confidence": 0.82,
              "distinctiveness": 0.82
            }
          ],
          "confidence": 0.92,
          "distinctiveness": 0.9,
          "representativeness": 0.92,
          "difference_explanation": "推荐标签覆盖类簇核心术语，并满足当前类簇间差异阈值。",
          "evidence": {
            "keywords": [
              "知识图谱",
              "关系抽取",
              "路径推理",
              "图表示学习"
            ],
            "named_entities": [
              "知识图谱",
              "关系抽取",
              "路径推理"
            ],
            "center_sentence": "实体关系抽取为知识图谱构建提供结构化三元组。",
            "text_count": 2
          },
          "linked_document_ids": [
            "DOC006",
            "DOC007"
          ]
        },
        {
          "cluster_id": "CLUSTER-04",
          "status": "generated",
          "recommended_label": "材料构效性能预测",
          "candidate_labels": [
            {
              "label": "材料构效性能预测",
              "rank": 1,
              "confidence": 0.91,
              "distinctiveness": 0.89
            },
            {
              "label": "材料结构表征",
              "rank": 2,
              "confidence": 0.86,
              "distinctiveness": 0.85
            },
            {
              "label": "绿色材料研发",
              "rank": 3,
              "confidence": 0.81,
              "distinctiveness": 0.81
            }
          ],
          "confidence": 0.91,
          "distinctiveness": 0.89,
          "representativeness": 0.9,
          "difference_explanation": "推荐标签覆盖类簇核心术语，并满足当前类簇间差异阈值。",
          "evidence": {
            "keywords": [
              "材料结构",
              "构效关系",
              "性能预测",
              "绿色制造"
            ],
            "named_entities": [
              "材料结构",
              "构效关系",
              "性能预测"
            ],
            "center_sentence": "材料结构表征与机器学习结合用于性能预测。",
            "text_count": 2
          },
          "linked_document_ids": [
            "DOC008",
            "DOC009",
            "DOC011"
          ]
        },
        {
          "cluster_id": "CLUSTER-05",
          "status": "generated",
          "recommended_label": "大模型科研语义理解",
          "candidate_labels": [
            {
              "label": "大模型科研语义理解",
              "rank": 1,
              "confidence": 0.89,
              "distinctiveness": 0.87
            },
            {
              "label": "科研语义检索",
              "rank": 2,
              "confidence": 0.84,
              "distinctiveness": 0.83
            },
            {
              "label": "研究问题结构化生成",
              "rank": 3,
              "confidence": 0.79,
              "distinctiveness": 0.79
            }
          ],
          "confidence": 0.89,
          "distinctiveness": 0.87,
          "representativeness": 0.89,
          "difference_explanation": "推荐标签覆盖类簇核心术语，并满足当前类簇间差异阈值。",
          "evidence": {
            "keywords": [
              "大语言模型",
              "语义检索",
              "研究问题识别",
              "结构化生成"
            ],
            "named_entities": [
              "大语言模型",
              "语义检索",
              "研究问题识别"
            ],
            "center_sentence": "大语言模型用于科研语义检索和结构化生成。",
            "text_count": 2
          },
          "linked_document_ids": [
            "DOC010",
            "DOC012"
          ]
        }
      ],
      "statistics": {
        "average_confidence": 0.92,
        "average_distinctiveness": 0.9,
        "duplicate_candidate_count": 0,
        "filtered_candidate_count": 0
      }
    },
    "meta": {
      "request_id": "req_cluster_label_1786704241364",
      "processing_stages": [
        "input_validation",
        "cluster_data_read",
        "semantic_statistics",
        "candidate_generation",
        "difference_filter",
        "result_build"
      ],
      "elapsed_ms": 1260
    }
  }
}

export const structuredReviewRuntime = {
  "demoDocuments": [
    {
      "id": "DOC001",
      "title": "面向多变量时间序列的层次超图建模方法",
      "abstract": "研究面向复杂多变量时间序列中的高阶依赖建模问题，提出层次超图与多尺度分块结合的方法。",
      "text": "本文通过多尺度分块提取局部动态模式，并利用层次超图描述变量之间的高阶关系。实验表明，该方法在长期预测与异常识别任务中提升了稳定性。",
      "publication_date": "2024-05-18"
    },
    {
      "id": "DOC002",
      "title": "面向异构数据的联邦时间序列异常检测",
      "abstract": "研究针对跨机构数据孤岛、隐私约束和客户端异质性问题，提出联邦异常检测框架。",
      "text": "该框架采用客户端—服务器分解对齐策略，在不共享原始数据的条件下完成模型协同训练，并通过多分辨率变换增强局部语义。",
      "publication_date": "2025-02-11"
    },
    {
      "id": "DOC003",
      "title": "自监督多尺度时序表征学习研究",
      "abstract": "研究利用掩码重建、对比学习和跨尺度一致性约束降低异常标签依赖。",
      "text": "方法通过自监督预训练学习正常模式，并在少量标注条件下完成异常识别。结果表明，该方法在跨数据集迁移中保持较好泛化能力。",
      "publication_date": "2023-10-09"
    },
    {
      "id": "DOC004",
      "title": "边缘设备上的轻量化时序检测模型",
      "abstract": "研究针对复杂模型部署成本高的问题，提出动态通道裁剪与知识蒸馏方法。",
      "text": "模型根据输入难度动态分配计算资源，并将教师模型知识迁移到轻量学生网络，从而降低推理延迟与显存占用。",
      "publication_date": "2025-07-22"
    },
    {
      "id": "DOC005",
      "title": "大语言模型辅助的异常原因解释框架",
      "abstract": "研究将异常片段、设备上下文和维修记录组织为结构化提示，生成异常原因和维护建议。",
      "text": "该框架在异常检测结果基础上引入证据约束与反事实校验，减少无依据解释，并返回来源片段和可信度。",
      "publication_date": "2026-03-16"
    }
  ],
  "batchText": {
    "code": 0,
    "message": "success",
    "data": {
      "tool": "结构化自动综述工具",
      "review_id": "REVIEW_1786704241365",
      "input_type": "texts",
      "topic": "多变量时间序列异常检测",
      "document_count": 5,
      "collection_id": null,
      "cluster_task_id": null,
      "language": "auto",
      "traceability": true,
      "statistics": {
        "research_question_count": 3,
        "method_count": 6,
        "progress_item_count": 6,
        "evidence_sentence_count": 15,
        "time_range": "2023—2026"
      },
      "tree": [
        {
          "question_id": "RQ-01",
          "research_question": "如何在复杂时序数据中同时建模多尺度动态模式与跨变量依赖？",
          "document_count": 4,
          "methods": [
            {
              "method_id": "M-01",
              "method": "多尺度分块与时频特征融合",
              "progress": [
                {
                  "summary": "研究由固定窗口特征逐步发展到自适应多尺度分块，并进一步融合频域信息以提高异常模式分辨能力。",
                  "conclusion": "多尺度表征已成为复杂时序建模的主流路线。",
                  "source_ids": [
                    "DOC001",
                    "DOC002"
                  ]
                }
              ]
            },
            {
              "method_id": "M-02",
              "method": "超图与注意力关系建模",
              "progress": [
                {
                  "summary": "超图结构用于描述变量间高阶关系，注意力机制进一步提升动态依赖建模能力。",
                  "conclusion": "高阶关系建模改善了跨变量耦合表示。",
                  "source_ids": [
                    "DOC001"
                  ]
                }
              ]
            }
          ]
        },
        {
          "question_id": "RQ-02",
          "research_question": "如何应对跨机构数据异质性、隐私约束与标签稀缺问题？",
          "document_count": 3,
          "methods": [
            {
              "method_id": "M-03",
              "method": "联邦学习与客户端对齐",
              "progress": [
                {
                  "summary": "联邦检测由参数平均发展到原型对齐和客户端—服务器分解对齐。",
                  "conclusion": "异质数据条件下的协同稳定性持续提升。",
                  "source_ids": [
                    "DOC002"
                  ]
                }
              ]
            },
            {
              "method_id": "M-04",
              "method": "自监督预训练与一致性约束",
              "progress": [
                {
                  "summary": "掩码重建、对比学习和跨尺度一致性约束降低了对异常标签的依赖。",
                  "conclusion": "自监督学习成为弱标注场景的重要补充。",
                  "source_ids": [
                    "DOC003"
                  ]
                }
              ]
            }
          ]
        },
        {
          "question_id": "RQ-03",
          "research_question": "如何降低模型部署成本并提高异常结果的可解释性？",
          "document_count": 2,
          "methods": [
            {
              "method_id": "M-05",
              "method": "轻量化网络与知识蒸馏",
              "progress": [
                {
                  "summary": "动态通道裁剪和知识蒸馏使复杂时序模型能够部署到边缘设备。",
                  "conclusion": "轻量化路线正在从离线压缩转向动态资源分配。",
                  "source_ids": [
                    "DOC004"
                  ]
                }
              ]
            },
            {
              "method_id": "M-06",
              "method": "大模型辅助异常解释",
              "progress": [
                {
                  "summary": "最新研究融合设备上下文、异常片段和维修记录生成异常原因与维护建议。",
                  "conclusion": "证据约束和反事实校验是降低解释幻觉的关键。",
                  "source_ids": [
                    "DOC005"
                  ]
                }
              ]
            }
          ]
        }
      ],
      "problem_clusters": [
        {
          "cluster_id": "PC-01",
          "label": "多尺度表征与关系建模",
          "document_count": 3
        },
        {
          "cluster_id": "PC-02",
          "label": "弱监督与联邦异常检测",
          "document_count": 2
        },
        {
          "cluster_id": "PC-03",
          "label": "轻量部署与异常解释",
          "document_count": 2
        }
      ],
      "structured_report": {
        "overview": "围绕“多变量时间序列异常检测”，现有研究形成了多尺度表征、跨变量关系建模、联邦与自监督学习、轻量部署及语义解释等技术路线。",
        "sections": [
          {
            "title": "研究问题",
            "content": "核心问题集中在复杂动态模式建模、数据异质性与标签稀缺、部署效率及结果可解释性。"
          },
          {
            "title": "研究方法",
            "content": "主流方法包括多尺度分块、时频融合、超图注意力、联邦对齐、自监督预训练、模型蒸馏和大模型解释。"
          },
          {
            "title": "研究进展",
            "content": "技术路线正从单尺度集中式检测向多尺度、分布式、轻量化和语义解释一体化演进。"
          },
          {
            "title": "趋势与不足",
            "content": "未来仍需解决跨设备泛化、在线自适应、异常因果解释和生成式模型幻觉控制问题。"
          }
        ]
      },
      "trends": {
        "hotspots": [
          {
            "name": "多尺度时频融合",
            "score": 0.94,
            "status": "持续热点"
          },
          {
            "name": "联邦异常检测",
            "score": 0.88,
            "status": "稳定上升"
          },
          {
            "name": "大模型异常解释",
            "score": 0.86,
            "status": "新兴热点"
          },
          {
            "name": "边缘轻量部署",
            "score": 0.79,
            "status": "快速增长"
          }
        ]
      },
      "evidence_index": [
        {
          "document_id": "DOC001",
          "title": "面向多变量时间序列的层次超图建模方法",
          "source_section": "摘要与引言",
          "evidence_excerpt": "研究围绕数据异质性、标签稀缺和解释可信度展开。",
          "supported_nodes": [
            "RQ-01",
            "M-01"
          ]
        },
        {
          "document_id": "DOC002",
          "title": "面向异构数据的联邦时间序列异常检测",
          "source_section": "方法与实验",
          "evidence_excerpt": "本文采用多尺度表示和关系建模提升复杂时序任务性能。",
          "supported_nodes": [
            "RQ-01",
            "M-01"
          ]
        },
        {
          "document_id": "DOC003",
          "title": "自监督多尺度时序表征学习研究",
          "source_section": "摘要与引言",
          "evidence_excerpt": "研究围绕数据异质性、标签稀缺和解释可信度展开。",
          "supported_nodes": [
            "RQ-02"
          ]
        },
        {
          "document_id": "DOC004",
          "title": "边缘设备上的轻量化时序检测模型",
          "source_section": "方法与实验",
          "evidence_excerpt": "本文采用多尺度表示和关系建模提升复杂时序任务性能。",
          "supported_nodes": [
            "RQ-02"
          ]
        },
        {
          "document_id": "DOC005",
          "title": "大语言模型辅助的异常原因解释框架",
          "source_section": "摘要与引言",
          "evidence_excerpt": "研究围绕数据异质性、标签稀缺和解释可信度展开。",
          "supported_nodes": [
            "RQ-03"
          ]
        }
      ]
    },
    "meta": {
      "request_id": "req_review_1786704241365",
      "elapsed_ms": 4380,
      "prototype_notice": "静态原型结果用于展示页面结构和接口字段，不代表真实生成结论。"
    }
  },
  "batchFile": {
    "code": 0,
    "message": "success",
    "data": {
      "tool": "结构化自动综述工具",
      "review_id": "REVIEW_1786704241365",
      "input_type": "files",
      "topic": "多变量时间序列异常检测",
      "document_count": 4,
      "collection_id": null,
      "cluster_task_id": null,
      "language": "auto",
      "traceability": true,
      "statistics": {
        "research_question_count": 3,
        "method_count": 6,
        "progress_item_count": 6,
        "evidence_sentence_count": 12,
        "time_range": "2023—2026"
      },
      "tree": [
        {
          "question_id": "RQ-01",
          "research_question": "如何在复杂时序数据中同时建模多尺度动态模式与跨变量依赖？",
          "document_count": 4,
          "methods": [
            {
              "method_id": "M-01",
              "method": "多尺度分块与时频特征融合",
              "progress": [
                {
                  "summary": "研究由固定窗口特征逐步发展到自适应多尺度分块，并进一步融合频域信息以提高异常模式分辨能力。",
                  "conclusion": "多尺度表征已成为复杂时序建模的主流路线。",
                  "source_ids": [
                    "DOC001",
                    "DOC002"
                  ]
                }
              ]
            },
            {
              "method_id": "M-02",
              "method": "超图与注意力关系建模",
              "progress": [
                {
                  "summary": "超图结构用于描述变量间高阶关系，注意力机制进一步提升动态依赖建模能力。",
                  "conclusion": "高阶关系建模改善了跨变量耦合表示。",
                  "source_ids": [
                    "DOC001"
                  ]
                }
              ]
            }
          ]
        },
        {
          "question_id": "RQ-02",
          "research_question": "如何应对跨机构数据异质性、隐私约束与标签稀缺问题？",
          "document_count": 3,
          "methods": [
            {
              "method_id": "M-03",
              "method": "联邦学习与客户端对齐",
              "progress": [
                {
                  "summary": "联邦检测由参数平均发展到原型对齐和客户端—服务器分解对齐。",
                  "conclusion": "异质数据条件下的协同稳定性持续提升。",
                  "source_ids": [
                    "DOC002"
                  ]
                }
              ]
            },
            {
              "method_id": "M-04",
              "method": "自监督预训练与一致性约束",
              "progress": [
                {
                  "summary": "掩码重建、对比学习和跨尺度一致性约束降低了对异常标签的依赖。",
                  "conclusion": "自监督学习成为弱标注场景的重要补充。",
                  "source_ids": [
                    "DOC003"
                  ]
                }
              ]
            }
          ]
        },
        {
          "question_id": "RQ-03",
          "research_question": "如何降低模型部署成本并提高异常结果的可解释性？",
          "document_count": 2,
          "methods": [
            {
              "method_id": "M-05",
              "method": "轻量化网络与知识蒸馏",
              "progress": [
                {
                  "summary": "动态通道裁剪和知识蒸馏使复杂时序模型能够部署到边缘设备。",
                  "conclusion": "轻量化路线正在从离线压缩转向动态资源分配。",
                  "source_ids": [
                    "DOC004"
                  ]
                }
              ]
            },
            {
              "method_id": "M-06",
              "method": "大模型辅助异常解释",
              "progress": [
                {
                  "summary": "最新研究融合设备上下文、异常片段和维修记录生成异常原因与维护建议。",
                  "conclusion": "证据约束和反事实校验是降低解释幻觉的关键。",
                  "source_ids": [
                    "DOC001"
                  ]
                }
              ]
            }
          ]
        }
      ],
      "problem_clusters": [
        {
          "cluster_id": "PC-01",
          "label": "多尺度表征与关系建模",
          "document_count": 3
        },
        {
          "cluster_id": "PC-02",
          "label": "弱监督与联邦异常检测",
          "document_count": 2
        },
        {
          "cluster_id": "PC-03",
          "label": "轻量部署与异常解释",
          "document_count": 2
        }
      ],
      "structured_report": {
        "overview": "围绕“多变量时间序列异常检测”，现有研究形成了多尺度表征、跨变量关系建模、联邦与自监督学习、轻量部署及语义解释等技术路线。",
        "sections": [
          {
            "title": "研究问题",
            "content": "核心问题集中在复杂动态模式建模、数据异质性与标签稀缺、部署效率及结果可解释性。"
          },
          {
            "title": "研究方法",
            "content": "主流方法包括多尺度分块、时频融合、超图注意力、联邦对齐、自监督预训练、模型蒸馏和大模型解释。"
          },
          {
            "title": "研究进展",
            "content": "技术路线正从单尺度集中式检测向多尺度、分布式、轻量化和语义解释一体化演进。"
          },
          {
            "title": "趋势与不足",
            "content": "未来仍需解决跨设备泛化、在线自适应、异常因果解释和生成式模型幻觉控制问题。"
          }
        ]
      },
      "trends": {
        "hotspots": [
          {
            "name": "多尺度时频融合",
            "score": 0.94,
            "status": "持续热点"
          },
          {
            "name": "联邦异常检测",
            "score": 0.88,
            "status": "稳定上升"
          },
          {
            "name": "大模型异常解释",
            "score": 0.86,
            "status": "新兴热点"
          },
          {
            "name": "边缘轻量部署",
            "score": 0.79,
            "status": "快速增长"
          }
        ]
      },
      "evidence_index": [
        {
          "document_id": "DOC001",
          "title": "面向多变量时间序列的层次超图建模方法",
          "source_section": "摘要与引言",
          "evidence_excerpt": "研究围绕数据异质性、标签稀缺和解释可信度展开。",
          "supported_nodes": [
            "RQ-01",
            "M-01"
          ]
        },
        {
          "document_id": "DOC002",
          "title": "面向异构数据的联邦时间序列异常检测",
          "source_section": "方法与实验",
          "evidence_excerpt": "本文采用多尺度表示和关系建模提升复杂时序任务性能。",
          "supported_nodes": [
            "RQ-01",
            "M-01"
          ]
        },
        {
          "document_id": "DOC003",
          "title": "自监督多尺度时序表征学习研究",
          "source_section": "摘要与引言",
          "evidence_excerpt": "研究围绕数据异质性、标签稀缺和解释可信度展开。",
          "supported_nodes": [
            "RQ-02"
          ]
        },
        {
          "document_id": "DOC004",
          "title": "边缘设备上的轻量化时序检测模型",
          "source_section": "方法与实验",
          "evidence_excerpt": "本文采用多尺度表示和关系建模提升复杂时序任务性能。",
          "supported_nodes": [
            "RQ-02"
          ]
        }
      ]
    },
    "meta": {
      "request_id": "req_review_1786704241365",
      "elapsed_ms": 4380,
      "prototype_notice": "静态原型结果用于展示页面结构和接口字段，不代表真实生成结论。"
    }
  },
  "collection": {
    "code": 0,
    "message": "success",
    "data": {
      "tool": "结构化自动综述工具",
      "review_id": "REVIEW_1786704241365",
      "input_type": "collection",
      "topic": "多变量时间序列异常检测",
      "document_count": 5,
      "collection_id": "COLL_TS_2026",
      "cluster_task_id": null,
      "language": "auto",
      "traceability": true,
      "statistics": {
        "research_question_count": 3,
        "method_count": 6,
        "progress_item_count": 6,
        "evidence_sentence_count": 15,
        "time_range": "2023—2026"
      },
      "tree": [
        {
          "question_id": "RQ-01",
          "research_question": "如何在复杂时序数据中同时建模多尺度动态模式与跨变量依赖？",
          "document_count": 4,
          "methods": [
            {
              "method_id": "M-01",
              "method": "多尺度分块与时频特征融合",
              "progress": [
                {
                  "summary": "研究由固定窗口特征逐步发展到自适应多尺度分块，并进一步融合频域信息以提高异常模式分辨能力。",
                  "conclusion": "多尺度表征已成为复杂时序建模的主流路线。",
                  "source_ids": [
                    "DOC001",
                    "DOC002"
                  ]
                }
              ]
            },
            {
              "method_id": "M-02",
              "method": "超图与注意力关系建模",
              "progress": [
                {
                  "summary": "超图结构用于描述变量间高阶关系，注意力机制进一步提升动态依赖建模能力。",
                  "conclusion": "高阶关系建模改善了跨变量耦合表示。",
                  "source_ids": [
                    "DOC001"
                  ]
                }
              ]
            }
          ]
        },
        {
          "question_id": "RQ-02",
          "research_question": "如何应对跨机构数据异质性、隐私约束与标签稀缺问题？",
          "document_count": 3,
          "methods": [
            {
              "method_id": "M-03",
              "method": "联邦学习与客户端对齐",
              "progress": [
                {
                  "summary": "联邦检测由参数平均发展到原型对齐和客户端—服务器分解对齐。",
                  "conclusion": "异质数据条件下的协同稳定性持续提升。",
                  "source_ids": [
                    "DOC002"
                  ]
                }
              ]
            },
            {
              "method_id": "M-04",
              "method": "自监督预训练与一致性约束",
              "progress": [
                {
                  "summary": "掩码重建、对比学习和跨尺度一致性约束降低了对异常标签的依赖。",
                  "conclusion": "自监督学习成为弱标注场景的重要补充。",
                  "source_ids": [
                    "DOC003"
                  ]
                }
              ]
            }
          ]
        },
        {
          "question_id": "RQ-03",
          "research_question": "如何降低模型部署成本并提高异常结果的可解释性？",
          "document_count": 2,
          "methods": [
            {
              "method_id": "M-05",
              "method": "轻量化网络与知识蒸馏",
              "progress": [
                {
                  "summary": "动态通道裁剪和知识蒸馏使复杂时序模型能够部署到边缘设备。",
                  "conclusion": "轻量化路线正在从离线压缩转向动态资源分配。",
                  "source_ids": [
                    "DOC004"
                  ]
                }
              ]
            },
            {
              "method_id": "M-06",
              "method": "大模型辅助异常解释",
              "progress": [
                {
                  "summary": "最新研究融合设备上下文、异常片段和维修记录生成异常原因与维护建议。",
                  "conclusion": "证据约束和反事实校验是降低解释幻觉的关键。",
                  "source_ids": [
                    "DOC005"
                  ]
                }
              ]
            }
          ]
        }
      ],
      "problem_clusters": [
        {
          "cluster_id": "PC-01",
          "label": "多尺度表征与关系建模",
          "document_count": 3
        },
        {
          "cluster_id": "PC-02",
          "label": "弱监督与联邦异常检测",
          "document_count": 2
        },
        {
          "cluster_id": "PC-03",
          "label": "轻量部署与异常解释",
          "document_count": 2
        }
      ],
      "structured_report": {
        "overview": "围绕“多变量时间序列异常检测”，现有研究形成了多尺度表征、跨变量关系建模、联邦与自监督学习、轻量部署及语义解释等技术路线。",
        "sections": [
          {
            "title": "研究问题",
            "content": "核心问题集中在复杂动态模式建模、数据异质性与标签稀缺、部署效率及结果可解释性。"
          },
          {
            "title": "研究方法",
            "content": "主流方法包括多尺度分块、时频融合、超图注意力、联邦对齐、自监督预训练、模型蒸馏和大模型解释。"
          },
          {
            "title": "研究进展",
            "content": "技术路线正从单尺度集中式检测向多尺度、分布式、轻量化和语义解释一体化演进。"
          },
          {
            "title": "趋势与不足",
            "content": "未来仍需解决跨设备泛化、在线自适应、异常因果解释和生成式模型幻觉控制问题。"
          }
        ]
      },
      "trends": {
        "hotspots": [
          {
            "name": "多尺度时频融合",
            "score": 0.94,
            "status": "持续热点"
          },
          {
            "name": "联邦异常检测",
            "score": 0.88,
            "status": "稳定上升"
          },
          {
            "name": "大模型异常解释",
            "score": 0.86,
            "status": "新兴热点"
          },
          {
            "name": "边缘轻量部署",
            "score": 0.79,
            "status": "快速增长"
          }
        ]
      },
      "evidence_index": [
        {
          "document_id": "DOC001",
          "title": "面向多变量时间序列的层次超图建模方法",
          "source_section": "摘要与引言",
          "evidence_excerpt": "研究围绕数据异质性、标签稀缺和解释可信度展开。",
          "supported_nodes": [
            "RQ-01",
            "M-01"
          ]
        },
        {
          "document_id": "DOC002",
          "title": "面向异构数据的联邦时间序列异常检测",
          "source_section": "方法与实验",
          "evidence_excerpt": "本文采用多尺度表示和关系建模提升复杂时序任务性能。",
          "supported_nodes": [
            "RQ-01",
            "M-01"
          ]
        },
        {
          "document_id": "DOC003",
          "title": "自监督多尺度时序表征学习研究",
          "source_section": "摘要与引言",
          "evidence_excerpt": "研究围绕数据异质性、标签稀缺和解释可信度展开。",
          "supported_nodes": [
            "RQ-02"
          ]
        },
        {
          "document_id": "DOC004",
          "title": "边缘设备上的轻量化时序检测模型",
          "source_section": "方法与实验",
          "evidence_excerpt": "本文采用多尺度表示和关系建模提升复杂时序任务性能。",
          "supported_nodes": [
            "RQ-02"
          ]
        },
        {
          "document_id": "DOC005",
          "title": "大语言模型辅助的异常原因解释框架",
          "source_section": "摘要与引言",
          "evidence_excerpt": "研究围绕数据异质性、标签稀缺和解释可信度展开。",
          "supported_nodes": [
            "RQ-03"
          ]
        }
      ]
    },
    "meta": {
      "request_id": "req_review_1786704241365",
      "elapsed_ms": 4380,
      "prototype_notice": "静态原型结果用于展示页面结构和接口字段，不代表真实生成结论。"
    }
  }
}
