"""消息缓存（FIFO）。

目标：
- 缓存最近 N 条群消息，供撤回时转发
- 缓存 reply 展开需要的“引用预览”（避免撤回后再 get_msg 失败）
- 对“转发消息”额外缓存：归档群中的 message_id（用于 NapCat 的转发接口）
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

from nonebot.adapters.onebot.v11.message import Message


Segment = dict[str, Any]

# 最大缓存消息数量（超过后按 FIFO 丢弃最早缓存）
MAX_CACHE_SIZE = 100


@dataclass(frozen=True, slots=True)
class CachedMessage:
    """缓存条目。"""

    sender_name: str
    message: Message
    group_id: int
    sender_user_id: int
    # 原始消息中包含的 forward_id（外层转发），用于撤回时原样转发以保留 QQ 原生嵌套能力
    forward_ids: list[str] | None
    expanded_segments: list[Segment]
    # 归档群中的消息 ID（用于 NapCat forward_friend_single_msg 转发）
    archived_message_id: int | None = None


_message_queue: deque[int] = deque()
_message_cache: dict[int, CachedMessage] = {}


def put(message_id: int, cached: CachedMessage) -> None:
    """写入缓存，超过上限自动 FIFO 淘汰。"""

    # 重要：同一个 message_id 可能被重复写入（例如事件重放/插件热重载等）。
    # 若不处理，队列里会出现重复 id，导致淘汰时把 dict 的最新值删掉，出现“缓存丢失”。
    if message_id in _message_cache:
        try:
            _message_queue.remove(message_id)
        except ValueError:
            pass

    if len(_message_queue) >= MAX_CACHE_SIZE:
        oldest = _message_queue.popleft()
        _message_cache.pop(oldest, None)

    _message_queue.append(message_id)
    _message_cache[message_id] = cached


def get(message_id: int) -> CachedMessage | None:
    """读取缓存（注意：不会在撤回时删除，淘汰由 FIFO 统一控制）。"""

    return _message_cache.get(message_id)


def offset_up(current_message_id: int, target_message_id: int) -> int | None:
    """计算“往上第 N 条”。

    - current_message_id：当前消息（正在处理的消息）
    - target_message_id：被回复的那条消息

    说明：
    - 若 current_message_id 尚未写入缓存（例如在写入前做 reply 展开），则将 current 视作队尾下一位。
    - 返回 None 表示无法计算或不合理（例如 target 在 current 之后）。
    """

    try:
        target_idx = _message_queue.index(target_message_id)
    except ValueError:
        return None

    try:
        current_idx = _message_queue.index(current_message_id)
    except ValueError:
        current_idx = len(_message_queue)

    offset = current_idx - target_idx
    return offset if offset > 0 else None

def remove(message_id: int) -> None:
    """从缓存中移除指定消息 ID 的缓存条目。"""

    try:
        _message_queue.remove(message_id)
    except ValueError:
        pass
    _message_cache.pop(message_id, None)
