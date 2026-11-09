"""Agent 节点单元测试（FakeLLM / Fake tools，不依赖外部服务）。"""
import asyncio

from langchain_core.messages import HumanMessage

from app.agents import nodes


class FakeLLM:
    """可配置返回内容的假 LLM。"""

    def __init__(self, content="分析结果"):
        self._content = content

    async def ainvoke(self, messages):
        return type("Resp", (), {"content": self._content})()

    async def astream(self, messages):
        yield self._content


async def _state(text):
    return {"messages": [HumanMessage(content=text)]}


def test_liability_assessor_calls_llm():
    """货损责任认定节点应检索并交由 LLM 分析。"""
    statutes = [{"title": "《民法典》第832条", "text": "承运人对毁损灭失承担赔偿责任。",
                 "source": "statute", "meta": {}}]
    cases = [{"title": "某物流货损案", "text": "判决承运人赔偿。", "source": "case", "meta": {}}]

    async def run():
        tools = {
            "search_statutes": async_func(statutes),
            "search_cases": async_func(cases),
        }
        state = await _state("货物运输途中毁损，承运人承担什么责任？")
        result = await nodes.liability_assessor(state, llm=FakeLLM("承运人应承担赔偿责任。"), tools=tools)
        assert result["route"] == "liability"
        assert result["final_answer"] == "承运人应承担赔偿责任。"
        assert len(result["citations"]) == 2
    asyncio.run(run())


def test_statute_retrieval_falls_back_when_no_llm():
    """法规检索在 LLM 失败时应回退到罗列原文。"""
    statutes = [{"title": "《民法典》第832条", "text": "承运人对毁损灭失承担赔偿责任。",
                 "source": "statute", "meta": {}}]

    class FailingLLM:
        async def ainvoke(self, messages):
            raise RuntimeError("boom")

    async def run():
        tools = {"search_statutes": async_func(statutes)}
        state = await _state("检索承运人责任")
        result = await nodes.statute_retrieval(state, llm=FailingLLM(), tools=tools)
        assert result["route"] == "statute"
        assert "承运人对毁损灭失承担赔偿责任" in result["final_answer"]
    asyncio.run(run())


def test_document_writer_uses_statutes():
    """文书生成节点应检索法条作为依据。"""
    statutes = [{"title": "《民法典》第832条", "text": "承运人对毁损灭失承担赔偿责任。",
                 "source": "statute", "meta": {}}]

    async def run():
        tools = {"search_statutes": async_func(statutes)}
        state = await _state("起草一份货损索赔函")
        result = await nodes.document_writer(state, llm=FakeLLM("货损索赔函正文"), tools=tools)
        assert result["route"] == "document"
        assert result["final_answer"] == "货损索赔函正文"
        assert len(result["citations"]) == 1
    asyncio.run(run())


def async_func(result):
    """把普通返回值包装成 async 可调用。"""
    async def _f(*args, **kwargs):
        return result
    return _f
