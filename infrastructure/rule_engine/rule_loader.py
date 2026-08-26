"""规则库加载引擎。

每个功能点拥有独立规则库 YAML，互不混用，避免功能互相影响。
支持两种形态：
- 旧式（其它功能点）：system_prompt + rules（拼进 prompt）+ output_schema
- 新式（mr_zh_abstract）：system_prompt + principles（进 prompt）+ pattern_rules
  + dictionaries（后置引擎执行），规则不直接拼进 prompt
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from config.settings import settings
from config.functional_points import get_functional_point

logger = logging.getLogger(__name__)


@dataclass
class RuleLibrary:
    """单个功能点的规则库。"""
    code: str
    name: str
    functional_item: str
    description: str
    system_prompt: str
    rules: List[Dict[str, Any]]
    output_schema: Dict[str, Any]
    examples: List[Dict[str, Any]]
    raw: Dict[str, Any]
    principles: str = ""
    pattern_rules: List[Dict[str, Any]] = field(default_factory=list)
    dictionaries: Dict[str, List[str]] = field(default_factory=dict)
    engine_type: str = ""  # 引擎类型：空=语步识别引擎，auto_classification=分类管线
    cross_lingual: bool = False  # 分类管线是否走 bge-m3 跨语言检索（ac_en）
    lang: str = ""  # 关键词管线语言：en=英文挖掘器(nltk)，空=中文(jieba)
    domain_list: list = field(default_factory=list)  # ac_domain 的 32 领域列表
    system_prompt_en: str = ""  # 英文 system_prompt（rq_identify 等双语工具）

    @property
    def has_engine(self) -> bool:
        """是否启用后置规则引擎（新式规则库）。"""
        return bool(self.pattern_rules) or bool(self.principles) or bool(self.engine_type)

    def render_system_prompt(self, lang: str = "") -> str:
        """拼装 system prompt。

        新式（有 principles）：只渲染抽象判定原则，不逐条拼规则（防过拟合 + 防 prompt 膨胀）。
        旧式：基础提示 + 规则逐条 + 输出 schema。
        lang="en" 且有 system_prompt_en 时用英文 base prompt。
        """
        base = self.system_prompt
        if lang == "en" and self.system_prompt_en.strip():
            base = self.system_prompt_en
        parts: List[str] = [base.strip()]

        if self.principles.strip():
            parts.append("\n\n【判定原则】" + self.principles.strip())
        elif self.rules:
            parts.append("\n\n【规则库】请严格遵循以下规则：")
            for r in self.rules:
                rid = r.get("id", "")
                desc = r.get("description", "")
                parts.append(f"- {rid}：{desc}")

        if self.output_schema:
            parts.append("\n\n【输出格式】必须输出符合如下 JSON Schema 的 JSON 对象：")
            parts.append(json.dumps(self.output_schema, ensure_ascii=False, indent=2))
            parts.append("仅输出 JSON，不要附加任何解释性文字。")

        return "\n".join(parts)


class RuleLoader:
    """规则库加载器（带内存缓存）。"""

    def __init__(self, rules_dir: Optional[Path] = None) -> None:
        self.rules_dir = rules_dir or settings.RULES_DIR
        self._cache: Dict[str, RuleLibrary] = {}

    def load(self, code: str) -> RuleLibrary:
        if code in self._cache:
            return self._cache[code]

        fp = get_functional_point(code)
        path = self.rules_dir / fp.rule_path
        if not path.exists():
            raise FileNotFoundError(f"功能点 [{code}] 规则库不存在：{path}")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        lib = RuleLibrary(
            code=code,
            name=data.get("name", fp.name),
            functional_item=data.get("functional_item", fp.functional_item),
            description=data.get("description", fp.description),
            system_prompt=data.get("system_prompt", ""),
            rules=data.get("rules", data.get("pattern_rules", [])),
            output_schema=data.get("output_schema", {}),
            examples=data.get("examples", []),
            raw=data,
            principles=data.get("principles", ""),
            pattern_rules=data.get("pattern_rules", []),
            dictionaries=data.get("dictionaries", {}),
            engine_type=data.get("engine_type", ""),
            cross_lingual=bool(data.get("cross_lingual", False)),
            lang=data.get("lang", ""),
            domain_list=data.get("domain_list", []),
            system_prompt_en=data.get("system_prompt_en", ""),
        )
        self._cache[code] = lib
        logger.info("已加载规则库 [%s] -> %s (engine=%s)", code, path, lib.has_engine)
        return lib


# 单例
rule_loader = RuleLoader()
