"""Run the graph and publish only the final, compliance-checked answer."""
import asyncio
import uuid
from typing import Any, AsyncIterator, Dict, Optional

from langchain_core.messages import HumanMessage

from app.agents.streaming import start_streaming, stop_streaming


async def stream_chat(
    conversation_id: Optional[str], message: str, agent: Any,
) -> AsyncIterator[Dict[str, Any]]:
    thread_id = conversation_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    # Reset per-turn output while preserving the conversation's message history.
    inputs = {
        "messages": [HumanMessage(content=message)],
        "final_answer": "", "citations": [], "documents": [], "highlights": [],
    }

    # 开启本次请求的流式 token 队列，供节点内 emit_token 使用
    queue = start_streaming()

    values: Dict[str, Any] = {}

    async def _run_graph():
        nonlocal values
        try:
            async for update in agent.astream(inputs, config=config, stream_mode="updates"):
                for state in update.values():
                    if isinstance(state, dict):
                        values.update(state)
        except Exception as exc:
            values["_error"] = f"{str(exc) or type(exc).__name__}"

    try:
        task = asyncio.create_task(_run_graph())
        streamed = False

        # 边跑图边消费 token 队列，逐 token 回传
        while True:
            try:
                token = await asyncio.wait_for(queue.get(), timeout=0.1)
                streamed = True
                yield {"type": "token", "content": token}
            except asyncio.TimeoutError:
                if task.done():
                    # 图已结束，排空队列剩余 token
                    while not queue.empty():
                        t = queue.get_nowait()
                        if t:
                            streamed = True
                            yield {"type": "token", "content": t}
                    break
            except asyncio.CancelledError:
                raise

        await task  # 吸收可能的异常
    finally:
        stop_streaming()

    if values.get("_error"):
        yield {"type": "error", "data": {"message": f"处理失败：{values['_error']}"}}
        return

    # 若节点未通过 emit_token 流式输出（如 waybill 审查），则一次性回传最终答案
    if not streamed:
        answer = values.get("final_answer") or ""
        if answer:
            yield {"type": "token", "content": answer}
    yield {"type": "citations", "data": {"items": values.get("citations") or []}}
    yield {"type": "done", "data": {
        "conversation_id": thread_id,
        "compliance_ok": bool(values.get("compliance_ok", True)),
        "route": values.get("route", "chat"),
    }}
