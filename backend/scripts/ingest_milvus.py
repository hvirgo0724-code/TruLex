# -*- coding: utf-8 -*-
"""入库 Milvus：读取 rag_data/milvus/*.jsonl，向量化后写入向量库。

用法（在 backend 容器内，backend 目录为 /app）：
    python scripts/ingest_milvus.py
    python scripts/ingest_milvus.py --files statutes,cases --batch_size 16

依赖：pymilvus + langchain-openai（见 backend/requirements.txt），
需先启动 Milvus（docker compose up -d milvus etcd minio）。
运行前请先执行 `python scripts/generate_rag_data.py` 生成原始数据。
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.dirname(HERE)
sys.path.insert(0, BACKEND_ROOT)

from app.llm.embeddings import get_embeddings  # noqa: E402
from app.retrieval import milvus  # noqa: E402

DATA_DIR = os.path.join(BACKEND_ROOT, "rag_data", "milvus")
FILES = ["statutes.jsonl", "cases.jsonl", "knowledge.jsonl"]


def load_rows(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError("数据文件不存在：%s，请先运行 generate_rag_data.py" % path)
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def ingest_file(path: str, embeddings, batch_size: int) -> int:
    rows = load_rows(path)
    if not rows:
        return 0

    # 单条 text 单向量入库；meta 为除 doc_id/text 外的其余字段
    texts = [r["text"] for r in rows if r.get("text")]
    doc_ids = [r["doc_id"] for r in rows if r.get("text")]
    metas = [{k: v for k, v in r.items() if k not in ("doc_id", "text")}
             for r in rows if r.get("text")]

    total = 0
    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i:i + batch_size]
        batch_docs = doc_ids[i:i + batch_size]
        batch_metas = metas[i:i + batch_size]
        vectors = embeddings.embed_documents(batch_texts)
        chunk_ids = batch_docs  # 单 chunk，doc_id == chunk_id
        total += milvus.insert(batch_docs, chunk_ids, batch_texts, vectors, batch_metas)
        print("  已写入 %s 第 %d~%d 条" % (os.path.basename(path), i + 1,
                                           min(i + batch_size, len(texts))))
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="入库 Milvus 向量库")
    parser.add_argument("--data_dir", type=str, default=DATA_DIR)
    parser.add_argument("--files", type=str, default=",".join(FILES),
                        help="逗号分隔的文件名，默认全部")
    parser.add_argument("--batch_size", type=int, default=16)
    args = parser.parse_args()

    embeddings = get_embeddings()
    selected = [f.strip() for f in args.files.split(",") if f.strip()]

    grand_total = 0
    for name in selected:
        path = os.path.join(args.data_dir, name)
        print("入库 %s ..." % name)
        grand_total += ingest_file(path, embeddings, args.batch_size)

    print("完成：共写入 %d 条向量（collection 内现有 %d 条）"
          % (grand_total, milvus.count()))


if __name__ == "__main__":
    main()