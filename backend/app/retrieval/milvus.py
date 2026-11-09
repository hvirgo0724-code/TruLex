"""Milvus 向量库：1024 维 collection 管理 + 稠密/稀疏(BM25)/混合(RRF)检索。

集合同时承载三类召回：
- 稠密向量（embedding，语义相似度）—— ``search``
- 稀疏向量（sparse，BM25 关键词）—— ``fulltext_search``
- 二者混合（RRF 融合）—— ``hybrid_search``（RAG 默认入口，替代原 Elasticsearch）

中文分词：BM25 使用 jieba 分析器 + 仅保留汉字/字母/数字的字符过滤器。
"""
from typing import Any, Dict, List, Optional

from pymilvus import (
    AnnSearchRequest,
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    Function,
    FunctionType,
    RRFRanker,
    connections,
    utility,
)

from app.core.config import settings

# 向量维度固定 1024（与 EMBEDDING_DIM 对齐）
DIM = 1024

# RRF 融合系数（k），越大越偏向召回而非排名差异
_RRF_K = 60

_FIELDS = [
    FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
    FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=128),
    FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=128),
    # enable_analyzer 使该字段可被 BM25 函数分词
    FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535, enable_analyzer=True,
                analyzer_params={"tokenizer": "jieba", "filter": ["cnalphanumonly"]}),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=DIM),
    # 稀疏向量字段：由下方 BM25 函数根据 text 自动生成，插入时无需手动填充
    FieldSchema(name="sparse", dtype=DataType.SPARSE_FLOAT_VECTOR),
    FieldSchema(name="meta", dtype=DataType.JSON),
]

_INDEX_PARAMS = {
    "metric_type": "IP",
    "index_type": "IVF_FLAT",
    "params": {"nlist": 128},
}

_SEARCH_PARAMS = {"metric_type": "IP", "params": {"nprobe": 16}}

_SPARSE_INDEX_PARAMS = {
    "index_type": "SPARSE_INVERTED_INDEX",
    "metric_type": "BM25",
}

_FTS_PARAMS = {"metric_type": "BM25"}

_OUTPUT_FIELDS = ["doc_id", "chunk_id", "text", "meta"]


def _bm25_function() -> Function:
    """构造 BM25 稀疏向量生成函数（中文 jieba 分词）。"""
    return Function(
        name="bm25",
        function_type=FunctionType.BM25,
        input_field_names=["text"],
        output_field_names="sparse",
    )


def _connect() -> None:
    """建立（幂等的）Milvus 连接。"""
    if not connections.has_connection("default"):
        connections.connect(alias="default", uri=settings.MILVUS_URI)


def ensure_collection() -> Collection:
    """确保 collection 存在（维度固定 1024，含 BM25 函数），并返回已加载的集合。

    注意：旧版（无 sparse/BM25）集合需先删除后重建：
        milvus drop collection 为 ``utility.drop_collection(settings.MILVUS_COLLECTION)``
    """
    _connect()
    if not utility.has_collection(settings.MILVUS_COLLECTION):
        schema = CollectionSchema(
            fields=_FIELDS, description="法律知识库向量集合（1024 维 + BM25 稀疏）"
        )
        schema.add_function(_bm25_function())
        collection = Collection(name=settings.MILVUS_COLLECTION, schema=schema)
        collection.create_index(field_name="embedding", index_params=_INDEX_PARAMS)
        collection.create_index(field_name="sparse", index_params=_SPARSE_INDEX_PARAMS)
    else:
        collection = Collection(name=settings.MILVUS_COLLECTION)
    collection.load()
    return collection


def get_collection() -> Collection:
    """获取已存在的集合对象（调用方负责 load）。"""
    _connect()
    return Collection(name=settings.MILVUS_COLLECTION)


def insert(
    doc_ids: List[str],
    chunk_ids: List[str],
    texts: List[str],
    embeddings: List[List[float]],
    metas: Optional[List[Dict[str, Any]]] = None,
) -> int:
    """批量写入向量；sparse 由 BM25 函数自动生成，返回插入条数。"""
    if not embeddings or len(embeddings[0]) != DIM:
        raise ValueError(f"向量维度必须为 {DIM}")
    n = len(texts)
    metas = metas or [{} for _ in range(n)]
    collection = ensure_collection()
    result = collection.insert(
        [
            doc_ids[:n],
            chunk_ids[:n],
            texts[:n],
            embeddings[:n],
            metas[:n],
        ]
    )
    collection.flush()
    return len(result.primary_keys)


def _parse_hits(results: Any) -> List[Dict[str, Any]]:
    hits: List[Dict[str, Any]] = []
    for hits_list in results:
        for hit in hits_list:
            entity = hit.entity
            hits.append(
                {
                    "score": float(hit.score),
                    "doc_id": entity.get("doc_id", ""),
                    "chunk_id": entity.get("chunk_id", ""),
                    "text": entity.get("text", ""),
                    "meta": entity.get("meta", {}),
                }
            )
    return hits


def search(
    query_vector: List[float],
    top_k: int = 5,
    filter_expr: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """稠密向量相似度检索，返回 [{score, doc_id, chunk_id, text, meta}]。"""
    if len(query_vector) != DIM:
        raise ValueError(f"查询向量维度必须为 {DIM}")
    collection = ensure_collection()
    results = collection.search(
        data=[query_vector],
        anns_field="embedding",
        param=_SEARCH_PARAMS,
        limit=top_k,
        expr=filter_expr,
        output_fields=_OUTPUT_FIELDS,
    )
    return _parse_hits(results)


def fulltext_search(
    query_text: str,
    top_k: int = 5,
    filter_expr: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """BM25 全文/keyword 检索，返回 [{score, doc_id, chunk_id, text, meta}]。"""
    collection = ensure_collection()
    results = collection.search(
        data=[query_text],
        anns_field="sparse",
        param=_FTS_PARAMS,
        limit=top_k,
        expr=filter_expr,
        output_fields=_OUTPUT_FIELDS,
    )
    return _parse_hits(results)


def hybrid_search(
    query_text: str,
    query_vector: List[float],
    top_k: int = 5,
    filter_expr: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """稠密(语义) + 稀疏(BM25) 混合检索，RRF 融合排序。"""
    if len(query_vector) != DIM:
        raise ValueError(f"查询向量维度必须为 {DIM}")
    collection = ensure_collection()

    dense_req = AnnSearchRequest(
        data=[query_vector],
        anns_field="embedding",
        param=_SEARCH_PARAMS,
        limit=top_k,
        expr=filter_expr,
    )
    sparse_req = AnnSearchRequest(
        data=[query_text],
        anns_field="sparse",
        param=_FTS_PARAMS,
        limit=top_k,
        expr=filter_expr,
    )

    results = collection.hybrid_search(
        [dense_req, sparse_req],
        RRFRanker(_RRF_K),
        limit=top_k,
        output_fields=_OUTPUT_FIELDS,
    )
    return _parse_hits(results)


def count() -> int:
    """返回集合内向量总数。"""
    collection = ensure_collection()
    return collection.num_entities
