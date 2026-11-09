"""聊天接口：SSE 流式问答 + 历史记录。"""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_optional, get_db
from app.db.session import async_session_factory
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.schemas.chat import ChatHistoryResponse, ChatRequest, MessageOut
from app.services.audit import record_audit
from app.services.chat import stream_chat

router = APIRouter(prefix="/chat", tags=["chat"])

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _sse(event_type: str, data) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _persist_messages(
    conversation_id: str, user_message: str, assistant_answer: str, user_id: Optional[int]
) -> None:
    """落库用户/助手消息与会话（失败不影响主流程）。"""
    try:
        async with async_session_factory() as db:
            conv = (
                await db.execute(
                    select(Conversation).where(Conversation.thread_id == conversation_id)
                )
            ).scalar_one_or_none()
            if conv is None:
                conv = Conversation(
                    thread_id=conversation_id,
                    user_id=user_id,
                    title=user_message[:50],
                )
                db.add(conv)
                await db.flush()
            db.add(
                Message(conversation_id=conv.id, role="user", content=user_message)
            )
            db.add(
                Message(
                    conversation_id=conv.id,
                    role="assistant",
                    content=assistant_answer,
                )
            )
            await db.commit()
    except Exception:
        pass


@router.post("")
async def chat(
    body: ChatRequest,
    request: Request,
    user: Optional[User] = Depends(get_current_user_optional),
) -> StreamingResponse:
    """SSE 流式对话，逐 token 回传，最后回传引用 citations。"""
    agent = request.app.state.agent

    async def event_generator():
        collected: list = []
        conversation_id = body.conversation_id
        async for event in stream_chat(body.conversation_id, body.message, agent):
            etype = event.get("type")
            if etype == "token":
                collected.append(event.get("content", ""))
                yield _sse("token", {"content": event.get("content", "")})
            elif etype == "citations":
                yield _sse("citations", event.get("data", {}))
            elif etype == "done":
                data = event.get("data", {})
                conversation_id = data.get("conversation_id", conversation_id)
                yield _sse("done", data)
            elif etype == "error":
                yield _sse("error", event.get("data", {}))

        # 持久化用户/助手消息
        await _persist_messages(
            conversation_id or body.conversation_id or "",
            body.message,
            "".join(collected),
            user.id if user else None,
        )
        # 审计
        try:
            async with async_session_factory() as db:
                await record_audit(
                    db,
                    action="chat.send",
                    user_id=user.id if user else None,
                    resource_type="chat",
                    resource_id=conversation_id,
                    ip_address=request.client.host if request.client else None,
                )
        except Exception:
            pass

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.get("/history", response_model=ChatHistoryResponse)
async def history(
    conversation_id: str = Query(..., description="会话 ID"),
    user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> ChatHistoryResponse:
    """按 conversation_id 拉取历史消息。"""
    conv = (
        await db.execute(select(Conversation).where(Conversation.thread_id == conversation_id))
    ).scalar_one_or_none()
    if conv is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    rows = (
        await db.execute(
            select(Message)
            .where(Message.conversation_id == conv.id)
            .order_by(Message.created_at.asc())
        )
    ).scalars().all()

    messages = [
        MessageOut(
            id=m.id,
            role=m.role,
            content=m.content,
            citations=m.citations,
            created_at=m.created_at,
        )
        for m in rows
    ]
    return ChatHistoryResponse(conversation_id=conversation_id, messages=messages)