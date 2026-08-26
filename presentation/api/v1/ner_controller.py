"""命名实体识别工具控制器（4 个功能点）。"""
from presentation.api.base_controller import build_item_router
from config.functional_points import list_points_by_item

ITEM_CODE = "ner"
ITEM_NAME = "命名实体识别工具"
router = build_item_router(ITEM_CODE, ITEM_NAME, list_points_by_item(ITEM_CODE))
