"""合同审查接口：接受合同文本或上传文件，返回风险点与高亮片段。"""

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.tools import parse_contract
from app.api.deps import get_current_user_optional, get_db
from app.models.user import User
from app.schemas.contract import ContractReviewResponse, ReviewItem
from app.services.audit import record_audit
from app.services.contract import review_contract

router = APIRouter(prefix="/contract", tags=["contract"])

_UPLOAD_DIR = "/tmp/legal_contracts"


@router.post("/review", response_model=ContractReviewResponse)
async def review(
    request: Request,
    text: Optional[str] = Form(None, description="合同文本（与文件二选一）"),
    title: Optional[str] = Form(None, description="合同名称"),
    file: Optional[UploadFile] = File(None, description="合同文件（.docx/.pdf/.txt）"),
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> ContractReviewResponse:
    """合同审查：文本或文件（multipart），二者至少提供一个。"""
    llm = request.app.state.llm

    file_path: Optional[str] = None
    if file is not None:
        import os

        os.makedirs(_UPLOAD_DIR, exist_ok=True)
        ext = os.path.splitext(file.filename or "")[1] or ".txt"
        safe_name = f"{os.urandom(8).hex()}{ext}"
        file_path = os.path.join(_UPLOAD_DIR, safe_name)
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

    if not text and not file_path:
        raise HTTPException(status_code=400, detail="请提供合同文本或上传文件")

    try:
        contract_text = await parse_contract(text=text, file_path=file_path)
        items = await review_contract(contract_text, llm)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"合同解析失败：{exc}")

    # 落库（审计 + 合同记录），失败不影响响应
    try:
        from app.models.contract import Contract

        contract_title = title or (file.filename if file else "未命名合同")
        contract = Contract(
            title=contract_title,
            raw_text=contract_text[:100000],
            review_result=items,
            uploaded_by=user.id if user else None,
        )
        db.add(contract)
        await db.commit()
        await record_audit(
            db,
            action="contract.review",
            user_id=user.id if user else None,
            resource_type="contract",
            resource_id=str(contract.id),
            ip_address=request.client.host if request.client else None,
        )
    except Exception:
        await db.rollback()

    review_items = [ReviewItem(**item) for item in items]
    summary = f"共发现 {len(review_items)} 处风险点。"
    return ContractReviewResponse(items=review_items, summary=summary)