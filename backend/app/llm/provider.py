"""LLMProvider：统一 LLM 访问抽象层。

业务代码一律通过本类访问大模型，不直接实例化 ``ChatOpenAI``。
底层使用 ``langchain_openai.ChatOpenAI``，通过 OpenAI 兼容协议接入
DashScope / DeepSeek / 自训 vLLM，仅需调整 ``API_KEY`` / ``BASE_URL`` / ``MODEL_NAME``。
"""

from typing import Any, AsyncIterator, Iterator, List, Optional, Union

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings

MessageLike = Union[str, BaseMessage, dict]


class LLMProvider:
    """大模型提供方抽象，封装流式 / 非流式、超时与重试、可切换模型。"""

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.2,
        timeout: float = 60.0,
        max_retries: int = 3,
    ) -> None:
        self.model_name = model_name or settings.MODEL_NAME
        self.api_key = api_key or settings.API_KEY
        self.base_url = base_url or settings.BASE_URL
        self.temperature = temperature
        self.timeout = timeout
        self.max_retries = max_retries
        self._clients: dict = {}

    # ------------------------------------------------------------------ #
    # 模型实例管理（可切换模型 / base_url，如 vLLM 自训模型）
    # ------------------------------------------------------------------ #
    def get_model(self, model_name: Optional[str] = None) -> ChatOpenAI:
        name = model_name or self.model_name
        if name not in self._clients:
            self._clients[name] = ChatOpenAI(
                model=name,
                api_key=self.api_key,
                base_url=self.base_url,
                temperature=self.temperature,
                timeout=self.timeout,
                max_retries=self.max_retries,
                streaming=True,  # 开启真流式，astream 逐 token 产出，前端实时回显
            )
        return self._clients[name]

    @staticmethod
    def to_messages(messages: Any) -> List[BaseMessage]:
        """将多种输入形态规整为 LangChain 消息列表。"""
        if isinstance(messages, BaseMessage):
            return [messages]
        if isinstance(messages, str):
            return [HumanMessage(content=messages)]
        if isinstance(messages, dict):
            messages = [messages]
        result: List[BaseMessage] = []
        for m in messages:
            if isinstance(m, BaseMessage):
                result.append(m)
                continue
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                result.append(SystemMessage(content=content))
            else:
                result.append(HumanMessage(content=content))
        return result

    @staticmethod
    def _extract(response: Any) -> str:
        """从 LangChain 返回对象中提取纯文本。"""
        if response is None:
            return ""
        if isinstance(response, str):
            return response
        content = getattr(response, "content", response)
        if isinstance(content, list):
            parts = []
            for c in content:
                if isinstance(c, str):
                    parts.append(c)
                elif isinstance(c, dict):
                    parts.append(c.get("text", ""))
            return "".join(parts)
        return str(content)

    # ------------------------------------------------------------------ #
    # 非流式（带 tenacity 重试）
    # ------------------------------------------------------------------ #
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def invoke(self, messages: Any, model_name: Optional[str] = None) -> str:
        model = self.get_model(model_name)
        return self._extract(model.invoke(self.to_messages(messages)))

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def ainvoke(self, messages: Any, model_name: Optional[str] = None) -> str:
        model = self.get_model(model_name)
        return self._extract(await model.ainvoke(self.to_messages(messages)))

    # ------------------------------------------------------------------ #
    # 流式
    # ------------------------------------------------------------------ #
    def stream(self, messages: Any, model_name: Optional[str] = None) -> Iterator[str]:
        model = self.get_model(model_name)
        for chunk in model.stream(self.to_messages(messages)):
            content = getattr(chunk, "content", "")
            if content:
                yield content

    async def astream(
        self, messages: Any, model_name: Optional[str] = None
    ) -> AsyncIterator[str]:
        model = self.get_model(model_name)
        async for chunk in model.astream(self.to_messages(messages)):
            content = getattr(chunk, "content", "")
            if content:
                yield content