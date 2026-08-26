"""深度聚类工具控制器。"""
from presentation.api.base_controller import build_item_router
from config.functional_points import list_points_by_item

ITEM_CODE = "deep_clustering"
ITEM_NAME = "深度聚类工具"
router = build_item_router(ITEM_CODE, ITEM_NAME, list_points_by_item(ITEM_CODE))
