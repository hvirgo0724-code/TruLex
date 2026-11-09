# -*- coding: utf-8 -*-
"""入库 Neo4j：读取 rag_data/neo4j/{nodes,relations}.jsonl，幂等写入图库。

用法（在 backend 容器内，backend 目录为 /app）：
    python scripts/ingest_neo4j.py
    python scripts/ingest_neo4j.py --data_dir rag_data/neo4j

依赖：neo4j driver（见 backend/requirements.txt），需先启动 Neo4j。
运行前请先执行 `python scripts/generate_rag_data.py` 生成节点/关系数据。
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_ROOT = os.path.dirname(HERE)
sys.path.insert(0, BACKEND_ROOT)

from app.retrieval import neo4j  # noqa: E402

DATA_DIR = os.path.join(BACKEND_ROOT, "rag_data", "neo4j")


def load_jsonl(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError("数据文件不存在：%s" % path)
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def ingest(data_dir: str) -> None:
    nodes = load_jsonl(os.path.join(data_dir, "nodes.jsonl"))
    relations = load_jsonl(os.path.join(data_dir, "relations.jsonl"))

    for n in nodes:
        neo4j.merge_node(n["type"], n["name"], n.get("props") or {})

    for r in relations:
        neo4j.merge_relation(
            r["src_type"], r["src_name"], r["rel"],
            r["dst_type"], r["dst_name"],
        )

    print("完成：写入节点 %d 个、关系 %d 条" % (len(nodes), len(relations)))


def main() -> None:
    parser = argparse.ArgumentParser(description="入库 Neo4j 图库")
    parser.add_argument("--data_dir", type=str, default=DATA_DIR)
    args = parser.parse_args()

    try:
        ingest(args.data_dir)
    finally:
        neo4j.close_driver()


if __name__ == "__main__":
    main()