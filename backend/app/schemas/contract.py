"""合同审查相关请求 / 响应模型。"""

from typing import List, Optional

from pydantic import BaseModel, Field


class ContractReviewRequest(BaseModel):
    text: Optional[str] = Field(None, description="合同文本（与文件二选一）")
    file_path: Optional[str] = Field(None, description="已上传文件的路径（可选）")
    title: str = "未命名合同"


class ReviewItem(BaseModel):
    clause: str = Field(..., description="触发风险的条款原文片段")
    risk_level: str = Field(..., description="风险等级：high / medium / low")
    suggestion: str = Field(..., description="修改建议")
    highlight: str = Field(..., description="用于前端高亮展示的关键片段")


class ContractReviewResponse(BaseModel):
    items: List[ReviewItem]
    summary: str = ""


class ContractReviewError(BaseModel):
    detail: str