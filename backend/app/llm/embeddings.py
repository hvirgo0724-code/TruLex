"""向量嵌入：OpenAIEmbeddings（DashScope 兼容，1024 维，qwen3.7-text-embedding）。"""

from typing import Optional

from langchain_openai import OpenAIEmbeddings

from app.core.config import settings

_embeddings: Optional[OpenAIEmbeddings] = None


def get_embeddings() -> OpenAIEmbeddings:
    """返回全局唯一的嵌入客户端（懒加载）。维度固定 1024。"""
    global _embeddings
    if _embeddings is None:
        _embeddings = OpenAIEmbeddings(
            model=settings.EMBEDDING_MODEL,
            api_key=settings.API_KEY,
            base_url=settings.BASE_URL,
            dimensions=settings.EMBEDDING_DIM,
            check_embedding_ctx_length=False,
            chunk_size=settings.EMBEDDING_CHUNK_SIZE,
        )
    return _embeddings


def reset_embeddings() -> None:
    """测试或热切换配置时重置，非必要不调用。"""
    global _embeddings
    _embeddings = None