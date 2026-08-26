"""v1 路由聚合：挂载功能项控制器，并提供功能点目录接口。"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter

from config.functional_points import FunctionalPoint, list_functional_points, list_items
from presentation.api.v1 import (
    auto_classification_controller,
    citation_recognition_controller,
    concept_definition_controller,
    cluster_labeling_controller,
    deep_clustering_controller,
    keyword_recognition_controller,
    move_recognition_controller,
    ner_controller,
    research_question_controller,
    structured_review_controller,
    integration_controller,
)

router = APIRouter()


@router.get("/catalog", response_model=List[dict], summary="功能点目录")
def catalog() -> List[dict]:
    """返回全部功能点的元数据，便于前端动态发现可用接口。"""
    return [
        {
            "code": fp.code,
            "name": fp.name,
            "functional_item": fp.functional_item,
            "functional_item_code": fp.functional_item_code,
            "input_type": fp.input_type.value,
            "description": fp.description,
            "endpoint": f"/api/v1/{fp.functional_item_code}/{fp.code}",
        }
        for fp in list_functional_points()
    ]


# 挂载功能项控制器
router.include_router(move_recognition_controller.router)
router.include_router(auto_classification_controller.router)
router.include_router(keyword_recognition_controller.router)
router.include_router(research_question_controller.router)
router.include_router(citation_recognition_controller.router)
router.include_router(concept_definition_controller.router)
router.include_router(ner_controller.router)
router.include_router(cluster_labeling_controller.router)
router.include_router(deep_clustering_controller.router)
router.include_router(structured_review_controller.router)
# 面向当前 Vue 的稳定接口放在最后挂载；旧 DDD 功能码接口继续保留。
router.include_router(integration_controller.router)
