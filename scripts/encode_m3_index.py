"""用 bge-m3（多语言）编码 CLC 知识库 → 跨语言索引。

bge-m3 支持中英等 100+ 语言同一向量空间，英文 query 可匹配中文 CLC 条目。
输出 1024 维归一化 dense 向量（与 clc_meta_full.json 按顺序一一对应），
存 infrastructure/rag/clc_index_m3/，供 ac_en 跨语言检索。核心逻辑已抽至 clc_index_builder.build_index。
"""
from config.settings import settings
from infrastructure.rag.clc_index_builder import build_index

if __name__ == "__main__":
    build_index(str(settings.CLC_RAG_DIR), build_large=False)
    print("DONE.")
