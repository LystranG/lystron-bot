"""合并转发（forward）相关处理。

核心策略：
- 收到消息时立即展开并缓存 forward 内容
- 撤回时直接使用缓存，避免后端因“消息过期/内层消息”导致 get_forward_msg 失败
"""

from __future__ import annotations

from typing import Any

from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.message import Message

from .segments import (
    ForwardNode,
    ReplyLookupResult,
    extract_forward_ids,
    extract_sender_user_id,
    make_forward_node,
    normalize_content_to_segments,
    expand_reply_segments,
)
from . import cache
from .utils import safe_int


def _placeholder_over_depth() -> list[dict[str, Any]]:
    return [{"type": "text", "data": {"text": "已超出嵌套上限"}}]


def _get_forward_id_from_segment(seg: dict[str, Any]) -> str | None:
    data = seg.get("data") if isinstance(seg.get("data"), dict) else {}
    fid = data.get("id") or data.get("forward_id") or data.get("res_id") or data.get("file")
    return str(fid) if fid else None


async def _build_nodes_from_forward_id(
    bot: Bot,
    forward_id: str,
    *,
    max_depth: int,
    depth: int,
    fallback_user_id: int,
    seen: set[str],
) -> list[ForwardNode] | None:
    """将一个 forward_id 展开为可发送的 ForwardNode 列表（支持递归嵌套）。

    说明：
    - NapCat/QQ 客户端在“合并转发的 node.content 里再塞 forward 段”时，常出现“查看0条转发消息”。
    - 因此这里直接把嵌套转发展开为同一个合并转发里的多个 node，从而保证可显示。
    """

    # 1) 优先复用插件本地缓存（避免 NapCat 对“内层消息” get_forward_msg 直接报错）
    cached = cache.get_forward(forward_id)
    if cached is not None:
        return cached

    if depth > max_depth:
        return [
            make_forward_node(
                user_id=fallback_user_id,
                nickname="防撤回",
                content=_placeholder_over_depth(),
            )
        ]

    if forward_id in seen:
        return [
            make_forward_node(
                user_id=fallback_user_id,
                nickname="防撤回",
                content=[{"type": "text", "data": {"text": "无法获取"}}],
            )
        ]
    seen.add(forward_id)

    try:
        forward_data = await bot.get_forward_msg(id=str(forward_id), _timeout=10)
    except Exception:
        return None

    if not isinstance(forward_data, dict):
        return None

    raw_items = list(forward_data.get("messages", []))
    local_index: dict[int, tuple[str, int, list[dict[str, Any]], int]] = {}
    pos_index: dict[int, tuple[str, int, list[dict[str, Any]]]] = {}
    normalized_items: list[tuple[int, str, int, list[dict[str, Any]], list[ForwardNode]]] = []

    pos = 0
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        pos += 1

        sender = item.get("sender", {}) if isinstance(item.get("sender"), dict) else {}
        nickname = str(sender.get("card") or sender.get("nickname") or item.get("nickname") or "未知")
        nickname = "".join(nickname.split()) or "未知"

        original_user_id = extract_sender_user_id(sender) or safe_int(
            item.get("user_id") or item.get("uin") or item.get("sender_id") or 0
        )

        content: Any = item.get("content")
        if content is None and "message" in item:
            content = item.get("message")

        content_segments = normalize_content_to_segments(content)
        content_segments, nested_nodes = await _inline_nested_forward_as_nodes(
            bot,
            content_segments,
            depth=depth,
            max_depth=max_depth,
            fallback_user_id=fallback_user_id,
            seen=seen,
        )

        normalized_items.append((pos, nickname, original_user_id, content_segments, nested_nodes))
        pos_index[pos] = (nickname, original_user_id, content_segments)

        msg_id = safe_int(item.get("message_id") or item.get("id") or item.get("real_id") or 0)
        if msg_id:
            local_index[msg_id] = (nickname, original_user_id, content_segments, pos)

    nodes: list[ForwardNode] = []
    for cur_pos, nickname, original_user_id, content_segments, nested_nodes in normalized_items:

        def _local_lookup(message_id: int) -> ReplyLookupResult | None:
            found = local_index.get(message_id)
            if found is None:
                prev = pos_index.get(cur_pos - 1)
                if prev is None:
                    return None
                pn, puid, pseg = prev
                return ReplyLookupResult(
                    sender_name=pn,
                    sender_user_id=puid,
                    quoted_segments=pseg,
                    offset_up=1,
                )
            fnick, fuid, fseg, fpos = found
            offset = cur_pos - fpos
            return ReplyLookupResult(
                sender_name=fnick,
                sender_user_id=fuid,
                quoted_segments=fseg,
                offset_up=offset if offset > 0 else None,
            )

        content_segments = await expand_reply_segments(
            bot, content_segments, local_reply_lookup=_local_lookup
        )

        nodes.append(
            make_forward_node(
                user_id=original_user_id or fallback_user_id,
                nickname=nickname,
                content=content_segments,
            )
        )
        if nested_nodes:
            nodes.extend(nested_nodes)

    return nodes


async def _inline_nested_forward_as_nodes(
    bot: Bot,
    segments: list[dict[str, Any]],
    *,
    depth: int,
    max_depth: int,
    fallback_user_id: int,
    seen: set[str],
) -> tuple[list[dict[str, Any]], list[ForwardNode]]:
    """将 segments 中的嵌套 forward 展开为“额外的 node”。

    返回： (替换后的 segments, 需要追加到外层 forward 的 nodes)
    """

    out: list[dict[str, Any]] = []
    extra_nodes: list[ForwardNode] = []
    for seg in segments:
        if not (isinstance(seg, dict) and seg.get("type") == "forward"):
            out.append(seg)
            continue

        fid = _get_forward_id_from_segment(seg)
        if not fid:
            out.append({"type": "text", "data": {"text": "无法获取"}})
            continue

        # forward 段本身代表“下一层嵌套”
        if depth + 1 > max_depth:
            out.extend(_placeholder_over_depth())
            continue

        nested = await _build_nodes_from_forward_id(
            bot,
            fid,
            max_depth=max_depth,
            depth=depth + 1,
            fallback_user_id=fallback_user_id,
            seen=seen,
        )
        if not nested:
            # 兜底：如果后端无法通过 get_forward_msg 展开该嵌套转发，
            # 则保留原始 forward 段，让客户端尽可能展示（哪怕只能看到预览/查看0条）。
            out.append(seg)
            continue

        # 当前 node 内用最短占位提示“这里有嵌套转发”，真正内容由额外 node 展示
        out.append({"type": "text", "data": {"text": "（聊天记录）"}})
        extra_nodes.extend(nested)

    return out, extra_nodes

async def build_forward_nodes(
    bot: Bot,
    *,
    sender_name: str,
    event_user_id: int,
    message: Message,
    max_depth: int,
) -> list[ForwardNode] | None:
    """如果 message 包含 forward 段，则展开并返回 node 列表；否则返回 None。"""

    forward_ids = extract_forward_ids(message)
    if not forward_ids:
        return None

    nodes: list[ForwardNode] = []
    for forward_id in forward_ids:
        nested = await _build_nodes_from_forward_id(
            bot,
            forward_id,
            max_depth=max_depth,
            depth=1,
            fallback_user_id=event_user_id,
            seen=set(),
        )
        if not nested:
            nodes.append(make_forward_node(user_id=event_user_id, nickname=sender_name, content="无法获取"))
            continue
        # 外层转发成功展开后，缓存 forward_id -> nodes，供后续嵌套复用
        cache.put_forward(forward_id, nested)
        nodes.extend(nested)

    return nodes
