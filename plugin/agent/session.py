"""Agent 会话管理（自控会话，不依赖 reject）。

设计目标：
- “只能通过 /a 开启会话”：不开启时，普通私聊消息不会进入 agent 会话逻辑
- 会话内存储：
  - n8n 会话唯一 id（用于 n8n 侧做会话关联/存档）
  - 聊天记录（用 UniMessage 存储，便于后续做结构化解析与上下文回放）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from plugin.agent.message_extract import ChatMessage

@dataclass(slots=True)
class AgentSession:
    """Agent 会话状态。"""

    # 用于 n8n 保存会话/串联上下文的唯一 id
    n8n_session_id: str = field(default_factory=lambda: uuid4().hex)

    # LangGraph thread_id（通常直接复用 n8n_session_id）
    thread_id: str = field(init=False)

    turns: list[ChatMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        self.thread_id = self.n8n_session_id

    def add(self, msg: ChatMessage):
        self.turns.append(msg)


class SessionStore:
    """进程内会话存储（按 session_key 维护）。"""

    def __init__(self) -> None:
        self._sessions: dict[str, AgentSession] = {}

    def has(self, session_key: str) -> bool:
        return session_key in self._sessions

    def get(self, session_key: str) -> AgentSession | None:
        return self._sessions.get(session_key)

    def create(self, session_key: str) -> AgentSession:
        sess = AgentSession()
        self._sessions[session_key] = sess
        return sess

    def pop(self, session_key: str) -> AgentSession | None:
        return self._sessions.pop(session_key, None)


__all__ = ["AgentSession", "SessionStore"]

