# -*- coding: utf-8 -*-
"""gold v2：修 v1 的两类噪声。
  ① 中文 PERSON 混入标题碎片 → 只收 文件名作者 + 整行人名列表行 + 正文引用作者，
     并剔除与标题互为子串的 token
  ② 英文 PERSON 混入标题大写词 → 语料级停用词（≥5 篇出现的大写词）+ 严格 byline 行
  ③ 中文 ORG 剔除 "以…为中心"类（含 的/与/以 开头）与 年 前缀
"""
import re, json, os, glob, sys, collections
sys.path.insert(0, '/root/autodl-tmp/semantic_toolkit')
os.chdir('/root/autodl-tmp/semantic_toolkit')
import fitz
def extract_bytes(content, name, light=True):
    doc = fitz.open(stream=content, filetype='pdf')
    return '\n'.join(p.get_text() for p in doc)

REF = re.compile(r'(?:^|\n)\s*#{0,3}\s*(参考文献|References|REFERENCES)\s*[：:．.\s]*(?:\n|$)')
CH_CITIES = """北京 天津 上海 重庆 石家庄 太原 呼和浩特 沈阳 长春 哈尔滨 南京 杭州 合肥 福州 南昌 济南 郑州 武汉 长沙 广州 南宁 海口 成都 贵阳 昆明 拉萨 西安 兰州 西宁 银川 乌鲁木齐
辽宁 吉林 黑龙江 河北 山西 陕西 甘肃 青海 山东 江苏 浙江 安徽 福建 江西 河南 湖北 湖南 广东 海南 四川 云南""".split()
EN_PLACES = set("""China USA United States UK England France Germany Japan Korea India Canada Australia Netherlands Switzerland Spain Italy Sweden Singapore Beijing Shanghai Tokyo Seoul Paris London Boston New York""".split())

files = sorted(glob.glob('/root/autodl-tmp/datasets/ch_papers/*.pdf')) + \
        sorted(glob.glob('/root/autodl-tmp/datasets/papers/*.pdf'))

# 预扫一遍：英文语料大写词频率（≥5 篇 → 停用，如 Anomalies/Distance）
en_cap_freq = collections.Counter()
en_texts = {}
texts = {}
for f in files:
    name = os.path.basename(f).encode('utf-8', 'replace').decode('utf-8')
    try:
        t = extract_bytes(open(f, 'rb').read(), os.path.basename(f), light=True)
    except Exception:
        t = ''
    print('.', end='', flush=True)
    texts[name] = t
    if not re.search(r'[一-鿿]', t[:2000]):
        en_texts[name] = t
        for w in set(re.findall(r'\b[A-Z][a-z]{2,}\b', t[:4000])):
            en_cap_freq[w] += 1
CAP_STOP = {w for w, n in en_cap_freq.items() if n >= 5}
CAP_STOP |= {'University', 'Institute', 'College', 'Department', 'School', 'Laboratory',
             'Abstract', 'Introduction', 'Keywords', 'Email', 'Corresponding', 'Paper', 'Study'}

def gold_one(name, raw_name, text):
    body = REF.split(text)[0]
    lines = [l.strip() for l in body.split('\n') if l.strip()]
    title = re.sub(r'\.pdf$', '', raw_name)
    title_core = re.sub(r'^_+', '_', title.split('_')[0] if '_' in title else title)
    persons, orgs, locs = set(), set(), set()
    is_ch = bool(re.search(r'[一-鿿]', body[:3000]))

    if is_ch:
        # ① 文件名尾作者（_佟志刚.pdf）——文件名是 GBK，须 surrogateescape 还原
        try:
            gbk_name = raw_name.encode('utf-8', 'surrogateescape').decode('gbk', 'replace')
        except Exception:
            gbk_name = raw_name
        m = re.search(r'_([一-鿿]{2,4})\.pdf$', gbk_name)
        if m:
            persons.add(m.group(1))
        # ② 整行人名列表：≥2 个 2-4 字名；先去 */†/上标数字、折叠 CJK 间空格
        for l in lines[:18]:
            l2 = re.sub(r'[*†‡#\d]', '', l)
            l2 = re.sub(r'(?<=[一-鿿])\s+(?=[一-鿿])', '', l2)
            if len(l2) > 34 or re.search(r'[A-Za-z摘要关键词基金项目收稿日期]', l2):
                continue
            toks = re.split(r'[,，、\s]+', l2)
            toks = [t for t in toks if t]
            if len(toks) >= 2 and all(re.fullmatch(r'[一-鿿]{2,4}', t) for t in toks):
                persons.update(toks)
        # ③ 正文引用作者
        _bad_end = ('法', '模型', '算法', '方法', '技术', '网络', '系统', '指标', '数据',
                    '特征', '策略', '框架', '研究', '分析', '结果', '方案', '结构', '过程', '性能', '模型')
        for m in re.finditer(r'([一-鿿]{2,4})(?:等\s*人|等\s*[\[（(]|等基于|等提出|等研究|等构建|等开发|等采用|等利用|等将|等针对)', body):
            tok = m.group(1)
            if not tok.endswith(_bad_end):
                persons.add(tok)
        # 标题碎片剔除：与文件名主体互为子串
        persons = {p for p in persons if p not in title and title.find(p) < 0 or not is_ch}
        persons = {p for p in persons if p not in title_core}
        # ④ 机构：≥4 字，含后缀，剔 以/年 开头与含 的/与/及
        for m in re.finditer(r'([一-鿿]{2,18}(?:大学|学院|医院|研究所|研究院|公司|实验室|中心))', body):
            s = m.group(1)
            if len(s) >= 4 and not re.match(r'^(以|年|与|和)', s) and not re.search(r'[的与及]', s[:-2]):
                orgs.add(s)
        for c in CH_CITIES:
            if c in body:
                locs.add(c)
    else:
        pre_abs = re.split(r'(?i)\babstract\b', body)[0]
        # byline 行：逗号分块，每块 1-3 个首字母大写词，无停用词，≥2 块
        _aff_words = ('University', 'Institute', 'College', 'Lab', 'Inc', 'USA', 'China',
                      'France', 'Germany', 'UK', 'Corporation', 'Department', 'School',
                      'Academy', 'Center', 'CNRS', 'Inria', 'Japan', 'Korea', 'Australia')
        for l in pre_abs.split('\n'):
            l = re.sub(r'[\d*†‡]', '', l).strip().rstrip(',')
            if not l or '@' in l or len(l) > 90 or ',' not in l:
                continue
            chunks = [c.strip() for c in l.split(',')]
            c0 = chunks[0].split()
            # 首块 = 1~3 个姓名词（Title/全大写均可）；行内其余块须含单位/国家信号
            # （或块数≥3），否则是正文句不是 byline
            if not (1 <= len(c0) <= 3) or not all(
                    re.fullmatch(r"[A-Z][A-Za-z\-']+", t) and t not in CAP_STOP for t in c0):
                continue
            rest = ' '.join(chunks[1:])
            if any(w in rest for w in _aff_words) or len(chunks) >= 3:
                persons.update(c0)
        for m in re.finditer(r'([A-Z][A-Za-z]*(?:\s+(?:of|and|for)\s+|\s+[A-Z][A-Za-z]*\s*){0,6}(?:University|Institute|College|Laboratory|Inc\.|Corporation|Company|Hospital))', body):
            s = re.sub(r'\s+', ' ', m.group(1)).strip()
            if 6 < len(s) < 70 and not s.endswith((' of', ' and', ' for')):
                orgs.add(s)
        for w in EN_PLACES:
            if re.search(r'\b' + w + r'\b', body):
                locs.add(w)
    return {"PERSON": sorted(persons), "ORGANIZATION": sorted(orgs), "LOCATION": sorted(locs)}

gold = {}
for f in files:
    raw_name = os.path.basename(f)
    name = raw_name.encode('utf-8', 'replace').decode('utf-8')
    gold[name] = gold_one(name, raw_name, texts.get(name, ''))
json.dump(gold, open('/tmp/ner_eval/gold.json', 'w'), ensure_ascii=False, indent=1)
np_ = sum(len(v.get('PERSON', [])) for v in gold.values())
no_ = sum(len(v.get('ORGANIZATION', [])) for v in gold.values())
nl_ = sum(len(v.get('LOCATION', [])) for v in gold.values())
print(f"gold v2: PERSON {np_} ORG {no_} LOC {nl_}")
