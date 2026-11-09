"""Regression checks for graph execution and per-turn output isolation."""
import asyncio

from langgraph.checkpoint.memory import InMemorySaver

from app.agents.graph import build_agent
from app.services.chat import stream_chat


class FakeLLM:
    async def ainvoke(self, messages):
        return "chat"

    async def astream(self, messages):
        yield "回答：" + messages[-1].content


def test_chat_without_persistent_memory():
    async def run():
        agent = build_agent(llm=FakeLLM())
        events = [e async for e in stream_chat(None, "问题一", agent)]
        assert events[0]["type"] == "token"
        assert "问题一" in events[0]["content"]
        assert events[-1]["type"] == "done"
    asyncio.run(run())


def test_followup_does_not_reuse_previous_answer():
    async def run():
        agent = build_agent(llm=FakeLLM(), checkpointer=InMemorySaver())
        first = [e async for e in stream_chat("regression", "问题一", agent)]
        second = [e async for e in stream_chat("regression", "问题二", agent)]
        assert "问题一" in first[0]["content"]
        assert "问题二" in second[0]["content"]
        assert "问题一" not in second[0]["content"]
    asyncio.run(run())
