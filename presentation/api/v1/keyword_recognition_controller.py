"""关键词识别工具控制器（2 个功能点）。"""
from presentation.api.base_controller import build_item_router
from config.functional_points import list_points_by_item

ITEM_CODE = "keyword_recognition"
ITEM_NAME = "关键词识别工具"
router = build_item_router(ITEM_CODE, ITEM_NAME, list_points_by_item(ITEM_CODE))
