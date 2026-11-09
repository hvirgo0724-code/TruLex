"""文档上传 / 入库相关模型。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    source_type: str
    status: str
    chunk_count: int
    created_at: datetime


class DocumentUploadResponse(BaseModel):
    document_id: int
    task_id: Optional[str] = None
    status: str = "pending"
    message: str = "已收到文件，正在异步入库"