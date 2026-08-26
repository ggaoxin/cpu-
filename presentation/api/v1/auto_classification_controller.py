"""自动分类工具控制器（3 个功能点）。"""
from presentation.api.base_controller import build_item_router
from config.functional_points import list_points_by_item

ITEM_CODE = "auto_classification"
ITEM_NAME = "自动分类工具"
router = build_item_router(ITEM_CODE, ITEM_NAME, list_points_by_item(ITEM_CODE))
