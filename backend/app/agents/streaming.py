"""流式 token 管道：让 LangGraph 节点内的 LLM 生成逐 token 回传。

通过 contextvars 在单次请求内共享一个 ``asyncio.Queue``，节点生成时把
每个 token 推入队列，`stream_chat` 消费队列实时 yield 给 SSE。
"""

import asyncio
from contextvars import ContextVar
from typing import Optional

# 当前请求的 token 队列（asyncio.Queue[str]），无则说明非流式调用
_stream_queue: ContextVar[Optional["asyncio.Queue[str]"]] = ContextVar(
    "stream_token_queue", default=None
)


def start_streaming() -> "asyncio.Queue[str]":
    """开启一个流式会话，返回用于接收 token 的队列。"""
    queue: "asyncio.Queue[str]" = asyncio.Queue()
    _stream_queue.set(queue)
    return queue


def stop_streaming() -> None:
    """结束流式会话，清空 contextvar。"""
    _stream_queue.set(None)


def emit_token(token: str) -> None:
    """节点内调用：把一段 token 推入当前请求的队列（非阻塞）。"""
    queue = _stream_queue.get()
    if queue is not None and token:
        queue.put_nowait(token)


def is_streaming() -> bool:
    return _stream_queue.get() is not None
