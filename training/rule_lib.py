"""训练用规则库模型（三层 + 条件 + 证据 + 等级 + 统计）。

按 rule.pdf 方法论重设计：
- principles：进 prompt 的少量抽象判定原则（不逐条拼规则）
- pattern_rules：后置规则引擎执行的可执行规则（必要条件 + 排除条件）
- dictionaries：语言表达词典（仅作特征，不直接决定标签）

条件（necessary/exclusion_conditions）为结构化 dict，由 rule_engine 解释执行：
  - {kind: keyword, any_of: [...]} / {kind: keyword, all_of: [...]}
  - {kind: regex, pattern: "..."}
  - {kind: feature, dim: research_actor|fact_status|action_type|evidence_type|
                       discourse_position|clause_role, in: [...]}  # 也可用 not_in
  - {kind: position, after_move: 研究结果} / {kind: position, before_move: 研究方法}
  - {kind: position, rel_min: 0.0, rel_max: 0.3}  # 相对位置区间
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from training.profile import get_profile

# 等级 → 最大调分权重上限（规则不直接覆盖 LLM，只做有限调整）
LEVEL_WEIGHT_CAP = {
    "candidate": 0.05,
    "advisory": 0.10,
    "soft": 0.18,
    "strong": 0.25,
}


@dataclass
class Rule:
    id: str
    layer: str = "universal"          # universal | dictionary | domain
    scope: str = "global"             # global | domain
    applicable_domains: List[str] = field(default_factory=list)
    target_move: Optional[str] = None  # 研究背景/目的/方法/结果/结论，review 类可 None
    necessary_conditions: List[Dict[str, Any]] = field(default_factory=list)
    exclusion_conditions: List[Dict[str, Any]] = field(default_factory=list)
    evidence_dims: List[str] = field(default_factory=list)
    action: str = "review"            # +score | -score | review
    level: str = "candidate"          # candidate | advisory | soft | strong
    weight: float = 0.5               # 基础权重，实际受 LEVEL_WEIGHT_CAP 约束
    description: str = ""
    positive_examples: List[str] = field(default_factory=list)
    negative_examples: List[str] = field(default_factory=list)
    mis_corrections: List[str] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)
    complexity: float = 0.0
    fold_count: int = 0
    # 兼容旧字段（渲染/聚合可能引用）
    pattern: str = ""
    type: str = ""

    # ---------------- 统计 ----------------
    @property
    def matched(self) -> int:
        return int(self.stats.get("matched", 0))

    @property
    def correct(self) -> int:
        return int(self.stats.get("correct", 0))

    @property
    def incorrect(self) -> int:
        return int(self.stats.get("incorrect", 0))

    @property
    def estimated_reliability(self) -> float:
        """规则在 LLM 判错句上的指向正确率（小样本平滑）：(改对+1)/(改对+改错+2)。"""
        c, i = self.correct, self.incorrect
        return (c + 1) / (c + i + 2) if (c + i) >= 0 else 0.5

    @property
    def net_gain(self) -> int:
        """净纠错收益 = 改对 - 改错。"""
        return self.correct - self.incorrect

    @property
    def effective_weight(self) -> float:
        """动态权重：从验证集净收益/可靠性/覆盖/稳定性学出来（rule.pdf 第7/13条）。

        两端萎缩、中间存活：
        - 未测量（无 stats）→ 回退到等级上限
        - 净收益 < 0（太宽，改错多于改对）→ 0（自动停用）
        - 覆盖因子：命中少（太紧，只帮少数论文）→ ×0.3；中等→×0.7；充足→×1.0
        - 净收益 > 0 → 上限 × 可靠性 × 覆盖因子 × (0.5 + 0.5×稳定性)
        """
        cap = float(LEVEL_WEIGHT_CAP.get(self.level, 0.05))
        if not self.stats:
            return cap  # 完全未测量 → 回退等级上限
        m = self.matched
        if m == 0:
            # 已测量但在错例上零命中（没覆盖）→ 低权重（符合"太紧/没覆盖→权重小"）
            return round(cap * 0.3, 4)
        net = self.net_gain
        if net < 0:
            return 0.0  # 太宽 → 停用
        rel = self.estimated_reliability  # 0..1
        # 覆盖因子（证据强度）：太紧的规则命中少 → 权重缩水
        coverage = 0.3 if m < 3 else (0.7 if m < 8 else 1.0)
        # 跨折稳定性
        from training.config import N_FOLDS
        stab = min(1.0, (self.fold_count if self.fold_count else 1) / max(N_FOLDS, 1))
        return round(cap * rel * coverage * (0.5 + 0.5 * stab), 4)

    # ---------------- 序列化 ----------------
    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "id": self.id,
            "layer": self.layer,
            "scope": self.scope,
            "target_move": self.target_move,
            "action": self.action,
            "level": self.level,
            "weight": self.weight,
            "description": self.description,
        }
        if self.applicable_domains:
            d["applicable_domains"] = self.applicable_domains
        if self.necessary_conditions:
            d["necessary_conditions"] = self.necessary_conditions
        if self.exclusion_conditions:
            d["exclusion_conditions"] = self.exclusion_conditions
        if self.evidence_dims:
            d["evidence_dims"] = self.evidence_dims
        if self.positive_examples:
            d["positive_examples"] = self.positive_examples
        if self.negative_examples:
            d["negative_examples"] = self.negative_examples
        if self.mis_corrections:
            d["mis_corrections"] = self.mis_corrections
        if self.stats:
            d["stats"] = self.stats
        if self.fold_count:
            d["fold_count"] = self.fold_count
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Rule":
        return cls(
            id=d.get("id", ""),
            layer=d.get("layer", "universal"),
            scope=d.get("scope", "global"),
            applicable_domains=d.get("applicable_domains", []) or [],
            target_move=d.get("target_move"),
            necessary_conditions=d.get("necessary_conditions", []) or [],
            exclusion_conditions=d.get("exclusion_conditions", []) or [],
            evidence_dims=d.get("evidence_dims", []) or [],
            action=d.get("action", "review"),
            level=d.get("level", "candidate"),
            weight=float(d.get("weight", 0.5)),
            description=d.get("description", ""),
            positive_examples=d.get("positive_examples", []) or [],
            negative_examples=d.get("negative_examples", []) or [],
            mis_corrections=d.get("mis_corrections", []) or [],
            stats=d.get("stats", {}) or {},
            complexity=float(d.get("complexity", 0.0)),
            fold_count=int(d.get("fold_count", 0)),
            pattern=d.get("pattern", ""),
            type=d.get("type", ""),
        )

    def compute_complexity(self) -> float:
        """复杂度评分：条件数 + 具体词数 + 例外数。越复杂越像记忆训练数据。"""
        n_cond = len(self.necessary_conditions)
        n_excl = len(self.exclusion_conditions)
        n_words = 0
        for c in self.necessary_conditions + self.exclusion_conditions:
            n_words += len(c.get("any_of", []) or [])
            n_words += len(c.get("all_of", []) or [])
        # 依赖精确位置区间加权
        pos_dep = any(c.get("kind") == "position" and ("rel_min" in c or "rel_max" in c)
                      for c in self.necessary_conditions)
        self.complexity = float(n_cond + n_excl + 0.3 * n_words + (0.5 if pos_dep else 0.0))
        return self.complexity


@dataclass
class RuleLib:
    name: str
    functional_item: str
    description: str
    system_prompt: str                       # 角色 + 五语步定义（基础）
    principles: str = ""                     # 抽象判定原则（进 prompt）
    pattern_rules: List[Rule] = field(default_factory=list)
    dictionaries: Dict[str, List[str]] = field(default_factory=dict)
    examples: List[Dict[str, Any]] = field(default_factory=list)
    output_schema: Dict[str, Any] = field(default_factory=dict)

    # 兼容旧接口：rules 即 pattern_rules
    @property
    def rules(self) -> List[Rule]:
        return self.pattern_rules

    # ---------------- IO ----------------
    @classmethod
    def load(cls, path: Path) -> "RuleLib":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        rules = [Rule.from_dict(r) for r in (data.get("pattern_rules") or data.get("rules") or [])]
        return cls(
            name=data.get("name", ""),
            functional_item=data.get("functional_item", ""),
            description=data.get("description", ""),
            system_prompt=data.get("system_prompt", ""),
            principles=data.get("principles", ""),
            pattern_rules=rules,
            dictionaries=data.get("dictionaries", {}) or {},
            examples=data.get("examples") or [],
            output_schema=data.get("output_schema") or {},
        )

    def save(self, path: Path) -> None:
        data = {
            "functional_item": self.functional_item,
            "name": self.name,
            "description": self.description,
            "input_type": "text",
            "system_prompt": self.system_prompt,
            "principles": self.principles,
            "dictionaries": self.dictionaries,
            "pattern_rules": [r.to_dict() for r in self.pattern_rules],
            "output_schema": self.output_schema,
            "examples": self.examples,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False, width=10000)

    # ---------------- 渲染 ----------------
    def render_principles_prompt(self) -> str:
        """只渲染抽象判定原则进 prompt，不逐条拼规则（防过拟合 + 防 prompt 膨胀）。"""
        parts: List[str] = [self.system_prompt.strip()]
        if self.principles.strip():
            parts.append("\n\n【判定原则】" + self.principles.strip())
        parts.append("\n\n【输出格式】输出 JSON 对象，键为五个语步，值为该语步对应的原文逐字摘录"
                     "（不得改写、不得遗漏、不得新增；空语步用空字符串）。")
        parts.append("键固定为：" + "、".join(get_profile().moves))
        parts.append("另输出一个键 move_confidence，值为对象，键为同样五个语步，值为该语步的识别置信度（0.0-1.0）："
                     "文本明确符合语步定义且无歧义→0.85-0.95；边界模糊或复合句拆分存疑→0.60-0.80；"
                     "判定该语步缺失（空字符串）→给判空确信度（结构完整可确认缺失→0.75-0.90，难以判断→0.55-0.70）。"
                     "置信度反映你对各语步划分（含判空）的确信程度，需有区分度，不要全部给同一值。")
        parts.append("仅输出 JSON，不要附加任何解释。")
        return "\n".join(parts)

    def render_few_shot(self, max_examples: int = 4) -> str:
        if not self.examples:
            return ""
        ex = self.examples[:max_examples]
        parts = ["\n\n【参考样例】以下为典型模式代表，供理解输出格式与判定准则（勿照搬个案）："]
        for i, e in enumerate(ex, 1):
            parts.append(f"样例{i} 摘要：{e.get('abstract','')}")
            parts.append("样例%d 输出：%s" % (i, __import__("json").dumps(e.get("spans", {}), ensure_ascii=False)))
        return "\n".join(parts)

    # 兼容旧接口
    def render_system_prompt(self) -> str:
        return self.render_principles_prompt()

    def engine_rules(self, domain: Optional[str] = None) -> List[Rule]:
        """返回适用于指定领域的规则：global 规则 + 匹配领域的 domain 规则。"""
        out: List[Rule] = []
        for r in self.pattern_rules:
            if r.scope == "global":
                out.append(r)
            elif r.scope == "domain" and domain and domain in r.applicable_domains:
                out.append(r)
        return out
