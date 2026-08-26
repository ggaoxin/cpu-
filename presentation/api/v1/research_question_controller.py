"""研究问题识别工具控制器（1 个功能点）。"""
from presentation.api.base_controller import build_item_router
from config.functional_points import list_points_by_item

ITEM_CODE = "research_question"
ITEM_NAME = "研究问题识别工具"
router = build_item_router(ITEM_CODE, ITEM_NAME, list_points_by_item(ITEM_CODE))
