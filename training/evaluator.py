"""评测器：句子级对齐 + 每类 P/R/F1 + 总体准确率。

评估思路：
- 对同一篇摘要分句（确定性）；
- 用 gold spans 得到每个句子的 gold 语步，用 pred spans 得到 pred 语步；
- 句子为实例，语步为类别，计算每类 P/R/F1 与总体 accuracy / macro-F1。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from training.profile import get_profile


@dataclass
class SampleMetrics:
    n_sentences: int = 0
    correct: int = 0
    per_move_gold: Dict[str, int] = field(default_factory=dict)
    per_move_pred: Dict[str, int] = field(default_factory=dict)
    per_move_tp: Dict[str, int] = field(default_factory=dict)


@dataclass
class EvalReport:
    accuracy: float
    macro_f1: float
    per_move: Dict[str, Dict[str, float]] = field(default_factory=dict)
    n_sentences: int = 0
    n_samples: int = 0

    def summary(self) -> str:
        lines = [f"样本数={self.n_samples} 句子数={self.n_sentences} "
                 f"准确率={self.accuracy:.4f} macroF1={self.macro_f1:.4f}"]
        for m in get_profile().moves:
            d = self.per_move.get(m, {})
            lines.append(f"  {m}: P={d.get('precision',0):.3f} "
                         f"R={d.get('recall',0):.3f} F1={d.get('f1',0):.3f}")
        return "\n".join(lines)


def evaluate_one(abstract: str, gold_spans: dict, pred_spans: dict) -> SampleMetrics:
    p = get_profile()
    sents = p.seg.segment(abstract)
    gold_labels = p.seg.assign_sentences_to_spans(sents, gold_spans)
    pred_labels = p.seg.assign_sentences_to_spans(sents, pred_spans)
    m = SampleMetrics(n_sentences=len(sents))
    for g, p in zip(gold_labels, pred_labels):
        m.per_move_gold[g] = m.per_move_gold.get(g, 0) + 1
        m.per_move_pred[p] = m.per_move_pred.get(p, 0) + 1
        if g == p:
            m.correct += 1
            m.per_move_tp[g] = m.per_move_tp.get(g, 0) + 1
    return m


def evaluate(samples: List, predict_fn) -> EvalReport:
    """对样本集合评估。predict_fn(abstract)->pred_spans(dict)。"""
    pred_spans = [predict_fn(s.abstract) for s in samples]
    return evaluate_preds(samples, pred_spans)


def evaluate_preds(samples: List, pred_spans_list: List[dict]) -> EvalReport:
    """用预计算的 pred spans 评估（避免重复调用模型）。"""
    agg = SampleMetrics()
    n_samples = 0
    for s, pred_spans in zip(samples, pred_spans_list):
        m = evaluate_one(s.abstract, s.spans, pred_spans)
        n_samples += 1
        agg.n_sentences += m.n_sentences
        agg.correct += m.correct
        for k, v in m.per_move_gold.items():
            agg.per_move_gold[k] = agg.per_move_gold.get(k, 0) + v
        for k, v in m.per_move_pred.items():
            agg.per_move_pred[k] = agg.per_move_pred.get(k, 0) + v
        for k, v in m.per_move_tp.items():
            agg.per_move_tp[k] = agg.per_move_tp.get(k, 0) + v

    accuracy = agg.correct / agg.n_sentences if agg.n_sentences else 0.0
    per_move: Dict[str, Dict[str, float]] = {}
    f1s = []
    for mv in get_profile().moves + [""]:
        tp = agg.per_move_tp.get(mv, 0)
        g = agg.per_move_gold.get(mv, 0)
        p = agg.per_move_pred.get(mv, 0)
        prec = tp / p if p else 0.0
        rec = tp / g if g else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        per_move[mv or "(无)"] = {"precision": prec, "recall": rec, "f1": f1}
        if mv:  # macro 只计入五个正式语步
            f1s.append(f1)
    macro_f1 = sum(f1s) / len(f1s) if f1s else 0.0
    return EvalReport(accuracy=accuracy, macro_f1=macro_f1, per_move=per_move,
                      n_sentences=agg.n_sentences, n_samples=n_samples)
