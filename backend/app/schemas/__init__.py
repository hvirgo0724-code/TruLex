"""Pydantic 请求 / 响应模型。"""

from app.schemas.auth import LoginRequest, TokenResponse, UserOut
from app.schemas.chat import (
    ChatHistoryResponse,
    ChatRequest,
    Citation,
    MessageOut,
)
from app.schemas.contract import ContractReviewRequest, ContractReviewResponse, ReviewItem
from app.schemas.document import DocumentOut, DocumentUploadResponse
from app.schemas.knowledge import (
    KnowledgeHit,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
)

__all__ = [
    "LoginRequest",
    "TokenResponse",
    "UserOut",
    "ChatRequest",
    "ChatHistoryResponse",
    "Citation",
    "MessageOut",
    "ContractReviewRequest",
    "ContractReviewResponse",
    "ReviewItem",
    "DocumentOut",
    "DocumentUploadResponse",
    "KnowledgeHit",
    "KnowledgeSearchRequest",
    "KnowledgeSearchResponse",
]