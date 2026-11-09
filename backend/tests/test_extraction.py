"""途律 · TruLex —— 实体与关系抽取单元测试。"""
from app.retrieval.extraction import (
    extract,
    extract_entities,
    extract_relations,
)


def test_extract_law_entity():
    """抽取法条实体（含条文号）。"""
    text = "依据《民法典》第832条规定，承运人对运输过程中货物的毁损、灭失承担赔偿责任。"
    entities = extract_entities(text)
    laws = [e for e in entities if e["type"] == "LAW"]
    assert any(e["name"] == "《民法典》第832条" for e in laws)
    law = [e for e in laws if e["name"] == "《民法典》第832条"][0]
    assert law["meta"]["law_name"] == "民法典"
    assert law["meta"]["article"] == "832"


def test_extract_money_entity():
    """抽取金额实体。"""
    text = "托运人主张承运人赔偿全部货损，损失金额500000元。"
    entities = extract_entities(text)
    moneys = [e["name"] for e in entities if e["type"] == "MONEY"]
    assert "500000元" in moneys


def test_extract_org_entity():
    """抽取组织实体。"""
    text = "某物流有限公司与某制造有限责任公司签订运输合同。"
    entities = extract_entities(text)
    orgs = [e["name"] for e in entities if e["type"] == "ORG"]
    assert "某物流有限公司" in orgs
    assert "某制造有限责任公司" in orgs


def test_extract_vehicle_entity():
    """抽取运输工具实体。"""
    text = "运输危险货物的罐式车辆未配备押运人员。"
    entities = extract_entities(text)
    vehicles = [e["name"] for e in entities if e["type"] == "VEHICLE"]
    assert "罐式车辆" in vehicles


def test_extract_concept_entity():
    """抽取物流法律概念。"""
    text = "本案涉及保价运输、承运人责任险与不可抗力免责事由。"
    entities = extract_entities(text)
    concepts = [e["name"] for e in entities if e["type"] == "CONCEPT"]
    assert "保价运输" in concepts
    assert "不可抗力" in concepts


def test_extract_cause_entity():
    """抽取案由实体。"""
    text = "本案系一起公路货物运输合同纠纷。"
    entities = extract_entities(text)
    causes = [e["name"] for e in entities if e["type"] == "CAUSE"]
    assert "公路货物运输合同纠纷" in causes


def test_extract_dedup():
    """验证实体去重。"""
    text = "承运人承担赔偿责任，承运人应赔偿损失。"
    entities = extract_entities(text)
    concepts = [e for e in entities if e["type"] == "CONCEPT" and e["name"] == "承运人"]
    assert len(concepts) == 1


def test_extract_relations_cites():
    """验证判例引用法条的关系抽取。"""
    text = "依据《民法典》第832条，承运人对货物毁损灭失承担赔偿责任。本案系公路货物运输合同纠纷。"
    result = extract(text, source={"type": "Case", "name": "某物流运输纠纷案"})
    relations = result["relations"]
    cites = [r for r in relations if r["rel"] == "CITES"]
    assert any(r["dst_name"] == "《民法典》第832条" and r["src_name"] == "某物流运输纠纷案"
               for r in cites)


def test_extract_relations_involves():
    """验证判例涉及案由的关系抽取。"""
    text = "本案系一起海上货物运输合同纠纷。"
    result = extract(text, source={"type": "Case", "name": "某海运纠纷案"})
    relations = result["relations"]
    involves = [r for r in relations if r["rel"] == "INVOLVES"]
    assert any(r["dst_name"] == "海上货物运输合同纠纷" for r in involves)
