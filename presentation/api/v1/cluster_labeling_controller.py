"""聚类标签生成工具控制器。"""
from presentation.api.base_controller import build_item_router
from config.functional_points import list_points_by_item

ITEM_CODE = "cluster_labeling"
ITEM_NAME = "聚类标签生成工具"
router = build_item_router(ITEM_CODE, ITEM_NAME, list_points_by_item(ITEM_CODE))
