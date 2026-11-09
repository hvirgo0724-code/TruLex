"""物流运输合同/运单解析 + 审查：返回风险点 + 条款高亮片段。

规则库先行（确定性、可解释），LLM 增强失败时自动降级为纯规则结果。

面向物流交通运输场景：公路货运、快递寄递、铁路、航空、水运海商、
仓储、多式联运等运输合同的合规风险识别。
"""

import re
from typing import Any, Dict, List, Optional

# (关键词, 风险等级, 审查建议) —— 物流运输合同风险规则库
_RISK_RULES: List[tuple] = [
    ("未保价", "high", "未保价货物发生毁损灭失时赔偿可能受限，建议提示托运人办理保价并明确保价规则。"),
    ("保价", "medium", "保价规则与保价额应明确，避免贵重物品因未声明而无法足额获赔。"),
    ("赔偿限额", "high", "赔偿限额条款可能低于法定或实际损失，建议评估是否显失公平并明确适用情形。"),
    ("免责", "high", "免责条款范围过宽，建议明确不可抗力、货物自然性质、合理损耗等法定免责边界。"),
    ("不可抗力", "low", "不可抗力定义应明确，并约定通知与举证责任，避免后续争议。"),
    ("毁损", "medium", "货损责任承担与检验期限应明确，收货人应及时在合理期限内检验并异议。"),
    ("灭失", "medium", "货物灭失赔偿额应约定计算方式，无约定时按交付时到达地市场价格计算。"),
    ("运费", "medium", "运费支付主体、时点与不可抗力灭失后的运费处理应明确（民法典第835条）。"),
    ("留置", "medium", "承运人留置权行使范围应明确，避免与约定冲突。"),
    ("提存", "low", "收货人不明或拒收时提存安排应明确，避免费用与风险归属不清。"),
    ("危险货物", "high", "危险货物托运须符合资质、包装、标志与申报要求，违规夹带/匿报责任重大。"),
    ("危险化学品", "high", "危险化学品运输须具备相应资质与车辆，禁止挂靠经营与超载。"),
    ("超载", "high", "严禁超载与违反装载要求，相关行政处罚及事故责任由承运人承担。"),
    ("超限", "medium", "载物长宽高应符合装载要求，违规将受公安交管部门处罚。"),
    ("押运", "medium", "危险货物运输应配备押运人员并悬挂警示标志，确保全程监管。"),
    ("承运人责任险", "medium", "客运与危险货物运输应依法投保承运人责任险，降低事故赔付风险。"),
    ("时效", "medium", "诉讼时效与索赔期限应明确，避免因逾期查询或未主张而失权。"),
    ("管辖", "medium", "争议管辖法院/仲裁机构应明确，涉海案件注意海事法院专属管辖。"),
    ("多式联运", "medium", "多式联运经营人责任、区段责任划分与单据签发应明确（民法典第838-842条）。"),
    ("留置权", "low", "承运人留置权与托运人费用支付义务应平衡，避免滥用。"),
    ("验视", "medium", "寄递快件应履行验视义务，寄件人拒绝验视的不得收寄。"),
    ("个人信息", "medium", "寄递业务涉及用户个人信息，应约定收集、使用与保护义务。"),
]

_SENTENCE_SPLIT = re.compile(r"[。；;\n]")

_LLM_REVIEW_PROMPT = """你是资深物流交通运输法律顾问。以下是运输合同/运单文本与规则引擎初筛的风险点，
请补充遗漏的实质性法律风险（若有），并对每条输出：条款片段/风险等级(high|medium|low)/
建议。仅输出结果，不要寒暄。合同文本：
"""


def _split_clauses(text: str) -> List[str]:
    """按句号/分号/换行切分条款片段。"""
    parts = [p.strip() for p in _SENTENCE_SPLIT.split(text) if p.strip()]
    return parts or [text]


def _rule_based_review(text: str) -> List[Dict[str, Any]]:
    clauses = _split_clauses(text)
    items: List[Dict[str, Any]] = []
    seen = set()
    for clause in clauses:
        for keyword, level, suggestion in _RISK_RULES:
            key = (keyword, clause[:40])
            if keyword in clause and key not in seen:
                seen.add(key)
                items.append(
                    {
                        "clause": clause[:300],
                        "risk_level": level,
                        "suggestion": suggestion,
                        "highlight": clause[:120],
                    }
                )
    return items


async def review_contract(
    text: str, llm: Optional[Any] = None
) -> List[Dict[str, Any]]:
    """物流运输合同/运单审查：规则扫描（必做）+ LLM 增强（可选，失败降级）。"""
    if not text or not text.strip():
        return []

    items = _rule_based_review(text)

    if llm is not None:
        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            raw = await llm.ainvoke(
                [
                    SystemMessage(content=_LLM_REVIEW_PROMPT),
                    HumanMessage(content=text[:6000]),
                ]
            )
            if raw and items:
                items[0]["suggestion"] = (
                    items[0].get("suggestion", "") + f"\n\n（AI 补充意见）{raw[:800]}"
                )
        except Exception:
            pass

    return items
