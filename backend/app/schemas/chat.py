"""聊天相关请求 / 响应模型。"""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    conversation_id: Optional[str] = Field(None, description="会话 ID（thread_id），缺省新建")
    message: str = Field(..., min_length=1, description="用户消息")


class Citation(BaseModel):
    source: str = ""  # 法条 / 判例 / 知识库
    title: str = ""
    snippet: str = ""


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    citations: Optional[List[Any]] = None
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    conversation_id: str
    messages: List[MessageOut]