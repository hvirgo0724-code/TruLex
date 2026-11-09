# -*- coding: utf-8 -*-
"""物流交通运输法律实体抽取与关系抽取（规则优先，可选 LLM 兜底）。

无第三方依赖即可运行；LLM 抽取作为可选增强（需 langchain + DashScope）。

实体类型（type）：
    LAW       法条（识别「《法律名》第X条」）
    CONCEPT   物流法律概念（内置词典）
    CAUSE     案由 / 纠纷类型（内置词典）
    COURT     法院 / 仲裁机构
    CRIME     罪名（识别「……罪」）
    MONEY     金额
    ORG       组织（识别「……公司」等）
    VEHICLE   运输工具 / 运输方式（货车、船舶、航空器、铁路等）

关系类型（rel）：
    CITES       Case -> Law（判例援引法条）
    INVOLVES    Case -> Cause（判例涉及的纠纷类型）
    TRIED_BY    Case -> Court（审理法院）
    RELATES_TO  Concept -> Law（概念与法条关联）
    MENTIONS    Case -> ORG/MONEY/VEHICLE（判例提及的组织/金额/运输方式）
"""
import re
from typing import Any, Dict, List, Optional

# --------------------------------------------------------------------------- #
# 词典与正则
# --------------------------------------------------------------------------- #
CONCEPT_LIST = [
    "承运人", "托运人", "收货人", "多式联运经营人", "实际承运人", "缔约承运人",
    "货损货差", "承运人责任期间", "保价运输", "保价", "承运人责任险", "保价额",
    "不可抗力", "合理损耗", "留置权", "提存", "快件验视", "验视", "超限超载",
    "超载", "危险货物", "危险化学品", "适航义务", "管货义务", "共同海损",
    "迟延交付", "迟延", "快件丢失", "快件延误", "内件短少", "违约金", "连带责任",
    "赔偿限额", "免责", "诉讼时效", "举证责任", "货物损毁", "货物灭失",
    "多式联运单据", "提单", "航空货运单", "运单", "货运运单", "集装箱",
]

CAUSE_LIST = [
    "公路货物运输合同纠纷", "铁路货物运输合同纠纷", "航空货物运输合同纠纷",
    "海上货物运输合同纠纷", "快递服务合同纠纷", "仓储合同纠纷",
    "多式联运合同纠纷", "运输合同纠纷", "货运代理合同纠纷",
    "机动车交通事故责任纠纷", "保险人代位求偿权纠纷", "保管合同纠纷",
    "委托合同纠纷", "危险货物运输合同纠纷", "物流服务合同纠纷",
]

VEHICLE_LIST = [
    "货车", "厢式货车", "危险货物运输车辆", "罐式车辆", "船舶", "海船",
    "航空器", "飞机", "铁路", "列车", "集装箱", "牵引车", "挂车",
]

_LAW_RE = re.compile(r"《([^》]{2,40})》(?:第([0-9一二三四五六七八九十百零千]+)条)?")
_COURT_RE = re.compile(r"([\u4e00-\u9fff]{2,12}(?:人民法院|互联网法院|海事法院|仲裁委员会|仲裁委))")
_CRIME_RE = re.compile(r"([\u4e00-\u9fff]{2,6}罪)")
_MONEY_RE = re.compile(r"([0-9]+(?:\.[0-9]{1,2})?(?:万元|千元|百元|元))")
# 公司名前的字符集合排除「与/和/及/、/，/。」等连接词与标点，避免贪婪匹配吞并多个主体
_ORG_RE = re.compile(
    r"([\u4e00-\u9fff]{2,20}?(?:有限责任公司|股份有限公司|有限公司|集团|公司))"
)

# 噪音罪名（非具体罪名的「罪」结尾词）
_CRIME_NOISE = {"犯罪", "无罪", "有罪", "治罪", "问罪"}


# --------------------------------------------------------------------------- #
# 实体抽取
# --------------------------------------------------------------------------- #
def _dedup(entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen, out = set(), []
    for e in entities:
        key = (e["type"], e["name"])
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


def extract_entities(text: str) -> List[Dict[str, Any]]:
    """从物流法律文本中抽取结构化实体（纯规则，返回 [{type, name, meta}]）。"""
    text = text or ""
    entities: List[Dict[str, Any]] = []

    # 法条（含条文号）
    for m in _LAW_RE.finditer(text):
        law = m.group(1)
        article = m.group(2)
        name = f"《{law}》" + (f"第{article}条" if article else "")
        entities.append({"type": "LAW", "name": name,
                         "meta": {"law_name": law, "article": article or ""}})

    # 法院 / 仲裁机构
    for m in _COURT_RE.finditer(text):
        entities.append({"type": "COURT", "name": m.group(1), "meta": {}})

    # 罪名（过滤通用「犯罪」等噪音）
    for m in _CRIME_RE.finditer(text):
        name = m.group(1)
        if name in _CRIME_NOISE:
            continue
        entities.append({"type": "CRIME", "name": name, "meta": {}})

    # 金额
    for m in _MONEY_RE.finditer(text):
        entities.append({"type": "MONEY", "name": m.group(1), "meta": {}})

    # 组织（公司/集团）
    for m in _ORG_RE.finditer(text):
        name = m.group(1)
        # 清理前导连接词/标点（如「与某制造有限责任公司」→「某制造有限责任公司」）
        name = re.sub(r"^[\u4e0e\u548c\u53ca\u4e0e\u3001\uff0c\u3002\uff0c\s]+", "", name)
        if name:
            entities.append({"type": "ORG", "name": name, "meta": {}})

    # 运输工具 / 运输方式
    for v in sorted(VEHICLE_LIST, key=len, reverse=True):
        if v in text:
            entities.append({"type": "VEHICLE", "name": v, "meta": {}})

    # 法律概念（词典精确匹配，按长度降序避免子串误判）
    for concept in sorted(CONCEPT_LIST, key=len, reverse=True):
        if concept in text:
            entities.append({"type": "CONCEPT", "name": concept, "meta": {}})

    # 案由（词典匹配）
    for cause in sorted(CAUSE_LIST, key=len, reverse=True):
        if cause in text:
            entities.append({"type": "CAUSE", "name": cause, "meta": {}})

    return _dedup(entities)


# --------------------------------------------------------------------------- #
# 关系抽取
# --------------------------------------------------------------------------- #
def _rel(src_type: str, src_name: str, rel: str, dst_type: str, dst_name: str) -> Dict[str, str]:
    return {
        "src_type": src_type,
        "src_name": src_name,
        "rel": rel,
        "dst_type": dst_type,
        "dst_name": dst_name,
    }


def extract_relations(
    source: Optional[Dict[str, Any]],
    entities: List[Dict[str, Any]],
    concept_law_map: Optional[Dict[str, List[str]]] = None,
) -> List[Dict[str, Any]]:
    """基于实体列表生成关系边。

    source: 当前文档信息，如 {"type": "Case", "name": "某物流公司运输纠纷案"}；
            为使 `(Case)-[:CITES]->(Law)` 成立，source.type 应为 "Case"。
    concept_law_map: 可选，概念 -> 法条名列表，用于生成 Concept-RELATES_TO-Law。
    """
    relations: List[Dict[str, Any]] = []
    laws = [e for e in entities if e["type"] == "LAW"]
    causes = [e for e in entities if e["type"] == "CAUSE"]
    courts = [e for e in entities if e["type"] == "COURT"]

    if source and source.get("type") == "Case":
        src_name = source.get("name", "")
        for law in laws:
            relations.append(_rel("Case", src_name, "CITES", "LAW", law["name"]))
        for cause in causes:
            relations.append(_rel("Case", src_name, "INVOLVES", "CAUSE", cause["name"]))
        for court in courts:
            relations.append(_rel("Case", src_name, "TRIED_BY", "COURT", court["name"]))
        # 运输方式 / 金额 / 组织关联
        for ent in entities:
            if ent["type"] in ("VEHICLE", "MONEY", "ORG"):
                relations.append(_rel("Case", src_name, "MENTIONS",
                                      ent["type"], ent["name"]))

    # 概念与法条的关联（可来自显式映射，否则同句共现兜底）
    concept_law_map = concept_law_map or {}
    for concept in [e for e in entities if e["type"] == "CONCEPT"]:
        mapped = concept_law_map.get(concept["name"], [])
        for law in laws:
            law_name = law.get("meta", {}).get("law_name", "")
            if law_name and law_name in mapped:
                relations.append(_rel("CONCEPT", concept["name"], "RELATES_TO",
                                      "LAW", law["name"]))
    return relations


# --------------------------------------------------------------------------- #
# 可选 LLM 兜底（需安装 langchain + DashScope；未配置时静默返回空）
# --------------------------------------------------------------------------- #
_LLM_EXTRACT_PROMPT = (
    "你是物流交通运输法律信息抽取器。从给定法律文本中抽取实体与关系，仅输出 JSON。"
    "实体类型限定：LAW / CONCEPT / CAUSE / COURT / CRIME / MONEY / ORG / VEHICLE。"
    "关系类型限定：CITES（判例->法条）、INVOLVES（判例->案由）、TRIED_BY（判例->法院）、"
    "MENTIONS（判例->组织/金额/运输方式）。"
    "输出格式：{\"entities\":[{\"type\":\"\",\"name\":\"\"}],"
    "\"relations\":[{\"src_type\":\"\",\"src_name\":\"\",\"rel\":\"\",\"dst_type\":\"\",\"dst_name\":\"\"}]}"
)


def extract_with_llm(text: str) -> Dict[str, Any]:
    """可选增强：调用 LLM 做开放域抽取；环境未就绪时返回空结果（调用方自行降级）。"""
    try:
        from langchain_openai import ChatOpenAI

        from app.core.config import settings
    except Exception:  # pragma: no cover - 依赖缺失时降级为规则结果
        return {"entities": [], "relations": []}

    try:
        model = ChatOpenAI(
            model=settings.MODEL_NAME,
            api_key=settings.API_KEY,
            base_url=settings.BASE_URL,
            temperature=0.0,
        )
        resp = model.invoke(_LLM_EXTRACT_PROMPT + "\n文本：" + text)
        content = getattr(resp, "content", "") or str(resp)
        import json

        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1:
            return {"entities": [], "relations": []}
        return json.loads(content[start:end + 1])
    except Exception:  # noqa: BLE001
        return {"entities": [], "relations": []}


def extract(
    text: str,
    source: Optional[Dict[str, Any]] = None,
    use_llm: bool = False,
    concept_law_map: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, Any]:
    """统一入口：优先规则，可选 LLM 兜底；返回 {entities, relations}。"""
    entities = extract_entities(text)
    relations = extract_relations(source, entities, concept_law_map=concept_law_map)

    if use_llm:
        llm_result = extract_with_llm(text)
        llm_entities = llm_result.get("entities", []) or []
        llm_relations = llm_result.get("relations", []) or []
        entities = _dedup(entities + [{"type": e.get("type", ""),
                                       "name": e.get("name", ""),
                                       "meta": {}} for e in llm_entities])
        seen_rel = {(r["src_type"], r["src_name"], r["rel"],
                     r["dst_type"], r["dst_name"]) for r in relations}
        for r in llm_relations:
            key = (r.get("src_type"), r.get("src_name"), r.get("rel"),
                   r.get("dst_type"), r.get("dst_name"))
            if key not in seen_rel:
                relations.append(r)
                seen_rel.add(key)

    return {"entities": entities, "relations": relations}
