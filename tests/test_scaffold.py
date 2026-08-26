"""脚手架自检测试：不依赖真实大模型调用，验证结构完整性。

运行：
    cd semantic-toolkit && python -m pytest tests/ -q
"""
from config.functional_points import list_functional_points, list_items, get_functional_point
from config.settings import settings
from infrastructure.rule_engine.rule_loader import rule_loader


EXPECTED_POINT_COUNT = 19
EXPECTED_ITEM_COUNT = 10


def test_functional_point_counts():
    """应有 19 个功能点、10 个功能项。"""
    points = list_functional_points()
    assert len(points) == EXPECTED_POINT_COUNT
    assert len(list_items()) == EXPECTED_ITEM_COUNT


def test_each_point_has_independent_rule_library():
    """每个功能点的规则库文件都存在且可加载，且互为独立文件。"""
    seen_paths = set()
    for fp in list_functional_points():
        lib = rule_loader.load(fp.code)
        assert lib.code == fp.code
        assert lib.system_prompt.strip(), f"{fp.code} 缺少 system_prompt"
        # 旧式有 rules；新式引擎规则库用 principles/pattern_rules/engine_type 代替逐条规则
        assert lib.rules or lib.principles or lib.pattern_rules or lib.engine_type, \
            f"{fp.code} 缺少规则集/原则/引擎"
        assert lib.output_schema, f"{fp.code} 缺少 output_schema"
        # 规则库路径独立
        assert fp.rule_path not in seen_paths, f"规则库路径重复：{fp.rule_path}"
        seen_paths.add(fp.rule_path)


def test_rule_library_renders_system_prompt():
    lib = rule_loader.load("mr_zh_abstract")
    rendered = lib.render_system_prompt()
    # 新式规则库：prompt 只含抽象判定原则，不逐条拼规则（防过拟合）
    assert lib.has_engine
    assert "判定原则" in rendered
    assert "JSON" in rendered


def test_app_routes_registered():
    """FastAPI 应用应注册全部 19 个功能点端点 + 目录 + 健康检查。"""
    from presentation.main import app

    paths = set(app.openapi()["paths"].keys())
    assert "/health" in paths
    assert "/api/v1/catalog" in paths
    for fp in list_functional_points():
        expected = f"/api/v1/{fp.functional_item_code}/{fp.code}"
        assert expected in paths, f"缺少端点：{expected}"


def test_input_type_dispatch_validation():
    """单篇/多篇输入校验应按 input_type 正确分发。"""
    from application.dto.common_dto import SemanticRequest
    from application.service.semantic_service import SemanticApplicationService

    # 用假 GLM 避免真实调用
    class FakeGLM:
        def chat_json(self, system_prompt, user_prompt, temperature=None):
            return {"data": {}, "confidence": 0.9}

    svc = SemanticApplicationService(glm=FakeGLM(), rule_loader=rule_loader)

    # text 类功能点缺少 text 应报错
    fp = get_functional_point("mr_zh_abstract")
    res = svc.execute("mr_zh_abstract", SemanticRequest())
    assert res.success is False
