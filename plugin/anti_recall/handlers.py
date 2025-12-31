"""事件监听与业务编排。

把“监听/编排”与“纯函数工具”分离，便于维护与单测。

当前策略（NapCat + QQ 嵌套转发）：
- 普通消息：构造合并转发卡片发送给目标账号
- 转发消息：先转发到归档群保存一份（拿到归档群 message_id），撤回时用 NapCat 转发接口转给目标账号
"""

from __future__ import annotations

from nonebot import on_message, on_notice
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, GroupRecallNoticeEvent
from nonebot.adapters.onebot.v11.message import Message, MessageSegment
from nonebot import logger
import asyncio

from . import cache, config
from .segments import (
    message_to_segments,
    reply_preview_segments,
    expand_reply_segments,
    extract_forward_ids,
    segments_to_cq,
)
from .utils import is_onebot_v11, bot_user_id
from .state import is_enabled


async def _resolve_latest_group_message_id(bot: Bot, group_id: int) -> int | None:
    """通过 get_group_msg_history 获取某群最新一条消息的 message_id。

    NapCat 的 forward_group_single_msg 通常不会返回新消息的 message_id，
    但会确实在群内产生一条新的“转发后的消息”。对于专用归档群，这里取最新一条即可。
    """

    try:
        res = await bot.call_api(
            "get_group_msg_history",
            group_id=group_id,
            message_seq=0,
            count=1,
            reverseOrder=True,
            _timeout=20,
        )
    except Exception:
        return None

    if not isinstance(res, dict):
        return None
    messages = res.get("messages")
    if not isinstance(messages, list) or not messages:
        return None
    first = messages[0]
    if not isinstance(first, dict):
        return None
    try:
        mid = first.get("message_id")
        return int(mid) if mid is not None else None
    except Exception:
        return None


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

    # 方案2：只提取“外层转发”的 forward_id，撤回时原样发送该 forward 段
    forward_ids = extract_forward_ids(message) or None

    archived_message_id: int | None = None
    # 方案一：如果是转发消息，先归档到指定群聊，保存归档 message_id 供撤回时转发
    if forward_ids and config.archive_group_id and config.archive_group_id != event.group_id:
        try:
            # NapCat: forward_group_single_msg(group_id, message_id)
            res = await bot.call_api(
                "forward_group_single_msg",
                group_id=config.archive_group_id,
                message_id=event.message_id,
                _timeout=60,
            )
            await asyncio.sleep(1)
            # 优先从返回中取 message_id，若没有则回退为“拉取归档群最新一条”
            archived_message_id = await _resolve_latest_group_message_id(
                bot, config.archive_group_id
            )
        except Exception:
            archived_message_id = None

    cache.put(
        event.message_id,
        cache.CachedMessage(
            sender_name=sender_name,
            message=message,
            group_id=event.group_id,
            sender_user_id=event.user_id,
            forward_ids=forward_ids,
            expanded_segments=message_segments,
            archived_message_id=archived_message_id,
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

    if not config.target_user_ids:
        return

    cached = cache.get(event.message_id)
    if cached is None:
        return

    header = (
        f"群号: {cached.group_id}\n"
        f"发送者: {cached.sender_name}({cached.sender_user_id})\n"
        f"撤回消息ID: {event.message_id}\n"
    )

    # 方案一：转发消息优先使用 NapCat 的 forward_friend_single_msg 转发归档群内的消息
    try:
        if cached.forward_ids:
            if not config.archive_group_id:
                return

            # 必须使用“归档群里的 message_id”，否则会出现“该消息类型暂不支持查看”或转发失败
            src_msg_id = cached.archived_message_id
            if not src_msg_id:
                return

            for target_user_id in config.target_user_ids:
                try:
                    # 先发 header（避免 forward 动作失败时完全无提示）
                    await bot.send_private_msg(
                        user_id=target_user_id, message=MessageSegment.text(header)
                    )
                    await asyncio.sleep(1)
                    await bot.call_api(
                        "forward_friend_single_msg",
                        user_id=target_user_id,
                        message_id=src_msg_id,
                        _timeout=60,
                    )
                    await asyncio.sleep(1)
                    await bot.delete_msg(message_id=cached.archived_message_id)
                    logger.log("反撤回： 已发送反撤回信息到目的qq")
                except Exception:
                    # 用户要求“尽量少输出”：失败静默，继续下一个目标
                    continue
            return
        else:
            # 普通消息：恢复成“合并转发卡片”发送
            cq = segments_to_cq(cached.expanded_segments)
            nodes = [
                {
                    "type": "node",
                    "data": dict(
                        MessageSegment.node_custom(
                            int(bot_user_id(bot)), "防撤回", header
                        ).data
                    ),
                },
                {
                    "type": "node",
                    "data": dict(
                        MessageSegment.node_custom(
                            int(cached.sender_user_id), cached.sender_name, cq
                        ).data
                    ),
                },
            ]

            async def _send_one(target_user_id: int) -> None:
                try:
                    await bot.call_api(
                        "send_private_forward_msg",
                        user_id=target_user_id,
                        messages=nodes,
                        _timeout=60,
                    )
                    return
                except Exception:
                    # 降级为普通消息（静默）
                    msg = Message()
                    msg.append(MessageSegment.text(header))
                    if cq:
                        msg += Message(cq)
                    await bot.send_private_msg(user_id=target_user_id, message=msg)

            for target_user_id in config.target_user_ids:
                try:
                    await _send_one(target_user_id)
                except Exception:
                    continue
    except Exception:
        # 用户要求“尽量少输出”：发送失败直接静默
        return
    finally:
        cache.remove(event.message_id)
