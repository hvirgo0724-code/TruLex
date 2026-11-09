"""Neo4j 关系图检索（官方 neo4j driver）。"""

from typing import Any, Dict, List, Optional

from neo4j import GraphDatabase

from app.core.config import settings

_driver = None


def get_driver():
    """返回全局 Neo4j 驱动（懒加载）。"""
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )
    return _driver


def close_driver() -> None:
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None


def _rows_to_dicts(records) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for record in records:
        for item in record.values():
            if item is None:
                continue
            if hasattr(item, "items"):
                result.append(dict(item))
            elif isinstance(item, dict):
                result.append(item)
    return result


# 允许创建的节点标签与关系类型（白名单，防止 Cypher 注入）
ALLOWED_LABELS = {"Law", "Case", "Concept", "Court", "Cause", "CRIME", "MONEY", "ORG", "Vehicle"}
ALLOWED_REL_TYPES = {"CITES", "INVOLVES", "TRIED_BY", "RELATES_TO", "MENTIONS"}


def _normalize_label(label: str) -> str:
    """Map extraction entity types to the graph's canonical labels."""
    return {"LAW": "Law", "CONCEPT": "Concept", "COURT": "Court",
            "CAUSE": "Cause", "CASE": "Case", "VEHICLE": "Vehicle"}.get(label, label)


def merge_node(label: str, name: str, props: Optional[Dict[str, Any]] = None) -> None:
    """按 name 幂等建/更新节点。label 需在白名单内。"""
    label = _normalize_label(label)
    if label not in ALLOWED_LABELS:
        raise ValueError(f"非法节点标签：{label}")
    driver = get_driver()
    cypher = f"MERGE (n:{label} {{name: $name}}) SET n += $props"
    with driver.session() as session:
        session.run(cypher, name=name, props=props or {})


def merge_relation(
    src_label: str, src_name: str, rel: str, dst_label: str, dst_name: str
) -> None:
    """幂等建关系：MERGE 头/尾节点 + MERGE 关系边。标签/关系类型需在白名单内。"""
    src_label = _normalize_label(src_label)
    dst_label = _normalize_label(dst_label)
    if src_label not in ALLOWED_LABELS or dst_label not in ALLOWED_LABELS:
        raise ValueError(f"非法节点标签：{src_label} / {dst_label}")
    if rel not in ALLOWED_REL_TYPES:
        raise ValueError(f"非法关系类型：{rel}")
    driver = get_driver()
    cypher = (
        f"MERGE (a:{src_label} {{name: $src_name}}) "
        f"MERGE (b:{dst_label} {{name: $dst_name}}) "
        f"MERGE (a)-[:{rel}]->(b)"
    )
    with driver.session() as session:
        session.run(cypher, src_name=src_name, dst_name=dst_name)


def query_related_nodes(keyword: str, limit: int = 5) -> List[Dict[str, Any]]:
    """按关键词查找相关法律节点（判例/法条/概念）。"""
    driver = get_driver()
    cypher = (
        "MATCH (n) "
        "WHERE (n.name CONTAINS $kw) OR (n.text CONTAINS $kw) "
        "RETURN n LIMIT $limit"
    )
    with driver.session() as session:
        records = session.run(cypher, kw=keyword, limit=limit)
        return _rows_to_dicts(records)


def query_citation_graph(case_name: str, limit: int = 10) -> List[Dict[str, Any]]:
    """查询判例引用的法条（判例 -> 引用 -> 法条的关系链路）。"""
    driver = get_driver()
    cypher = (
        "MATCH (c:Case)-[r:CITES]->(l:Law) "
        "WHERE c.name CONTAINS $name "
        "RETURN c.name AS case_name, type(r) AS relation, l.name AS law_name, l.text AS law_text "
        "LIMIT $limit"
    )
    with driver.session() as session:
        records = session.run(cypher, name=case_name, limit=limit)
        return [dict(r) for r in records]


def query_similar_cases(keyword: str, limit: int = 5) -> List[Dict[str, Any]]:
    """查找相似判例（同引用同一法条的判例）。"""
    driver = get_driver()
    cypher = (
        "MATCH (c1:Case)-[:CITES]->(l:Law)<-[:CITES]-(c2:Case) "
        "WHERE (c1.name CONTAINS $kw AND c1 <> c2) "
        "RETURN c2.name AS case_name, c2.text AS case_text, l.name AS law_name "
        "LIMIT $limit"
    )
    with driver.session() as session:
        records = session.run(cypher, kw=keyword, limit=limit)
        return [dict(r) for r in records]
