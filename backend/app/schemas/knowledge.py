"""知识检索请求 / 响应模型。"""

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="检索问题")
    top_k: int = Field(5, ge=1, le=50, description="返回条数")


class KnowledgeHit(BaseModel):
    score: float = 0.0
    source: str = "milvus"
    text: str = ""
    title: str = ""
    metadata: Optional[Any] = None


class KnowledgeSearchResponse(BaseModel):
    hits: List[KnowledgeHit]