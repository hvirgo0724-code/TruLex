"""文档上传 / 入库接口（触发 Celery 异步任务）。"""

import os
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_optional, get_db
from app.models.document import Document
from app.models.user import User
from app.schemas.document import DocumentUploadResponse
from app.services.audit import record_audit

router = APIRouter(prefix="/documents", tags=["documents"])

_UPLOAD_DIR = "/tmp/legal_uploads"


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload(
    request: Request,
    file: UploadFile = File(...),
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> DocumentUploadResponse:
    """上传文档，保存文件并触发 Celery 入库任务。"""
    if file is None:
        raise HTTPException(status_code=400, detail="缺少文件")

    os.makedirs(_UPLOAD_DIR, exist_ok=True)
    filename = file.filename or "unnamed.txt"
    ext = os.path.splitext(filename)[1] or ".txt"
    safe_name = f"{os.urandom(8).hex()}{ext}"
    path = os.path.join(_UPLOAD_DIR, safe_name)

    content = await file.read()
    with open(path, "wb") as f:
        f.write(content)

    doc = Document(
        title=filename,
        source_type="upload",
        file_path=path,
        content=None,
        status="pending",
        uploaded_by=user.id if user else None,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # 触发 Celery 异步入库
    try:
        from app.tasks.knowledge import ingest_document

        task = ingest_document.delay(doc.id)
        task_id = task.id
    except Exception:
        task_id = None

    await record_audit(
        db,
        action="document.upload",
        user_id=user.id if user else None,
        resource_type="document",
        resource_id=str(doc.id),
        ip_address=request.client.host if request.client else None,
    )

    return DocumentUploadResponse(document_id=doc.id, task_id=task_id)