# -*- coding: utf-8 -*-
"""RAG 端到端验证脚本（宿主机直连容器内 Milvus/Neo4j）。

用途：在不启动 backend 容器的情况下，验证「语料入库 -> 混合检索」链路可用。

依赖：pymilvus / neo4j / langchain-openai / python-dotenv
用法：在 backend 目录下执行 `python scripts/verify_rag_local.py`
"""
import json
import os
import sys

from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.dirname(HERE)
sys.path.insert(0, BACKEND_ROOT)

load_dotenv(os.path.join(BACKEND_ROOT, "..", ".env"))

# 宿主机直连地址（容器端口已映射到 localhost）
MILVUS_URI = os.getenv("MILVUS_URI", "http://localhost:19530").replace(
    "http://milvus:19530", "http://localhost:19530")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687").replace(
    "bolt://neo4j:7687", "bolt://localhost:7687")

from pymilvus import (  # noqa: E402
    AnnSearchRequest, Collection, CollectionSchema, DataType, FieldSchema,
    Function, FunctionType, RRFRanker, connections, utility,
)
from langchain_openai import OpenAIEmbeddings  # noqa: E402
from neo4j import GraphDatabase  # noqa: E402

DIM = int(os.getenv("EMBEDDING_DIM", "1024"))
COLLECTION = os.getenv("MILVUS_COLLECTION", "legal_knowledge")
DATA_DIR = os.path.join(BACKEND_ROOT, "rag_data")


def get_embeddings():
    return OpenAIEmbeddings(
        model=os.getenv("EMBEDDING_MODEL", "qwen3.7-text-embedding"),
        api_key=os.getenv("API_KEY"),
        base_url=os.getenv("BASE_URL"),
        dimensions=DIM,
        check_embedding_ctx_length=False,
        chunk_size=int(os.getenv("EMBEDDING_CHUNK_SIZE", "10")),
    )


def load_rows(path):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def setup_milvus():
    connections.connect(alias="default", uri=MILVUS_URI)
    if utility.has_collection(COLLECTION):
        utility.drop_collection(COLLECTION)  # 重建，避免旧 schema 冲突
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=128),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535, enable_analyzer=True,
                    analyzer_params={"tokenizer": "jieba", "filter": ["cnalphanumonly"]}),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=DIM),
        FieldSchema(name="sparse", dtype=DataType.SPARSE_FLOAT_VECTOR),
        FieldSchema(name="meta", dtype=DataType.JSON),
    ]
    schema = CollectionSchema(fields=fields, description="物流法律知识库")
    schema.add_function(Function(
        name="bm25", function_type=FunctionType.BM25,
        input_field_names=["text"], output_field_names="sparse"))
    col = Collection(name=COLLECTION, schema=schema)
    col.create_index("embedding", {"metric_type": "IP", "index_type": "IVF_FLAT",
                                   "params": {"nlist": 128}})
    col.create_index("sparse", {"index_type": "SPARSE_INVERTED_INDEX", "metric_type": "BM25"})
    col.load()
    return col


def ingest_milvus(col, emb):
    total = 0
    for name in ["statutes.jsonl", "cases.jsonl", "knowledge.jsonl"]:
        rows = load_rows(os.path.join(DATA_DIR, "milvus", name))
        texts = [r["text"] for r in rows if r.get("text")]
        doc_ids = [r["doc_id"] for r in rows if r.get("text")]
        metas = [{k: v for k, v in r.items() if k not in ("doc_id", "text")}
                 for r in rows if r.get("text")]
        for i in range(0, len(texts), 16):
            bt = texts[i:i + 16]
            bd = doc_ids[i:i + 16]
            bm = metas[i:i + 16]
            vecs = emb.embed_documents(bt)
            col.insert([bd, bd, bt, vecs, bm])
        total += len(texts)
        print(f"  入库 {name}: {len(texts)} 条")
    col.flush()
    print(f"Milvus 共写入 {total} 条向量")
    return total


def ingest_neo4j():
    driver = GraphDatabase.driver(NEO4J_URI, auth=("neo4j", os.getenv("NEO4J_PASSWORD")))
    nodes = load_rows(os.path.join(DATA_DIR, "neo4j", "nodes.jsonl"))
    rels = load_rows(os.path.join(DATA_DIR, "neo4j", "relations.jsonl"))
    with driver.session() as s:
        s.run("MATCH (n) DETACH DELETE n")
        for n in nodes:
            s.run(f"MERGE (n:{n['type']} {{name: $name}}) SET n += $props",
                  name=n["name"], props=n.get("props") or {})
        for r in rels:
            s.run(f"MERGE (a:{r['src_type']} {{name: $sn}}) "
                  f"MERGE (b:{r['dst_type']} {{name: $dn}}) "
                  f"MERGE (a)-[:{r['rel']}]->(b)",
                  sn=r["src_name"], dn=r["dst_name"])
    driver.close()
    print(f"Neo4j 写入节点 {len(nodes)} 个、关系 {len(rels)} 条")
    return len(nodes), len(rels)


def hybrid_search(col, query, emb, top_k=3):
    vec = emb.embed_query(query)
    dense = AnnSearchRequest(data=[vec], anns_field="embedding",
                             param={"metric_type": "IP", "params": {"nprobe": 16}},
                             limit=top_k)
    sparse = AnnSearchRequest(data=[query], anns_field="sparse",
                              param={"metric_type": "BM25"}, limit=top_k)
    res = col.hybrid_search([dense, sparse], RRFRanker(60), limit=top_k,
                            output_fields=["doc_id", "text", "meta"])
    out = []
    for h in res[0]:
        e = h.entity
        out.append({"score": round(float(h.score), 3),
                    "title": (e.get("meta") or {}).get("title", ""),
                    "text": (e.get("text") or "")[:60]})
    return out


def main():
    print("=" * 60)
    print("途律 · TruLex RAG 端到端验证")
    print(f"  Milvus: {MILVUS_URI}   Neo4j: {NEO4J_URI}  维度: {DIM}")
    print("=" * 60)

    emb = get_embeddings()
    print("\n[1/3] 建立 Milvus collection 并入库...")
    col = setup_milvus()
    ingest_milvus(col, emb)

    print("\n[2/3] 入库 Neo4j 知识图谱...")
    ingest_neo4j()

    print("\n[3/3] 混合检索验证（BM25 + 稠密向量 RRF 融合）...")
    queries = [
        "快递丢失了怎么赔偿？",
        "公路货运中货物毁损灭失，承运人承担什么责任？",
        "危险货物运输有什么特别规定？",
    ]
    for q in queries:
        print(f"\n  查询：{q}")
        for hit in hybrid_search(col, q, emb, top_k=3):
            print(f"    [{hit['score']}] {hit['title']} | {hit['text']}")

    print("\n" + "=" * 60)
    print(f"验证完成：Milvus 向量数 = {col.num_entities}")
    print("=" * 60)


if __name__ == "__main__":
    main()
