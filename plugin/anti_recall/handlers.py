"""事件监听与业务编排。

把“监听/编排”与“纯函数工具”分离，便于维护与单测。
"""

from __future__ import annotations

from typing import Any

from nonebot import on_message, on_notice
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, GroupRecallNoticeEvent
from nonebot.adapters.onebot.v11.exception import ActionFailed, NetworkError

from . import cache, config
from .forward import build_forward_nodes
from .segments import message_to_segments, reply_preview_segments, expand_reply_segments, make_forward_node
from .utils import is_onebot_v11, bot_user_id
from .state import is_enabled


# 监听群消息事件：用于缓存（包括合并转发展开结果、reply 预览等）
group_msg = on_message(priority=10, block=False)


@group_msg.handle()
async def handle_group_message(bot: Bot, event: GroupMessageEvent):
    """缓存群消息（仅 OneBot v11）。"""

    if not is_onebot_v11(bot):
        return
    if not is_enabled():
        return

    if event.group_id not in config.monitor_groups:
        return

    sender_name = event.sender.card or event.sender.nickname
    message = event.get_message()

    # 先把当前消息转换为 segments（后续会用于撤回转发）
    message_segments = message_to_segments(message)

    # 优先使用 NoneBot 已经解析好的 event.reply（更稳定，避免撤回后再 get_msg 失败）
    if event.reply is not None and event.reply.sender.user_id is not None:
        reply_sender_name = event.reply.sender.card or event.reply.sender.nickname
        reply_sender_user_id = int(event.reply.sender.user_id)
        message_segments = reply_preview_segments(
            sender_name=reply_sender_name,
            sender_user_id=reply_sender_user_id,
            message=event.reply.message,
        ) + message_segments

    # 兼容：若 reply 预解析失败（reply 段仍留在 message 中），在缓存阶段就展开为可读文本
    message_segments = await expand_reply_segments(
        bot, message_segments, current_message_id=event.message_id
    )

    # 合并转发：收到时展开并缓存（撤回后后端可能无法 get_forward_msg）
    forward_nodes = await build_forward_nodes(
        bot,
        sender_name=sender_name,
        event_user_id=event.user_id,
        message=message,
        max_depth=config.forward_max_depth,
    )

    cache.put(
        event.message_id,
        cache.CachedMessage(
            sender_name=sender_name,
            message=message,
            group_id=event.group_id,
            sender_user_id=event.user_id,
            forward_nodes=forward_nodes,
            expanded_segments=message_segments,
        ),
    )


# 监听群消息撤回事件：用于转发
recall_notice = on_notice(priority=5, block=False)


@recall_notice.handle()
async def handle_group_recall(bot: Bot, event: GroupRecallNoticeEvent):
    """处理群消息撤回事件（仅 OneBot v11）。"""

    if not is_onebot_v11(bot):
        return
    if not is_enabled():
        return

    if event.group_id not in config.monitor_groups:
        return

    if not config.target_user_id:
        return

    cached = cache.get(event.message_id)
    if cached is None:
        return

    header = (
        f"群号: {cached.group_id}\n"
        f"发送者: {cached.sender_name}({cached.sender_user_id})\n"
        f"撤回消息ID: {event.message_id}\n"
    )

    # 合并转发节点（统一以机器人身份发送）
    nodes: list[dict[str, Any]] = [
        make_forward_node(user_id=bot_user_id(bot), nickname="防撤回", content=header)
    ]

    if cached.forward_nodes is not None:
        nodes.append(
            make_forward_node(
                user_id=bot_user_id(bot),
                nickname="防撤回",
                content="原消息为合并转发（已在收到消息时缓存展开内容）：",
            )
        )
        nodes.extend(cached.forward_nodes)
    else:
        nodes.append(
            make_forward_node(
                user_id=bot_user_id(bot),
                nickname=cached.sender_name,
                content=cached.expanded_segments,
            )
        )

    try:
        await bot.call_api(
            "send_private_forward_msg",
            user_id=config.target_user_id,
            messages=nodes,
            _timeout=30,
        )
        return
    except (ActionFailed, NetworkError):
        # 用户要求“尽量少输出”：无权限/失败直接静默
        return
