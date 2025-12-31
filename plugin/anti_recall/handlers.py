"""事件监听与业务编排。

把“监听/编排”与“纯函数工具”分离，便于维护与单测。

方案2（NapCat 嵌套转发支持）：
- 不再尝试重建合并转发或展开内层（会触发 NapCat “内层消息无法获取转发消息”限制）
- 撤回时直接把“原消息里的外层 forward 段”原样发送给目标账号，让 QQ 客户端原生渲染嵌套
"""

from __future__ import annotations

from typing import Any

from nonebot import on_message, on_notice
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, GroupRecallNoticeEvent
from nonebot.adapters.onebot.v11.message import Message, MessageSegment

from . import cache, config
from .segments import message_to_segments, reply_preview_segments, expand_reply_segments, extract_forward_ids, segments_to_cq
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

    # 方案2：只提取“外层转发”的 forward_id，撤回时原样发送该 forward 段
    forward_ids = extract_forward_ids(message) or None

    cache.put(
        event.message_id,
        cache.CachedMessage(
            sender_name=sender_name,
            message=message,
            group_id=event.group_id,
            sender_user_id=event.user_id,
            forward_ids=forward_ids,
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

    # 发送为普通私聊消息（不再重建合并转发），以避免 NapCat 对内层转发 get_forward_msg 的限制
    try:
        if cached.forward_ids:
            # NapCat 私聊发送 [CQ:forward] 可能超时，优先走“引用原消息 message_id”的 node 转发：
            # send_private_forward_msg(messages=[node_custom(header), node(id=原消息message_id)])
            try:
                await bot.call_api(
                    "send_private_forward_msg",
                    user_id=config.target_user_id,
                    messages=[
                        {
                            "type": "node",
                            "data": {
                                "user_id": str(bot_user_id(bot)),
                                "nickname": "防撤回",
                                "content": header,
                            },
                        },
                        {"type": "node", "data": {"id": str(event.message_id)}},
                    ],
                    _timeout=60,
                )
                return
            except Exception:
                # 失败则降级：至少把 header 发出去
                await bot.send_private_msg(
                    user_id=config.target_user_id, message=MessageSegment.text(header)
                )
                return
        else:
            # 普通消息：按缓存的 segments 输出（CQ 字符串形式更兼容）
            cq = segments_to_cq(cached.expanded_segments)
            msg = Message()
            msg.append(MessageSegment.text(header))
            if cq:
                msg += Message(cq)
            await bot.send_private_msg(user_id=config.target_user_id, message=msg)
    except Exception:
        # 用户要求“尽量少输出”：发送失败直接静默
        return
