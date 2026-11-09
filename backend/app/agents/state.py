"""LangGraph 多 Agent 共享状态。

使用 ``Annotated[list, add_messages]`` 累加消息，其余字段为「最后写入生效」。
"""

from typing import Annotated, Any, List, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """多 Agent 编排的全局状态。"""

    # 对话消息（自动追加合并）
    messages: Annotated[List[Any], add_messages]
    # supervisor 路由结果：waybill / statute / case / liability / document / chat
    route: str
    # 检索到的原始材料（法条/判例/知识库片段）
    documents: List[Any]
    # 运单/运输合同审查需要前端高亮的条款片段
    highlights: List[str]
    # 最终回答引用的来源（法条/判例/知识库）
    citations: List[dict]
    # 合规兜底检测结果：是否通过
    compliance_ok: bool
    # 最终回答文本
    final_answer: str