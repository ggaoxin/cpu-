"""文档解析器 v3：从 MinerU Markdown 解析结构化文档，提取一级/二级/三级标题。

支持三种文档类型：
- 中文论文：# 标题 / 摘要：/ 关键词：/ ## 章节标题 / 参考文献
- 英文论文：# Title / ## Abstract / ## 1. Introduction / References
- 基金项目：## 项目名 / 表单字段 / 报告章节

输出结构化 JSON（含三级标题及字数）：
  {
    "doc_type": "zh_paper|en_paper|fund_project",
    "title": "...",
    "authors": "...",
    "abstract": "...",
    "keywords": ["...", ...],
    "sections": [{"heading": "...", "level": 1|2|3, "content": "...", "char_count": N}],
    "references": ["...", ...],
    "figures": [{"caption": "..."}],
    "tables": [{"caption": "..."}],
    "full_text": "原始全文"
  }
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


def extract_abstract_text(text: str, doc_type: str = "zh_paper") -> str:
    """结构化摘要段提取（模块级，供语步识别/关键词识别等管线复用）。

    中文：[【（]?摘要[】）]?[:：]? 到 关键词/中图分类号/引言 等边界；
    英文：## Abstract（markdown 标题）、Abstract:、ABSTRACT 到 Keywords/Introduction 边界。
    提取不到返回空串（调用方据此回退全文路径）。
    """
    full = text
    if doc_type == 'zh_paper':
        m = re.search(r'[\[【（(]?\s*摘\s*要\s*[\]】）)]?\s*[:：]?\s*(.+?)(?=关键词|中图分类号|文献标识码|文献标志码|文章编号|Abstract|ABSTRACT|引言|0\s*引|^##)',
                      full, re.DOTALL)
        if m:
            return m.group(1).strip()
    m = re.search(r'##\s*(?:Abstract|ABSTRACT)[^\n]*\n\s*(.+?)(?=\n##\s|\n#\s|$)', full, re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(r'(?:^|\n)Abstract\s*[.。:：]?\s*(.+?)(?=Keywords|Index Terms|Introduction|1\.|^##|$)', full, re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(r'(?:^|\n)ABSTRACT\s*[.。:：]?\s*(.+?)(?=Keywords|Index Terms|1\s+INTRODUCTION|^##|$)', full, re.DOTALL)
    if m:
        return m.group(1).strip()
    return ''


class DocumentParser:
    """从 MinerU Markdown 解析结构化文档。"""

    HEADING_RE = re.compile(r'^(#{1,6})\s+(.+)$')
    JOURNAL_COVER_RE = re.compile(r'^《.+》网络首发论文')
    # 摘要行内标志：兼容「摘要」「摘 要」「摘要:」及 CNKI 网络首发等带括号前缀「[摘要]」「【摘要】」「（摘要）」
    INLINE_ABSTRACT_RE = re.compile(
        r'^[\[【（(]?\s*(?:摘\s*要|Abstract|ABSTRACT)\s*[\]】）)]?\s*[:：]?\s*(.+)$')
    FUND_MARKERS = ['国家自然科学基金', '资助项目', '项目批准号', '依托单位', '负责人']

    FUND_TEMPLATE = [
        (1, '项目摘要'), (1, '结题摘要'),
        (1, '（一）结题部分'),
        (2, '1. 研究计划执行情况概述'), (2, '2. 研究工作主要进展、结果和影响'),
        (2, '3. 研究人员的合作与分工'), (2, '4. 国内外学术合作交流等情况'),
        (2, '5. 存在的问题、建议及其他需要说明的情况'),
        (1, '（二）成果部分'),
        (2, '1. 项目取得成果的总体情况'), (2, '2. 项目成果转化及应用情况'),
        (2, '3. 人才培养情况'), (2, '4. 其他需要说明的成果'),
        (2, '5. 项目成果科普性介绍或展示网站'),
        (1, '研究成果目录'),
        (1, '附表：研究成果统计数据表'),
        (1, '签字及审核意见表'),
    ]
    _glm = None

    def set_glm(self, glm_client):
        self._glm = glm_client

    # ------------------------------------------------------------------ #
    # 公共接口
    # ------------------------------------------------------------------ #
    def parse(self, md_path: str | Path) -> Dict[str, Any]:
        md_path = Path(md_path)
        text = md_path.read_text(encoding='utf-8')
        return self.parse_text(text, md_path)

    @staticmethod
    def _strip_tags(text: str) -> str:
        """去掉 MinerU 产出的 HTML 标签（<sup>/<sub> 等），保留纯文本。"""
        if not text:
            return ''
        text = re.sub(r'<sup>\s*(\[?\d+(?:[-,–]\d+)*\]?)\s*</sup>', '', text)
        text = re.sub(r'<sub>\s*(\[?\d+(?:[-,–]\d+)*\]?)\s*</sub>', '', text)
        text = re.sub(r'<[^>]+>', '', text)
        return text

    def parse_content_list(self, content_list_path: str | Path) -> Dict[str, Any]:
        """从 MinerU content_list.json 结构化提取标题/摘要/关键词。

        比 MD 正则准：MinerU 已做版面识别，content_list 块带 type/text_level，
        可直接用 text_level==1 定位标题、用 type 过滤页眉/页脚/页码块。
        块字段：type(text/header/footer/page_number/...)、text、text_level(1/2/None)、page_idx。
        """
        try:
            blocks = json.loads(Path(content_list_path).read_text(encoding='utf-8'))
        except Exception:  # noqa: BLE001
            return {}
        return self.parse_content_list_blocks(blocks)

    def parse_content_list_blocks(self, blocks: list) -> Dict[str, Any]:
        """从已解析的 content_list blocks 数组结构化提取标题/摘要/关键词。

        供 HTTP 模式直接喂 mineru-api 返回的 content_list（无需落盘读文件）。
        块字段：type(text/header/footer/page_number/...)、text、text_level(1/2/None)、page_idx。
        """
        if not isinstance(blocks, list):
            return {}

        # 过滤页眉/页脚/页码块（MinerU 版面识别的核心优势，pdfplumber 做不到）
        SKIP_TYPES = {'header', 'footer', 'page_number'}
        body = [b for b in blocks if b.get('type') not in SKIP_TYPES]

        # 标题：text_level==1 的 text 块（第1个中文标题，第2个英文标题）
        title, en_title = '', ''
        title_count = 0
        for b in body:
            if b.get('type') == 'text' and b.get('text_level') == 1:
                t = self._strip_tags(b.get('text', '') or '').strip()
                if not t:
                    continue
                title_count += 1
                if title_count == 1:
                    title = t
                elif title_count == 2:
                    en_title = t
                else:
                    break

        # 摘要：text 含「摘 要」/「Abstract」标志，去标志词前缀，中英分别取
        abstract_zh, abstract_en = '', ''
        for b in body:
            if b.get('type') != 'text':
                continue
            t = (b.get('text', '') or '').strip()
            if not t:
                continue
            m = re.match(r'^[\[【（(]?\s*摘\s*要\s*[\]】）)]?\s*[:：]?\s*(.+)$', t, re.DOTALL)
            if m and not abstract_zh:
                abstract_zh = self._strip_tags(m.group(1)).strip()
                continue
            m = re.match(r'^(?:Abstract|ABSTRACT)\s*[:：.。]?\s*(.+)$', t, re.DOTALL)
            if m and not abstract_en:
                abstract_en = self._strip_tags(m.group(1)).strip()

        # 关键词：复用 _extract_keywords 切分逻辑，中英分别取
        keywords_zh, keywords_en = [], []
        for b in body:
            if b.get('type') != 'text':
                continue
            t = (b.get('text', '') or '').strip()
            if not re.match(r'^[\[【（(]?\s*(?:关键词|Key\s*words|Keywords|KEYWORDS|Index\s*Terms)', t):
                continue
            kws = self._extract_keywords(t)
            if not kws:
                continue
            if re.match(r'^[\[【（(]?\s*关键词', t) and not keywords_zh:
                keywords_zh = kws
            elif not keywords_en:
                keywords_en = kws

        abstract = abstract_zh or abstract_en
        keywords = keywords_zh or keywords_en

        # doc_type 推断
        ref_title = title or en_title
        if ref_title:
            cn = len(re.findall(r'[一-鿿]', ref_title))
            en = len(re.findall(r'[a-zA-Z]', ref_title))
            doc_type = 'en_paper' if en > cn * 2 else 'zh_paper'
        else:
            doc_type = 'unknown'

        return {
            'doc_type': doc_type,
            'title': title,
            'en_title': en_title,
            'authors': '',
            'abstract': abstract,
            'abstract_zh': abstract_zh,
            'abstract_en': abstract_en,
            'keywords': keywords,
            'keywords_zh': keywords_zh,
            'keywords_en': keywords_en,
            'sections': [],
            'full_text': '\n'.join(self._strip_tags(b.get('text', '') or '')
                                   for b in body if (b.get('text', '') or '').strip()),
            '_source': 'content_list',
        }

    def parse_text(self, text: str, md_path: str | Path | None = None) -> Dict[str, Any]:
        """从 Markdown 文本直接解析（parse 的文本版本，供上游已持有文本时调用）。"""
        doc_type = self._detect_type(text)
        if doc_type == 'fund_project':
            return self._parse_fund(text, md_path)
        return self._parse_paper(text, doc_type)

    def _detect_type(self, text: str) -> str:
        fund_score = sum(1 for m in self.FUND_MARKERS if m in text[:3000])
        if fund_score >= 2:
            return 'fund_project'
        head = text[:1000]
        en_chars = len(re.findall(r'[a-zA-Z]', head))
        cn_chars = len(re.findall(r'[一-鿿]', head))
        if en_chars > cn_chars * 2:
            return 'en_paper'
        return 'zh_paper'

    # ------------------------------------------------------------------ #
    # 论文解析（中文/英文）
    # ------------------------------------------------------------------ #
    def _parse_paper(self, text: str, doc_type: str) -> Dict[str, Any]:
        lines = text.split('\n')

        # 标题
        title = ''
        title_line_idx = -1
        for i, line in enumerate(lines):
            m = self.HEADING_RE.match(line.strip())
            if m and m.group(1) == '#':
                heading = m.group(2).strip()
                if not self.JOURNAL_COVER_RE.match(heading):
                    title = re.sub(r'<[^>]+>', '', heading).strip()
                    title_line_idx = i
                    break
        if not title:
            for line in lines[:10]:
                stripped = line.strip()
                if stripped and not stripped.startswith('#') and not stripped.startswith('!') and \
                   not self.JOURNAL_COVER_RE.match(stripped) and len(stripped) > 5:
                    title = stripped
                    break

        # 作者
        authors = ''
        if title_line_idx >= 0:
            for i in range(title_line_idx + 1, min(title_line_idx + 5, len(lines))):
                line = lines[i].strip()
                if line and not line.startswith('#') and not line.startswith('!') and \
                   not line.startswith('<') and len(line) > 2:
                    authors = line
                    break

        abstract = self._extract_abstract(text, doc_type)
        keywords = self._extract_keywords(text)
        sections = self._extract_sections_v3(lines, doc_type)
        references = self._extract_references(text)
        figures = [{'caption': m.group(0)} for m in re.finditer(r'^(?:图|Figure|Fig\.?)\s*\d+', text, re.MULTILINE)]
        tables = [{'caption': m.group(0)} for m in re.finditer(r'^(?:表|Table|Tab\.?)\s*\d+', text, re.MULTILINE)]

        return {
            'doc_type': doc_type, 'title': title, 'authors': authors,
            'abstract': abstract, 'keywords': keywords,
            'sections': sections, 'references': references,
            'figures': figures, 'tables': tables, 'full_text': text,
        }

    def _extract_sections_v3(self, lines: List[str], doc_type: str) -> List[Dict[str, Any]]:
        """提取章节（v3：L1-L3按标准 + 超阈值章节自适应向下提取L4+）。"""
        # 第一步：按 ## 标题提取所有章节块（不丢任何标题）
        raw_sections = self._extract_all_headings(lines, doc_type)

        # 第二步：自适应拆分——超过阈值的章节，从其内容中提取子标题
        threshold = 4000  # 超过4000字的章节触发向下提取
        result = []
        for sec in raw_sections:
            if sec['char_count'] > threshold and sec['level'] < 6:
                # 尝试从内容中提取子标题
                sub_sections = self._extract_sub_headings(sec, doc_type)
                if sub_sections:
                    result.extend(sub_sections)
                else:
                    result.append(sec)  # 无法拆分，保留原样
            else:
                result.append(sec)
        return result

    def _extract_all_headings(self, lines: List[str], doc_type: str) -> List[Dict[str, Any]]:
        """提取所有 ## 标题，按内容模式归一化为L1-L3，未匹配的自动降级为L4+。"""
        sections = []
        current_heading = ''
        current_level = 0
        current_content: List[str] = []
        title_seen = False
        last_norm_level = 0  # 上一个归一化级别，用于自适应降级

        for line in lines:
            stripped = line.strip()

            # 行内摘要升级为独立L1
            inline_abs = self.INLINE_ABSTRACT_RE.match(stripped)
            if inline_abs and not current_heading:
                if current_heading:
                    self._append_section(sections, current_heading, current_level, current_content)
                abs_type = '摘要' if '摘' in stripped else 'Abstract'
                current_heading = abs_type
                current_level = 1
                current_content = [inline_abs.group(1)]
                last_norm_level = 1
                continue

            m = self.HEADING_RE.match(stripped)
            if m:
                heading = m.group(2).strip()
                raw_level = len(m.group(1))

                # 跳过文档标题和期刊封面
                if raw_level == 1 and not title_seen:
                    title_seen = True
                    continue
                if self.JOURNAL_COVER_RE.match(heading):
                    continue

                # 归一化级别
                norm_level = self._normalize_level(heading, doc_type)

                if norm_level is None:
                    # 未匹配标准模式 → 自适应降级：比上一个标题深一级
                    if last_norm_level > 0:
                        norm_level = last_norm_level + 1
                    else:
                        norm_level = 2
                if norm_level > 6:
                    norm_level = 6  # 最大6级

                if current_heading:
                    self._append_section(sections, current_heading, current_level, current_content)
                current_heading = heading
                current_level = norm_level
                last_norm_level = norm_level
                current_content = []
            elif current_heading:
                current_content.append(line)

        if current_heading:
            self._append_section(sections, current_heading, current_level, current_content)
        return sections

    def _extract_sub_headings(self, parent_section: Dict, doc_type: str) -> List[Dict]:
        """从大章节内容中提取子标题，拆分为更小的块。

        扫描内容中的 ## 标题和文本模式子标题（一、/（一）/1./1.1.1 等）。
        """
        content = parent_section['content']
        parent_level = parent_section['level']
        parent_heading = parent_section['heading']

        lines = content.split('\n')
        sub_sections = []
        current_sub_heading = parent_heading  # 第一个块用父标题（前面无子标题的内容）
        current_sub_level = parent_level + 1
        current_content: List[str] = []
        found_any_sub = False

        # 子标题模式（按优先级）
        sub_patterns = [
            (re.compile(r'^##\s+(.+)'), None),  # ## 标题（MinerU输出）
            (re.compile(r'^[一二三四五六七八九十]+[、.．]\s*(.+)'), None),  # 一、xxx
            (re.compile(r'^[（(][一二三四五六七八九十]+[)）]\s*(.+)'), None),  # （一）xxx
            (re.compile(r'^\d+\.\s+(.+)'), None),  # 1. xxx（注意不匹配 1.1.）
            (re.compile(r'^[（(]\d+[)）]\s*(.+)'), None),  # （1）xxx
        ]

        for line in lines:
            stripped = line.strip()
            matched = False

            # 先检查 ## 标题
            m = self.HEADING_RE.match(stripped)
            if m:
                sub_heading = m.group(2).strip()
                if current_content or found_any_sub:
                    self._append_section(sub_sections, current_sub_heading, current_sub_level, current_content)
                current_sub_heading = sub_heading
                current_sub_level = parent_level + 1
                current_content = []
                found_any_sub = True
                continue

            # 检查文本模式子标题（仅在未找到 ## 标题时）
            if not found_any_sub:
                for pattern, _ in sub_patterns[1:]:  # 跳过 ## 标题（已处理）
                    if pattern.match(stripped) and len(stripped) < 100:
                        if current_content and len('\n'.join(current_content).strip()) > 50:
                            self._append_section(sub_sections, current_sub_heading, current_sub_level, current_content)
                        current_sub_heading = stripped
                        current_sub_level = parent_level + 1
                        current_content = []
                        found_any_sub = True
                        matched = True
                        break
                if matched:
                    continue

            current_content.append(line)

        # 最后一块
        if current_content:
            if found_any_sub:
                self._append_section(sub_sections, current_sub_heading, current_sub_level, current_content)
            else:
                # 没找到子标题，返回原章节
                return [parent_section]

        # 如果拆分后的块仍超过阈值，递归拆分
        threshold = 4000
        final = []
        for sec in sub_sections:
            if sec['char_count'] > threshold and sec['level'] < 6:
                deeper = self._extract_sub_headings(sec, doc_type)
                final.extend(deeper)
            else:
                final.append(sec)
        return final if final else [parent_section]

    @staticmethod
    def _append_section(sections, heading, level, content):
        text = '\n'.join(content).strip()
        # 清理 HTML 表格（实验数据不算正文字数），保留换行结构
        text_clean = re.sub(r'<table>.*?</table>', '\n', text, flags=re.DOTALL)
        text_clean = re.sub(r'<[^>]+>', '', text_clean)  # 去其他HTML标签
        text_clean = re.sub(r'[ \t]+', ' ', text_clean)  # 合并行内多余空格（保留换行）
        text_clean = re.sub(r'\n{3,}', '\n\n', text_clean)  # 压缩多余空行
        text_clean = text_clean.strip()
        sections.append({
            'heading': heading, 'level': level,
            'content': text_clean, 'char_count': len(text_clean),
        })

    def _normalize_level(self, heading: str, doc_type: str) -> Optional[int]:
        """归一化为1/2/3级。"""
        h = heading.strip()

        # L1 关键词
        l1_keywords = ['摘要', 'Abstract', 'ABSTRACT', '引言', 'Introduction', 'INTRODUCTION',
                       '参考文献', 'References', 'REFERENCES', '结语', '结论', 'Conclusion',
                       'CONCLUSION', '致谢', 'Acknowledgement', 'Acknowledgments',
                       '附录', 'Appendix', 'APPENDIX', 'Supplementary']
        if any(h == kw or h.startswith(kw) for kw in l1_keywords):
            return 1

        if doc_type == 'zh_paper':
            # L3：X.X.X（1.2.1）或 （N）数字括号
            if re.match(r'^\d+\.\d+\.\d+', h):
                return 3
            if re.match(r'^[（(]\d+[)）]', h):
                return 3
            # L1：X、 / X. / X空格 / 一、
            if re.match(r'^\d+[、.．\s]+\D', h):
                return 1
            if re.match(r'^[一二三四五六七八九十]+[、.．]', h):
                return 1
            # L2：X.X / （一）
            if re.match(r'^\d+\.\d+', h):
                return 2
            if re.match(r'^[（(][一二三四五六七八九十]+[)）]', h):
                return 2
            if len(h) < 25 and not re.match(r'^\d', h):
                return 1
            return 2

        if doc_type == 'en_paper':
            # L3：N.N.N 或 A.1.1
            if re.match(r'^\d+\.\d+\.\d+', h):
                return 3
            if re.match(r'^[A-Z]\.\d+\.\d+', h):
                return 3
            # L2：N.N. 或 A.1
            if re.match(r'^\d+\.\d+\.', h):
                return 2
            if re.match(r'^[A-Z]\.\d+', h):
                return 2
            # L1：N. Title
            if re.match(r'^\d+\.\s+[A-Z]', h):
                return 1
            if re.match(r'^[A-Z]\s+', h):
                return 1
            if len(h) < 30 and not re.match(r'^\d', h):
                return 1
            return 2
        return 2

    def _extract_abstract(self, text: str, doc_type: str) -> str:
        return extract_abstract_text(text, doc_type)

    def _extract_keywords(self, text: str) -> List[str]:
        m = re.search(r'(?:##\s*)?[\[【（(]?\s*(?:关键词|Key\s*words|Keywords|KEYWORDS|Index Terms)\s*[\]】）)]?\s*[:：—\-]?\s*\n?(.+)', text)
        if not m:
            return []
        kw_str = m.group(1).strip()
        kw_str = re.split(r'(?:中图分类号|文献标识码|文献标志码|文章编号|doi|DOI|Abstract|ABSTRACT|^#|\n##)', kw_str)[0]
        if re.search(r'[;；、，,]', kw_str):
            kws = re.split(r'[;；、，,]+', kw_str)
        else:
            kws = kw_str.split()
        result = []
        for k in kws:
            k = k.strip()
            if not k or len(k) < 2:
                continue
            if re.match(r'^(?:中图|文献|文章|doi|DOI|\d+\.?\d*$)', k):
                continue
            k = re.sub(r'<[^>]+>', '', k).strip()
            if k and len(k) >= 2:
                result.append(k)
        return result

    def _extract_references(self, text: str) -> List[str]:
        m = re.search(r'^#{1,3}\s*(?:参考文献|References|REFERENCES)', text, re.MULTILINE)
        if not m:
            return []
        ref_text = text[m.start():]
        ref_lines = ref_text.split('\n')[1:]
        refs, current = [], ''
        for line in ref_lines:
            stripped = line.strip()
            if not stripped:
                if current:
                    refs.append(current.strip())
                    current = ''
                continue
            if re.match(r'^\[?\d+[\].]', stripped):
                if current:
                    refs.append(current.strip())
                current = stripped
            else:
                current += ' ' + stripped
        if current:
            refs.append(current.strip())
        return refs

    # ------------------------------------------------------------------ #
    # 基金项目解析
    # ------------------------------------------------------------------ #
    def _parse_fund(self, text: str, md_path: str | Path | None = None) -> Dict[str, Any]:
        lines = text.split('\n')

        # 标题
        title = ''
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('#') and '国家自然科学基金' not in stripped and '资助项目' not in stripped:
                m = self.HEADING_RE.match(stripped)
                if m:
                    heading = m.group(2).strip()
                    if '项目名称' not in heading and len(heading) > 3:
                        title = heading
                        break
        if not title:
            m = re.search(r'项目名称\s*[:：]\s*(.+)', text)
            if m:
                title = m.group(1).strip()

        # 表单
        form_fields = {}
        for field in ['项目批准号', '申请代码', '负责人', '依托单位', '资助类别', '电子邮件', '电话']:
            m = re.search(rf'{field}\s*[:：]\s*(.+)', text)
            if m:
                form_fields[field] = m.group(1).strip()

        # 摘要+关键词（从表格提取）
        project_abstract_zh = self._clean_text(
            self._extract_from_table(text, r'项目摘要.*?中文摘要\s*[:：]?\s*(.+?)(?:Abstract|英文摘要)', ''))
        project_abstract_en = self._clean_text(
            self._extract_from_table(text, r'项目摘要.*?Abstract\s*[:：]?\s*(.+?)(?:关键词|Keywords|NSFC)', ''))
        completion_abstract_zh = self._clean_text(
            self._extract_from_table(text, r'结题摘要.*?中文摘要.*?[:：]\s*(.+?)(?=Abstract|#|$)', ''))
        completion_abstract_en = self._clean_text(
            self._extract_from_table(text, r'结题摘要.*?Abstract.*?[:：]\s*(.+?)(?=关键词|Keywords|#|$)', ''))

        keywords_zh, keywords_en = [], []
        for m in re.finditer(r'关键词\s*（用分号分开）\s*[:：]\s*([^<\n]+?)(?:\s*Keywords|<|$)', text):
            keywords_zh.extend([k.strip() for k in re.split(r'[;；]', m.group(1)) if k.strip()])
        for m in re.finditer(r'Keywords\s*\(separated by;?\)\s*[:：]\s*([^<\n]+?)(?:<|$)', text):
            keywords_en.extend([k.strip() for k in re.split(r'[;；]', m.group(1)) if k.strip()])
        keywords_zh = list(dict.fromkeys(keywords_zh))
        keywords_en = list(dict.fromkeys(keywords_en))

        # 章节（L1/L2/L3 + 自适应拆分大章节）
        sections = self._extract_fund_sections(lines)
        # 自适应拆分：超过阈值的章节向下提取子标题
        threshold = 4000
        split_sections = []
        for sec in sections:
            if sec.get('char_count', len(sec.get('content', ''))) > threshold and sec['level'] < 6:
                sub = self._extract_sub_headings(sec, 'fund_project')
                split_sections.extend(sub)
            else:
                split_sections.append(sec)
        # 过滤字数过少的章节（空标题壳/纯表格/无实际内容）
        min_chars = 50
        sections = [s for s in split_sections if s.get('char_count', 0) >= min_chars]

        # 补充虚拟章节
        has_project_abstract = any(s['heading'] == '项目摘要' for s in sections)
        if not has_project_abstract and project_abstract_zh:
            sections.insert(0, {'heading': '项目摘要', 'level': 1, 'content': project_abstract_zh, 'char_count': len(project_abstract_zh)})
        has_signoff = any('签字' in s['heading'] for s in sections)
        if not has_signoff and '项目负责人承诺' in text:
            sections.append({'heading': '签字及审核意见表', 'level': 1, 'content': '', 'char_count': 0})
        has_appendix = any('附表' in s['heading'] for s in sections)
        if not has_appendix:
            m = re.search(r'附表[：:]\s*研究成果统计数据表', text)
            if m:
                sections.append({'heading': '附表：研究成果统计数据表', 'level': 1, 'content': '', 'char_count': 0})

        # LLM 兜底
        missing = self._check_fund_missing(sections)
        if missing and self._glm:
            llm_sections = self._llm_find_missing_sections(text, missing)
            for ls in llm_sections:
                ls_key = ls['heading'][:15]
                if any(ls_key in s['heading'][:15] for s in sections):
                    continue
                parent_l1 = self._find_parent_l1(ls['heading'])
                insert_pos = len(sections)
                for i, s in enumerate(sections):
                    if s['level'] == 1 and parent_l1 and parent_l1 in s['heading']:
                        j = i + 1
                        while j < len(sections) and sections[j]['level'] >= 2:
                            j += 1
                        insert_pos = j
                        break
                ls['char_count'] = len(ls.get('content', ''))
                sections.insert(insert_pos, ls)

        # 用 content_list.json 给章节附页码（文本位置溯源）
        if md_path is not None:
            self._attach_pages(sections, md_path)
        abstract = completion_abstract_zh or project_abstract_zh
        return {
            'doc_type': 'fund_project', 'title': title,
            'authors': form_fields.get('负责人', ''),
            'abstract': abstract, 'keywords': keywords_zh or keywords_en,
            'sections': sections, 'references': [], 'figures': [], 'tables': [],
            'form_fields': form_fields,
            'project_abstract_zh': project_abstract_zh, 'project_abstract_en': project_abstract_en,
            'completion_abstract_zh': completion_abstract_zh, 'completion_abstract_en': completion_abstract_en,
            'keywords_zh': keywords_zh, 'keywords_en': keywords_en,
            'full_text': text,
        }

    def _attach_pages(self, sections: List[Dict[str, Any]], md_path) -> None:
        """从 mineru content_list.json 提取每个章节的页码（1-based），附到 section['pages']。"""
        md_path = Path(md_path)
        cl_path = md_path.parent / f"{md_path.stem}_content_list.json"
        if not cl_path.exists():
            return
        try:
            cl = json.loads(cl_path.read_text(encoding='utf-8'))
        except Exception:  # noqa: BLE001
            return
        # 标题序列：(text, page_idx, block_idx)
        titles = [(b.get('text', '').strip(), b.get('page_idx', -1), i)
                  for i, b in enumerate(cl)
                  if b.get('type') == 'text' and b.get('text_level') in (1, 2, 3)]
        for sec in sections:
            heading = sec.get('heading', '').strip()
            match = None
            for ti, (t, _, _) in enumerate(titles):
                if heading and (heading in t or t in heading):
                    match = ti
                    break
            if match is None:
                sec['pages'] = []
                continue
            start_bi = titles[match][2]
            end_bi = titles[match + 1][2] if match + 1 < len(titles) else len(cl)
            pages = sorted({cl[j].get('page_idx', -1) for j in range(start_bi, end_bi)
                            if cl[j].get('type') == 'text' and cl[j].get('page_idx', -1) >= 0})
            sec['pages'] = [p + 1 for p in pages]  # 转 1-based

    def _extract_fund_sections(self, lines: List[str]) -> List[Dict[str, Any]]:
        """基金项目章节提取：L1/L2/L3 白名单。"""
        sections = []
        current_heading = ''
        current_level = 0
        current_content: List[str] = []

        # L1 模式
        l1_patterns = [
            re.compile(r'项目摘要'), re.compile(r'结题摘要'),
            re.compile(r'[（(][一二二三四五六七八九十]+[)）]\s*[结成]题部分'),
            re.compile(r'[（(][一二二三四五六七八九十]+[)）]\s*成果部分'),
            re.compile(r'研究成果目录'), re.compile(r'附表'), re.compile(r'决算表'),
            re.compile(r'决算说明书'), re.compile(r'签字及审核意见表'),
            re.compile(r'电子附件目录'),
        ]
        # L2 模式
        l2_patterns = [
            re.compile(r'^\d+\.\s*(?:研究计划|研究工作|研究人员|国内外学术|存在的问题)'),
            re.compile(r'^\d+\.\s*项目取得成果'), re.compile(r'^\d+\.\s*项目成果转化'),
            re.compile(r'^\d+\.\s*人才培养'), re.compile(r'^\d+\.\s*其他需要说明的成果'),
            re.compile(r'^\d+\.\s*项目成果科普'),
            re.compile(r'^(?:期刊论文|会议论文|软件著作权|人才培养|学术交流|项目成果应用前景)$'),
            re.compile(r'^[一二三四五六七八九十]+、\s*(?:项目资金|资金结余|单价|资金管理|其他需要说明)'),
            re.compile(r'^(?:项目负责人承诺|依托单位科研管理部门|依托单位财务管理部门|依托单位审查意见|科学处审核意见|科学部核准意见|分管委领导意见)'),
        ]
        # L3 模式（基金报告模板子节）
        l3_patterns = [
            re.compile(r'^[（(]\d+[)）]\s*(?:按计划执行|研究目标完成|主要研究内容|取得的主要研究)'),
        ]

        for line in lines:
            stripped = line.strip()
            m = self.HEADING_RE.match(stripped)
            if m:
                heading = m.group(2).strip()
                level = None
                for p in l1_patterns:
                    if p.search(heading):
                        level = 1
                        break
                if level is None:
                    for p in l2_patterns:
                        if p.match(heading):
                            level = 2
                            break
                if level is None:
                    for p in l3_patterns:
                        if p.match(heading):
                            level = 3
                            break
                if level is None:
                    if current_heading:
                        current_content.append(line)
                    continue
                if current_heading:
                    self._append_section(sections, current_heading, current_level, current_content)
                current_heading = heading
                current_level = level
                current_content = []
            elif current_heading:
                current_content.append(line)
        if current_heading:
            self._append_section(sections, current_heading, current_level, current_content)
        return sections

    def _check_fund_missing(self, sections: List[Dict]) -> List[tuple]:
        existing = set()
        for s in sections:
            for kw in ['项目摘要', '结题摘要', '结题部分', '成果部分',
                       '研究计划', '研究工作', '研究人员', '国内外学术', '存在的问题',
                       '项目取得成果', '项目成果转化', '人才培养', '其他需要说明的成果', '项目成果科普',
                       '研究成果目录', '附表', '签字', '决算说明书']:
                if kw in s['heading']:
                    existing.add(kw)
        missing = []
        for level, kw in self.FUND_TEMPLATE:
            if not any(ekw in kw or kw in ekw for ekw in existing):
                missing.append((level, kw))
        return missing

    def _llm_find_missing_sections(self, text: str, missing: List[tuple]) -> List[Dict]:
        if not self._glm or not missing:
            return []
        missing_str = '\n'.join([f'  L{lv}: {kw}' for lv, kw in missing])
        sysp = ("你是文档结构解析专家。给定文档全文和缺失的章节标题关键词，"
                "请在文档中找到这些章节。只输出JSON："
                '{"data":{"found":[{"heading":"完整标题","keyword":"关键词","content":"内容前200字"}]}}')
        full_text = text[:8000]
        usr = f'缺失章节：\n{missing_str}\n\n文档全文（截取前8000字）：\n{full_text}'
        try:
            d = self._glm.chat_json(sysp, usr, timeout=60.0, max_tokens=1000, temperature=0.0)
            d = d.get('data', d) if isinstance(d, dict) else {}
            found = d.get('found', [])
        except Exception:
            return []
        results = []
        for item in found:
            kw = item.get('keyword', '').strip()
            heading = item.get('heading', '').strip()
            content = item.get('content', '').strip()
            if not heading:
                continue
            level = 2
            for lv, mkw in missing:
                if mkw in heading or heading in mkw:
                    level = lv
                    break
            results.append({'heading': heading, 'level': level, 'content': content})
        return results

    def llm_verify_and_clean(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """LLM 末端校验+清洗：对前三层提取的 title/abstract/keywords 做正确性判定与清洗。

        - 校验：判断候选是否真的是标题/摘要/关键词（非页眉、期刊名、日期、引言正文）
        - 清洗：去残留引用标记、页眉页码、多余空白、修正截断
        - 容错：LLM 未注入/异常时返回纯规则预处理后的 doc，不阻塞主流程
        """
        import logging
        logger = logging.getLogger(__name__)
        if not isinstance(doc, dict):
            return doc

        def _prep(s):
            if not s:
                return ''
            s = self._strip_tags(s)
            s = re.sub(r'[ \t]+', ' ', s)
            s = re.sub(r'\n{3,}', '\n\n', s)
            return s.strip()

        title = _prep(doc.get('title', ''))
        abstract = _prep(doc.get('abstract', ''))
        keywords = doc.get('keywords', []) or []
        if isinstance(keywords, str):
            keywords = [k.strip() for k in re.split(r'[;；、，,]', keywords) if k.strip()]
        keywords = [self._strip_tags(k).strip() for k in keywords if k]

        # 上下文：文档前 2000 字（供 LLM 判定标题真伪、修正截断）
        ctx = doc.get('full_text') or ''
        if not ctx:
            secs = doc.get('sections') or []
            ctx = '\n'.join((s.get('heading', '') + ' ' + s.get('content', ''))
                            for s in secs if isinstance(s, dict))
        ctx = self._strip_tags(ctx)[:2000]

        # 无 LLM → 仅规则预处理
        if not self._glm:
            doc.update({'title': title, 'abstract': abstract, 'keywords': keywords})
            doc['_llm_review'] = {'issues': ['LLM 未注入，仅规则预处理'], 'confidence': None}
            return doc

        sysp = (
            "你是文档结构校验与清洗专家。给定从 PDF 提取的候选标题/摘要/关键词及文档前部文本，"
            "请逐项校验并清洗：\n"
            "1. 标题：是否为论文/报告真正标题？若候选是页眉、期刊名、页码、日期等非标题内容，"
            "尽量从文档前部找出真正标题；找不到则置空。\n"
            "2. 摘要：是否为真正的摘要段落？若实为引言、正文片段或无摘要，置空；"
            "若是摘要，清理其中的引用标记[1-4]、DOI、页码等噪声。\n"
            "3. 关键词：是否为真正的关键词？剔除混入的分类号、文献标志码、DOI 等。\n"
            "4. 通用清洗：去多余空白、修正明显截断。\n"
            "只输出JSON：{\"title\":\"\",\"abstract\":\"\",\"keywords\":[],"
            "\"issues\":[\"说明每项做了什么调整\"],\"confidence\":0.0到1.0}"
        )
        cand = json.dumps({'title': title, 'abstract': abstract, 'keywords': keywords},
                          ensure_ascii=False)
        usr = f'候选字段：\n{cand}\n\n文档前部文本：\n{ctx}'

        try:
            d = self._glm.chat_json(sysp, usr, timeout=60.0, max_tokens=1500, temperature=0.0)
            d = d.get('data', d) if isinstance(d, dict) else {}
        except Exception as e:  # noqa: BLE001
            logger.warning('LLM 校验清洗失败(%s)，返回规则预处理结果', e)
            doc.update({'title': title, 'abstract': abstract, 'keywords': keywords})
            doc['_llm_review'] = {'issues': [f'LLM 异常: {e}，仅规则预处理'], 'confidence': None}
            return doc

        # 合并：LLM 返回的非空字段覆盖原值，空字段保留原候选
        new_title = (d.get('title') or '').strip()
        new_abstract = (d.get('abstract') or '').strip()
        new_kw = d.get('keywords') or []
        if not isinstance(new_kw, list):
            new_kw = [new_kw] if new_kw else []
        new_kw = [self._strip_tags(str(k)).strip() for k in new_kw if k]

        if new_title:
            title = new_title
        if new_abstract:
            abstract = new_abstract
        if new_kw:
            keywords = new_kw

        doc.update({'title': title, 'abstract': abstract, 'keywords': keywords})
        doc['_llm_review'] = {
            'issues': d.get('issues') or [],
            'confidence': d.get('confidence'),
        }
        return doc

    def _find_parent_l1(self, l2_heading: str) -> Optional[str]:
        h = l2_heading.strip()
        if re.match(r'^\d+\.\s*(?:研究计划|研究工作|研究人员|国内外学术|存在的问题)', h):
            return '结题部分'
        if re.match(r'^\d+\.\s*(?:项目取得成果|项目成果转化|人才培养|其他需要说明的成果|项目成果科普)', h):
            return '成果部分'
        if h in ('期刊论文', '会议论文', '软件著作权', '人才培养', '学术交流', '项目成果应用前景'):
            return '研究成果目录'
        if re.match(r'^[一二三四五六七八九十]+、', h):
            return '决算说明书'
        return None

    @staticmethod
    def _extract_from_table(text: str, pattern: str, default: str = '') -> str:
        m = re.search(pattern, text, re.DOTALL)
        return m.group(1).strip() if m else default

    @staticmethod
    def _clean_text(text: str) -> str:
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()


def parse_document(md_path: str | Path) -> Dict[str, Any]:
    return DocumentParser().parse(md_path)
