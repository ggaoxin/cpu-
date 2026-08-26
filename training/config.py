"""训练框架配置。"""
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 数据集路径（项目自包含：data/datasets）
from config.settings import settings as _settings
DATASETS_DIR = _settings.DATA_DIR
ABSTRACTS_FILE = DATASETS_DIR / "chinese_abstracts.json"
MOVE_RESULTS_FILE = DATASETS_DIR / "chinese_abstract_move_results.json"

# 训练产物目录
TRAINING_DIR = PROJECT_ROOT / "training"
DATA_DIR = TRAINING_DIR / "data"          # 归一化后的数据集缓存
RUNS_DIR = TRAINING_DIR / "runs"          # 每次运行的产物（规则库、报告）
RUNS_DIR.mkdir(parents=True, exist_ok=True)

# 目标功能点
FUNCTIONAL_POINT_CODE = "mr_zh_abstract"
RULE_FILE = PROJECT_ROOT / "rules" / "move_recognition" / "mr_zh_abstract.yaml"

# 五个语步类别
MOVES = ["研究背景", "研究目的", "研究方法", "研究结果", "研究结论"]

# 划分参数
HOLDOUT_SIZE = 400          # 最终留出集
N_FOLDS = 5                 # 5 折 CV
RANDOM_SEED = 42            # 主随机种子（每折派生不同种子）
STRATIFY = True             # 按语步构成分层抽样

# 迭代调优参数（缩减规模以适配 GLM 限流，保证数小时内跑完）
MAX_ITERATIONS = 2          # 每折最大迭代轮数
INDUCE_SAMPLE_SIZE = 24     # 每折每轮用于错误分析的样本数
EVAL_SAMPLE_SIZE = 60       # 每折每轮评估样本数
GENERALIZE_CHECK_SIZE = 40  # 兼容旧签名（source_check 不用）
HOLDOUT_EVAL_SIZE = 150     # 最终留出集评测样本数
RULE_GENERALIZE_MIN_GAIN = 0.0

# 数据限量：阶段一赶进度，只用前 N 篇（None=全量2000）
DATASET_LIMIT = 200

# 跨篇泛化校验（防过拟合）：候选规则在“非源摘要”的其它篇上平均准确率不得退化
CROSS_CHECK_SIZE = 8        # 跨篇校验用的“其它篇”数量
CROSS_ALLOW_DEGRADE = 0.0   # 允许的平均准确率退化上限（0=不允许退化）

# 反例搜索（rule.pdf 第9条）：每条候选规则生成反例检查是否误触发（1次GLM/候选）
ENABLE_COUNTEREXAMPLE = True

# 验证集大小（rule.pdf 第6条）：每折训练集再切一份验证集，准入净收益在验证集上测（泛化校验）
# 规则从归纳集产出，在未参与归纳的验证集上测净收益——避免"用训练集既归纳又验证"的循环泄漏
VALIDATE_SIZE = 20

# 并发
MAX_WORKERS = 4             # GLM 并发数（过高触发 429 限流，反而变慢）

# 归纳分批：错例按批喂给 GLM，每批 INDUCE_BATCH_SIZE 个，避免单次 prompt 过大超时
INDUCE_BATCH_SIZE = 6

# GLM 调用
GLM_TEMPERATURE = 0.1
GLM_INDUCE_TEMPERATURE = 0.4  # 规则归纳用更高温度激发多样性

# 评估时是否触发冲突二次审核（True=测量真实系统效果，False=省GLM只测引擎+LLM）
EVAL_DO_REVIEW = True
