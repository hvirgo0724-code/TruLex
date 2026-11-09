"""知识检索接口。"""

from fastapi import APIRouter, Depends

from app.agents.tools import search_knowledge
from app.middleware.rate_limit import default_rate_limit
from app.schemas.knowledge import (
    KnowledgeHit,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/search", response_model=KnowledgeSearchResponse)
async def search(
    body: KnowledgeSearchRequest,
    _: None = Depends(default_rate_limit),
) -> KnowledgeSearchResponse:
    """向量检索知识库，返回 top_k 结果（含来源）。"""
    results = await search_knowledge(body.query, top_k=body.top_k)
    hits = [
        KnowledgeHit(
            score=float(r.get("score", 0.0)),
            source=r.get("source", "milvus"),
            text=r.get("text", ""),
            title=r.get("title", "") or (r.get("meta") or {}).get("title", ""),
            metadata=r.get("meta"),
        )
        for r in results
    ]
    return KnowledgeSearchResponse(hits=hits)