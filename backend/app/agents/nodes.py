"""LangGraph 六个 Agent 节点（途律 · TruLex）：

supervisor（意图路由）、waybill_reviewer（运单/运输合同审查）、
statute_retrieval（法规检索）、case_retrieval（判例检索）、
liability_assessor（货损责任认定）、document_writer（物流文书生成）、
compliance_guard（合规兜底）。

节点签名为 ``(state, *, llm, tools)``，由 ``build_agent`` 通过 ``functools.partial``
绑定 ``llm`` / ``tools`` 后注入。
"""

import re
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.state import AgentState
from app.agents.streaming import emit_token

# --------------------------------------------------------------------------- #
# 提示词
# --------------------------------------------------------------------------- #
_ROUTING_PROMPT = """你是途律 · TruLex的意图路由主控（supervisor）。
根据用户输入，输出且只输出以下单个分类词之一：
- waybill：用户要审查/分析运输合同、运单、物流合同、快递面单等
- statute：用户要检索物流交通运输法律法规条文（如道路运输条例、快递条例、海商法、铁路法、民航法等）
- case：用户要检索物流交通纠纷判例/案例/裁判文书
- liability：用户要认定货损货差责任归属、承运人是否担责、赔偿计算等
- document：用户要起草/生成物流法律文书（起诉状、运输合同、律师函、货损索赔函等）
- chat：一般性物流法律咨询或闲聊

用户输入如下："""

_DOCUMENT_PROMPT = """你是一名资深物流交通运输法律文书起草助手。请根据用户的要求，草拟一份结构完整、
语言严谨的中国物流交通法律文书（如货物运输合同、货损索赔函、律师函、起诉状等）。
若信息不足可合理假设并说明。输出正式文书正文。"""

_LIABILITY_PROMPT = """你是物流交通运输法律专家。请基于以下纠纷事实与检索到的法规/判例，
分析货物毁损、灭失、短少、延误的责任归属：承运人是否担责、有无免责事由、赔偿额如何计算。
请援引具体法条（如民法典第832条、第833条等），条理清晰、结论明确。"""

_STATUTE_SUMMARY_PROMPT = """你是物流交通运输法规检索助手。请基于以下检索到的法规条文，
用简体中文清晰、准确地回答用户的问题。要求：
1. 优先直接引述相关法条原文并标注法条名称与条号；
2. 对法条做必要的适用解读，说明其针对什么情形；
3. 若检索结果不足以回答，请如实说明并给出进一步查询建议，切勿编造法条。"""

_CASE_SUMMARY_PROMPT = """你是物流交通运输判例分析师。请基于以下检索到的判例，
用简体中文归纳回答用户的问题。要求：
1. 概括判例的案情、争议焦点与裁判规则；
2. 提炼类案可参考的裁判思路；
3. 说明判例对当前问题的参考意义，并提示个案差异。"""

_FALLBACK_PROMPT = """你是「途律 · TruLex」的专业咨询助手。请用简体中文、
专业且准确地回答用户关于物流、运输、快递、仓储、多式联运、危险货物运输等领域的法律问题。
若涉及具体法条或判例，请说明依据；若不确定，如实告知，切勿编造。"""

# --------------------------------------------------------------------------- #
# 工具函数
# --------------------------------------------------------------------------- #
# 敏感信息脱敏正则
_PATTERNS = [
    (re.compile(r"\b1[3-9]\d{9}\b"), "手机号"),
    (re.compile(r"\b\d{17}[\dXx]\b"), "身份证号"),
    (re.compile(r"\b[1-9]\d{15,18}\b"), "银行卡号"),
    (re.compile(r"\b[\w.-]+@[\w.-]+\.\w+\b"), "邮箱"),
]


def _desensitize(text: str) -> str:
    """对常见 PII（手机号/身份证/银行卡/邮箱）打码脱敏。"""
    for pattern, label in _PATTERNS:
        text = pattern.sub(f"[已脱敏{label}]", text)
    return text


def _last_user_text(state: AgentState) -> str:
    messages = state.get("messages") or []
    for msg in reversed(messages):
        if getattr(msg, "type", "") == "human":
            return getattr(msg, "content", "") or ""
        role = getattr(msg, "type", None) or getattr(msg, "role", None)
        if role in ("human", "user"):
            return getattr(msg, "content", "") or ""
    return ""


def _normalize_route(raw: str, fallback_text: str = "") -> str:
    """把 LLM / 关键词结果规整为标准路由名。"""
    raw = (raw or "").strip().lower()
    mapping = {
        "waybill": "waybill",
        "运单": "waybill",
        "运输合同": "waybill",
        "合同": "waybill",
        "面单": "waybill",
        "审查": "waybill",
        "statute": "statute",
        "法条": "statute",
        "法规": "statute",
        "条文": "statute",
        "条例": "statute",
        "case": "case",
        "判例": "case",
        "案例": "case",
        "裁判": "case",
        "liability": "liability",
        "责任": "liability",
        "担责": "liability",
        "赔偿": "liability",
        "货损": "liability",
        "货差": "liability",
        "谁承担": "liability",
        "document": "document",
        "文书": "document",
        "起草": "document",
        "生成": "document",
        "起诉状": "document",
        "律师函": "document",
        "索赔函": "document",
        "chat": "chat",
    }
    for key, value in mapping.items():
        if key in raw:
            return value
    # 兜底：根据用户原文本做关键词判断
    text = (fallback_text or "").lower()
    for key in ("运单", "运输合同", "面单", "审查合同", "审查运单"):
        if key in text:
            return "waybill"
    for key in ("法条", "法规", "条文", "条例", "依据哪条", "什么规定"):
        if key in text:
            return "statute"
    for key in ("判例", "案例", "裁判文书", "类案"):
        if key in text:
            return "case"
    # 文书生成意图优先（「起草/生成/索赔函」等动词意图明确，应先于 liability 的「货损/赔偿」命中）
    for key in ("起草", "生成", "起诉状", "律师函", "索赔函", "合同范本", "写一份", "帮我写"):
        if key in text:
            return "document"
    for key in ("责任", "担责", "赔偿", "货损", "货差", "谁承担", "免责", "灭失"):
        if key in text:
            return "liability"
    return "chat"


def _format_citations(citations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "source": c.get("source", ""),
            "title": c.get("title", ""),
            "snippet": (c.get("text") or "")[:300],
        }
        for c in citations
    ]


# --------------------------------------------------------------------------- #
# 节点
# --------------------------------------------------------------------------- #
async def supervisor(state: AgentState, *, llm, tools=None) -> Dict[str, Any]:
    """意图路由主控：非流式调用 LLM 判断去向。"""
    user_text = _last_user_text(state)
    route = "chat"
    try:
        raw = await llm.ainvoke(
            [
                SystemMessage(content=_ROUTING_PROMPT),
                HumanMessage(content=user_text[:1500]),
            ]
        )
        route = _normalize_route(raw, user_text)
    except Exception:
        route = _normalize_route("", user_text)
    return {"route": route}


async def waybill_reviewer(state: AgentState, *, llm, tools=None) -> Dict[str, Any]:
    """运单/运输合同审查：解析文本并输出风险点 + 条款高亮。"""
    from app.services.contract import review_contract

    user_text = _last_user_text(state)
    parse = (tools or {}).get("parse_contract")
    contract_text = user_text
    if parse:
        try:
            contract_text = await parse(text=user_text) or user_text
        except Exception:
            contract_text = user_text

    items: List[Dict[str, Any]] = []
    try:
        items = await review_contract(contract_text, llm)
    except Exception:
        items = []

    highlights = [item.get("highlight", "") for item in items]
    lines = []
    for item in items:
        lines.append(
            f"[{item.get('risk_level', 'medium')}] {item.get('clause', '')}\n"
            f"建议：{item.get('suggestion', '')}"
        )
    final = "运输合同/运单审查发现以下法律风险点：\n" + ("\n\n".join(lines) if lines else "未发现明显风险点。")
    return {
        "route": "waybill",
        "final_answer": final,
        "highlights": highlights,
        "documents": items,
        "citations": [],
    }


async def statute_retrieval(state: AgentState, *, llm, tools=None) -> Dict[str, Any]:
    """法规检索：Milvus 混合检索（BM25 + 稠密向量）后由 LLM 归纳解读。"""
    user_text = _last_user_text(state)
    search = (tools or {}).get("search_statutes")
    results: List[Dict[str, Any]] = []
    if search:
        try:
            results = await search(user_text, top_k=5)
        except Exception:
            results = []
    citations = _format_citations(results)

    # 检索结果作为上下文，交由 LLM 归纳解读（提升回答质量，而非简单罗列原文）
    final = ""
    if results:
        context = "\n".join(
            f"{r.get('title', '')}：{r.get('text', '')}" for r in results
        )
        try:
            parts: List[str] = []
            async for token in llm.astream(
                [
                    SystemMessage(content=_STATUTE_SUMMARY_PROMPT),
                    HumanMessage(content=f"用户问题：{user_text}\n\n检索到的法规条文：\n{context[:5000]}"),
                ]
            ):
                parts.append(token)
                emit_token(token)
            final = "".join(parts)
        except Exception:
            final = ""
    if not final:
        final = "为您检索到相关物流交通法规条文：\n" + (
            "\n".join(f"{i + 1}. {r.get('title', '')}：{r.get('text', '')}"
                      for i, r in enumerate(results))
            if results else "暂未检索到相关法规，请补充关键词。"
        )
    return {
        "route": "statute",
        "final_answer": final,
        "documents": results,
        "citations": citations,
    }


async def case_retrieval(state: AgentState, *, llm, tools=None) -> Dict[str, Any]:
    """判例检索：Milvus 混合检索 + Neo4j 关系图后由 LLM 归纳判例裁判规则。"""
    user_text = _last_user_text(state)
    search = (tools or {}).get("search_cases")
    results: List[Dict[str, Any]] = []
    if search:
        try:
            results = await search(user_text, top_k=5)
        except Exception:
            results = []
    citations = _format_citations(results)

    final = ""
    if results:
        context = "\n".join(
            f"{r.get('title', '')}：{r.get('text', '')}" for r in results
        )
        try:
            parts: List[str] = []
            async for token in llm.astream(
                [
                    SystemMessage(content=_CASE_SUMMARY_PROMPT),
                    HumanMessage(content=f"用户问题：{user_text}\n\n检索到的判例：\n{context[:5000]}"),
                ]
            ):
                parts.append(token)
                emit_token(token)
            final = "".join(parts)
        except Exception:
            final = ""
    if not final:
        final = "为您检索到相关物流交通纠纷判例：\n" + (
            "\n".join(f"{i + 1}. {r.get('title', '')}：{r.get('text', '')}"
                      for i, r in enumerate(results))
            if results else "暂未检索到相关判例，请补充关键词。"
        )
    return {
        "route": "case",
        "final_answer": final,
        "documents": results,
        "citations": citations,
    }


async def liability_assessor(state: AgentState, *, llm, tools=None) -> Dict[str, Any]:
    """货损责任认定：检索法规/判例后由 LLM 综合分析责任归属与赔偿计算。"""
    user_text = _last_user_text(state)
    search_statutes = (tools or {}).get("search_statutes")
    search_cases = (tools or {}).get("search_cases")
    statutes: List[Dict[str, Any]] = []
    cases: List[Dict[str, Any]] = []
    if search_statutes:
        try:
            statutes = await search_statutes(user_text, top_k=3)
        except Exception:
            statutes = []
    if search_cases:
        try:
            cases = await search_cases(user_text, top_k=3)
        except Exception:
            cases = []

    citations = _format_citations(statutes + cases)
    context = "\n".join(
        [f"法条：{r.get('title', '')} {r.get('text', '')}" for r in statutes]
        + [f"判例：{r.get('title', '')} {r.get('text', '')}" for r in cases]
    ) or "（未检索到相关依据，请基于通用运输合同法理分析）"

    answer = "货损责任认定分析失败，请稍后重试。"
    try:
        parts: List[str] = []
        async for token in llm.astream(
            [
                SystemMessage(content=_LIABILITY_PROMPT),
                HumanMessage(content=f"纠纷事实：{user_text}\n\n参考依据：\n{context[:6000]}"),
            ]
        ):
            parts.append(token)
            emit_token(token)
        answer = "".join(parts) or answer
    except Exception:
        pass

    return {
        "route": "liability",
        "final_answer": answer,
        "documents": statutes + cases,
        "citations": citations,
    }


async def document_writer(state: AgentState, *, llm, tools=None) -> Dict[str, Any]:
    """物流文书生成：检索相关法规后由 LLM 起草法律文书，附法条依据。"""
    user_text = _last_user_text(state)
    # 检索相关法规作为文书起草依据
    search = (tools or {}).get("search_statutes")
    statutes: List[Dict[str, Any]] = []
    if search:
        try:
            statutes = await search(user_text, top_k=3)
        except Exception:
            statutes = []
    citations = _format_citations(statutes)
    context = "\n".join(
        f"{r.get('title', '')}：{r.get('text', '')}" for r in statutes
    ) or "（未检索到相关法条，请基于通用合同法与运输合同法理起草）"

    draft = ""
    try:
        parts: List[str] = []
        async for token in llm.astream(
            [
                SystemMessage(content=_DOCUMENT_PROMPT),
                HumanMessage(content=f"{user_text}\n\n可引用的法条依据：\n{context[:4000]}"),
            ]
        ):
            parts.append(token)
            emit_token(token)
        draft = "".join(parts)
    except Exception:
        draft = "文书生成失败，请稍后重试。"
    return {
        "route": "document",
        "final_answer": draft,
        "documents": statutes,
        "citations": citations,
    }


async def compliance_guard(state: AgentState, *, llm, tools=None) -> Dict[str, Any]:
    """合规兜底：兜底生成回答 + 敏感信息脱敏 + 合规检查。"""
    answer = state.get("final_answer") or ""
    if not answer:
        # chat 路由兜底：流式生成回答
        user_text = _last_user_text(state)
        chunks: List[str] = []
        try:
            async for token in llm.astream(
                [
                    SystemMessage(content=_FALLBACK_PROMPT),
                    HumanMessage(content=user_text),
                ]
            ):
                chunks.append(token)
                emit_token(token)
        except Exception:
            chunks = ["抱歉，服务暂时不可用，请稍后重试。"]
        answer = "".join(chunks)

    cleaned = _desensitize(answer)
    disclaimer = "（以上内容由 AI 生成，仅供参考，不构成正式法律意见，具体请以现行法律法规及司法实践为准。）"
    if "法律意见" not in cleaned:
        cleaned = cleaned.rstrip() + "\n\n" + disclaimer

    return {
        "final_answer": cleaned,
        "compliance_ok": True,
        "route": state.get("route", "chat"),
    }


NODES: Dict[str, Any] = {
    "supervisor": supervisor,
    "waybill_reviewer": waybill_reviewer,
    "statute_retrieval": statute_retrieval,
    "case_retrieval": case_retrieval,
    "liability_assessor": liability_assessor,
    "document_writer": document_writer,
    "compliance_guard": compliance_guard,
}
