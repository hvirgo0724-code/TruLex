"""知识库入库 / 向量重算 Celery 任务。

入库流程：读取文档 -> 分块 -> 向量化（Embedding）-> 写入 Milvus（稠密 + BM25 稀疏）。
"""

import asyncio
import hashlib
from typing import Any, Dict, List

from app.llm.embeddings import get_embeddings
from app.retrieval import milvus
from app.tasks.celery_app import celery_app

_CHUNK_SIZE = 1000
_CHUNK_OVERLAP = 100


def _chunk_text(text: str, chunk_size: int = _CHUNK_SIZE, overlap: int = _CHUNK_OVERLAP) -> List[str]:
    """按固定长度切块（带重叠），简单可靠。"""
    text = (text or "").strip()
    if not text:
        return []
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap
    return chunks


async def _ingest_document(document_id: int) -> Dict[str, Any]:
    """实际入库逻辑（asyncio）。"""
    from sqlalchemy import select

    from app.db.session import async_session_factory
    from app.models.document import Document

    async with async_session_factory() as db:
        doc = await db.get(Document, document_id)
        if doc is None:
            return {"status": "failed", "reason": "文档不存在"}
        doc.status = "processing"
        await db.commit()

        content = doc.content or ""
        if not content and doc.file_path:
            from app.agents.tools import _parse_contract_file

            try:
                loop = asyncio.get_running_loop()
                content = await loop.run_in_executor(None, _parse_contract_file, doc.file_path)
            except Exception:
                content = ""

        chunks = _chunk_text(content)
        if not chunks:
            doc.status = "failed"
            await db.commit()
            return {"status": "failed", "reason": "无可入库内容"}

        embeddings = get_embeddings()
        doc_ids: List[str] = []
        chunk_ids: List[str] = []
        texts: List[str] = []
        vectors: List[List[float]] = []
        metas: List[Dict[str, Any]] = []

        for i, chunk in enumerate(chunks):
            vec = await embeddings.aembed_query(chunk)
            chunk_id = hashlib.md5(f"{document_id}:{i}".encode("utf-8")).hexdigest()
            doc_ids.append(str(document_id))
            chunk_ids.append(chunk_id)
            texts.append(chunk)
            vectors.append(vec)
            metas.append({"title": doc.title, "source_type": doc.source_type})

        # 写入向量库（稠密向量 + BM25 稀疏向量，由集合内 bm25 函数基于 text 自动生成）
        milvus.insert(doc_ids, chunk_ids, texts, vectors, metas)

        doc.status = "done"
        doc.chunk_count = len(chunks)
        await db.commit()

        return {"status": "done", "chunk_count": len(chunks)}


@celery_app.task(name="app.tasks.knowledge.ingest_document", bind=True)
def ingest_document(self, document_id: int, **kwargs: Any) -> Dict[str, Any]:
    """知识库文档入库任务。"""
    try:
        return asyncio.run(_ingest_document(document_id))
    except Exception as exc:  # noqa: BLE001
        return {"status": "failed", "reason": str(exc)}


@celery_app.task(name="app.tasks.knowledge.recompute_vectors", bind=True)
def recompute_vectors(self, document_id: int, **kwargs: Any) -> Dict[str, Any]:
    """向量重算任务（模型升级后重建向量）。"""
    # 简化实现：复用 ingest 流程
    return ingest_document.apply(args=[document_id], kwargs=kwargs)