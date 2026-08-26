"""用 bge-large-zh-v1.5 编码合并后的完整 CLC 知识库（40912 条）。

输出两套 1024 维归一化向量（与 clc_meta_full.json 按顺序一一对应）：
- clc_vectors_large_fullpath.npy  （编码 full_path，含层级，检索 recall 更高）
- clc_vectors_large_ragtext.npy    （编码 rag_text，备用）
覆盖 infrastructure/rag/clc_index_large/。核心逻辑已抽至 clc_index_builder.build_index。
"""
from config.settings import settings
from infrastructure.rag.clc_index_builder import build_index

if __name__ == "__main__":
    build_index(str(settings.CLC_RAG_DIR), build_m3=False)
    print("DONE.")
