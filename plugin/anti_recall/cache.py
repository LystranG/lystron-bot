"""消息缓存（FIFO）。

目标：
- 缓存最近 N 条群消息，供撤回时转发
- 缓存合并转发的展开结果（因为撤回后后端往往无法再 get_forward_msg）
- 缓存 reply 展开需要的“引用预览”（避免撤回后再 get_msg 失败）
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any
import copy

from nonebot.adapters.onebot.v11.message import Message


Segment = dict[str, Any]
ForwardNode = dict[str, Any]

# 最大缓存消息数量（超过后按 FIFO 丢弃最早缓存）
MAX_CACHE_SIZE = 100
# 最大 forward_id 缓存数量（用于嵌套转发的复用）
MAX_FORWARD_CACHE_SIZE = 100


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
    # 可选：用于 reply 摘要的原始 segments（例如转发记录内部条目无法构造 Message 时）
    source_segments: list[Segment] | None = None


_message_queue: deque[int] = deque()
_message_cache: dict[int, CachedMessage] = {}
_forward_queue: deque[str] = deque()
_forward_cache: dict[str, list[ForwardNode]] = {}


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


def put_forward(forward_id: str, nodes: list[ForwardNode]) -> None:
    """缓存 forward_id 对应的节点列表（用于嵌套转发复用）。

    说明：
    - NapCat 对“内层消息”的 get_forward_msg 会直接报错，导致嵌套转发无法展开
    - 因此当某个 forward_id 首次作为“外层转发”出现并成功展开时，先缓存起来
    - 后续若它作为嵌套转发出现，则直接复用缓存，避免触发后端限制
    """

    fid = str(forward_id or "").strip()
    if not fid:
        return

    if fid in _forward_cache:
        try:
            _forward_queue.remove(fid)
        except ValueError:
            pass

    if len(_forward_queue) >= MAX_FORWARD_CACHE_SIZE:
        oldest = _forward_queue.popleft()
        _forward_cache.pop(oldest, None)

    _forward_queue.append(fid)
    # 深拷贝，避免外部修改影响缓存
    _forward_cache[fid] = copy.deepcopy(nodes)


def get_forward(forward_id: str) -> list[ForwardNode] | None:
    """读取 forward_id 缓存（返回深拷贝，避免被修改）。"""

    fid = str(forward_id or "").strip()
    if not fid:
        return None
    nodes = _forward_cache.get(fid)
    return copy.deepcopy(nodes) if nodes is not None else None


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
