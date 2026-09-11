# -*- coding: utf-8 -*-
"""科研 NER 与专业领域 NER 的 gold 构建（高置信锚点法，与通用 NER 同款）。

research-ner gold：KNOWN_METHOD/DATASET/INSTRUMENT 词表在正文的出现 + 文件名核心主题 TOPIC。
domain-ner gold：医学三篇人工复核的 DISEASE/DRUG/TREATMENT 锚点。
"""
import sys, glob, re, os, json
sys.path.insert(0, '/root/autodl-tmp/semantic_toolkit')
os.chdir('/root/autodl-tmp/semantic_toolkit')
import fitz

files = sorted(glob.glob('/root/autodl-tmp/datasets/ch_papers/*.pdf')) + \
        sorted(glob.glob('/root/autodl-tmp/datasets/papers/*.pdf'))

TOPIC_BY_FILE = {  # 文件名特征 → TOPIC 锚点（人工从标题提炼）
    '场馆': '体育场馆智慧化建设', 'BOPPPS': '护理实习教学', 'AI': 'AI画像',
    '地震动': '地震动记录选取', '长安': '客流协同管控', 'LSTM': '马赫数控制',
    'ResNet': '混凝土搅拌均匀性', 'Transformer': '医院设备', 'WGCNA': '糖尿病肾病',
    '时序行为': '居民行为', '转炉': '转炉炼钢', '泄漏': '泄漏声学识别',
    '核电': '施工图算量', '磁共振': '强直性脊柱炎', '水库': '超标准洪水',
    '骨质疏松': '骨质疏松风险预测', '能量迹': '侧信道攻击', '光伏电站运维': '光伏电站运维',
    '火电厂': '燃烧优化', '铜绿': '感染预测',
}
EXTRA_METHOD = {'协同过滤算法', '主成分分析', '随机森林', '卷积神经网络', '深度学习',
                '机器学习', '余弦退火', '模拟退火算法', '支持向量机', '关联规则',
                '梯度提升', '数据增强', '注意力机制', '模糊PID'}
KNOWN_DATASETS = {'GEO', 'TCGA', 'MIMIC', 'MIMIC-IV', 'ArrayExpress', 'ImageNet', 'GeneMANIA',
                  'TRRUST', 'HAGR', 'KEGG', '地震动记录'}
INSTRUMENTS = {'风洞', '无人机', 'GPU', '虚拟仿真平台'}

DOM_GOLD = {  # 医学三篇人工复核（DISEASE/DRUG/TREATMENT）
    'WGCNA': {'DISEASE': ['糖尿病肾病', '糖尿病', '类风湿关节炎', '终末期肾病'],
              'DRUG': [], 'TREATMENT': ['靶向治疗', '同种异体移植']},
    '骨质疏松': {'DISEASE': ['骨质疏松', '慢性肾脏病', '冠心病', '骨关节炎', '骨质疏松性骨折',
                        '椎体压缩骨折', '骨软化'],
            'DRUG': [], 'TREATMENT': ['血液透析', '器官移植']},
    'BOPPPS': {'DISEASE': [], 'DRUG': [], 'TREATMENT': ['血液透析']},
}

gold_res, gold_dom = {}, {}
for f in files:
    raw = os.path.basename(f)
    name = raw.encode('utf-8', 'replace').decode('utf-8')
    try:
        doc = fitz.open(stream=open(f, 'rb').read(), filetype='pdf')
        body = '\n'.join(p.get_text() for p in doc)
    except Exception:
        body = ''
    REF = re.compile(r'(?:^|\n)\s*#{0,3}\s*(参\s*考\s*文\s*献|References|REFERENCES)\s*[：:．.\s]*(?:\n|$)')
    body = REF.split(body)[0]
    # research gold
    try:
        gbk_name = raw.encode('utf-8', 'surrogateescape').decode('gbk', 'replace')
    except Exception:
        gbk_name = raw
    methods = set()
    for m in list(EXTRA_METHOD) + ['LSTM', 'ResNet', 'Transformer', 'WGCNA', 'XGBoost', 'GBR',
                                   'RF', 'PCA', 'MPC', 'PID', 'BOPPPS', 'YOLOv5', 'U-Net', 'CNN',
                                   'RNN', 'ARIMA', 'LightGBM', 'K-means']:
        if m.isascii():
            if re.search(r'(?<![A-Za-z0-9])' + re.escape(m) + r'(?![A-Za-z0-9])', body):
                methods.add(m)
        elif m in body:
            methods.add(m)
    datasets = sorted(d for d in KNOWN_DATASETS if d in body)
    instruments = sorted(i for i in INSTRUMENTS if i in body)
    topic = next((v for k, v in TOPIC_BY_FILE.items() if k in gbk_name), None)
    gold_res[name] = {'METHOD': sorted(methods), 'DATASET': datasets,
                      'INSTRUMENT': instruments, 'TOPIC': [topic] if topic else []}
    # domain gold（只给医学篇）
    for key, dg in DOM_GOLD.items():
        if key in gbk_name:
            gold_dom[name] = dg

json.dump(gold_res, open('/tmp/ner_eval/gold_research.json', 'w'), ensure_ascii=False, indent=1)
json.dump(gold_dom, open('/tmp/ner_eval/gold_domain.json', 'w'), ensure_ascii=False, indent=1)
n = lambda g, t: sum(len(v.get(t, [])) for v in g.values())
print(f"research gold: METHOD {n(gold_res,'METHOD')} DATASET {n(gold_res,'DATASET')} "
      f"INSTRUMENT {n(gold_res,'INSTRUMENT')} TOPIC {n(gold_res,'TOPIC')}")
print(f"domain gold: {len(gold_dom)} 篇, DISEASE {n(gold_dom,'DISEASE')} "
      f"DRUG {n(gold_dom,'DRUG')} TREATMENT {n(gold_dom,'TREATMENT')}")
