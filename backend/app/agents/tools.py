"""Agent 工具函数集合。

- ``search_statutes``：Milvus 混合检索（BM25 + 稠密向量）法条检索
- ``search_cases``：Milvus 混合检索 + Neo4j 判例检索
- ``search_knowledge``：Milvus 通用知识检索
- ``parse_contract``：python-docx / pdfplumber 解析合同文件
"""

import asyncio
from typing import Any, Dict, List, Optional

from app.llm.embeddings import get_embeddings
from app.retrieval import milvus
from app.retrieval import neo4j


def _merge_dedup(*hit_lists: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """合并去重多个检索结果（按 text 前 80 字符去重）。"""
    seen = set()
    merged: List[Dict[str, Any]] = []
    for hits in hit_lists:
        for h in hits:
            key = (h.get("text") or "")[:80]
            if key and key in seen:
                continue
            seen.add(key)
            merged.append(h)
    return merged


async def _embed_query(query: str) -> List[float]:
    embeddings = get_embeddings()
    return await embeddings.aembed_query(query)


async def search_statutes(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """检索物流交通法规：Milvus 混合检索（BM25 + 稠密向量），按 source_type=statute 过滤。"""
    results: List[Dict[str, Any]] = []
    try:
        vector = await _embed_query(query)
        loop = asyncio.get_running_loop()
        hits = await loop.run_in_executor(
            None,
            lambda: milvus.hybrid_search(
                query, vector, top_k=top_k,
                filter_expr='meta["source_type"] == "statute"',
            ),
        )
        for hit in hits:
            hit["source"] = "statute"
            hit["title"] = (hit.get("meta") or {}).get("title") or \
                (hit.get("meta") or {}).get("law_name", "法规")
            results.append(hit)
    except Exception:
        pass
    for r in results:
        r.setdefault("source", "statute")
        r.setdefault("title", r.get("title") or "法规")
    return results[:top_k]


async def search_cases(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """检索物流交通判例：Milvus 混合检索（按 source_type=case 过滤）+ Neo4j 关系图补充。"""
    results: List[Dict[str, Any]] = []
    try:
        vector = await _embed_query(query)
        loop = asyncio.get_running_loop()
        hits = await loop.run_in_executor(
            None,
            lambda: milvus.hybrid_search(
                query, vector, top_k=top_k,
                filter_expr='meta["source_type"] == "case"',
            ),
        )
        for hit in hits:
            hit["source"] = "case"
            hit["title"] = (hit.get("meta") or {}).get("title") or \
                (hit.get("meta") or {}).get("case_name", "判例")
            results.append(hit)
    except Exception:
        pass
    try:
        loop = asyncio.get_running_loop()
        graph_hits = await loop.run_in_executor(
            None, neo4j.query_similar_cases, query, top_k
        )
        for g in graph_hits:
            results.append(
                {
                    "source": "case",
                    "title": g.get("case_name", "判例"),
                    "text": g.get("case_text", ""),
                    "meta": {"law_name": g.get("law_name", "")},
                    "score": 0.0,
                }
            )
    except Exception:
        pass
    for r in results:
        r.setdefault("source", "case")
        r.setdefault("title", r.get("title") or "判例")
    return results[:top_k]


async def search_knowledge(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """通用知识库检索：仅 Milvus 向量，返回结果保留真实来源类型（法规/判例/概念）。"""
    try:
        vector = await _embed_query(query)
        loop = asyncio.get_running_loop()
        hits = await loop.run_in_executor(None, milvus.search, vector, top_k)
    except Exception:
        return []
    for h in hits:
        meta = h.get("meta") or {}
        # 优先用真实来源类型，回退为 knowledge
        h["source"] = meta.get("source_type", "knowledge")
        h.setdefault("title", meta.get("title", "知识库"))
    return hits


# ------------------------------------------------------------------ #
# 合同解析（同步 IO，供 async 工具经 to_thread 调用）
# ------------------------------------------------------------------ #
def _parse_contract_file(file_path: str) -> str:
    """解析 .docx / .pdf / .txt 合同文件为纯文本。"""
    if not file_path:
        return ""
    lower = file_path.lower()
    if lower.endswith(".docx"):
        import docx

        doc = docx.Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs if p.text)
    if lower.endswith(".pdf"):
        import pdfplumber

        parts: List[str] = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                parts.append(text)
        return "\n".join(parts)
    # 默认按文本读取
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


async def parse_contract(
    text: Optional[str] = None, file_path: Optional[str] = None
) -> str:
    """解析合同：优先返回传入文本，否则解析文件路径。"""
    if text:
        return text
    if not file_path:
        return ""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _parse_contract_file, file_path)


TOOLS: Dict[str, Any] = {
    "search_statutes": search_statutes,
    "search_cases": search_cases,
    "search_knowledge": search_knowledge,
    "parse_contract": parse_contract,
}