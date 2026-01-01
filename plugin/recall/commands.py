"""Alconna 命令注册：recall

注意：本文件只负责注册命令与参数解析，不实现具体撤回逻辑。
"""

from __future__ import annotations

from nonebot import require
from nonebot.adapters import Bot as BaseBot
from nonebot.adapters.onebot.v11 import GroupMessageEvent, PrivateMessageEvent
from nonebot.adapters.onebot.v11 import Bot as V11Bot

from nb_shared.alconna_ns import build_default_namespace

from .executers import recall_friend, recall_group

require("nonebot_plugin_alconna")

from arclet.alconna import Alconna, Args  # noqa: E402
from nonebot_plugin_alconna import (  # noqa: E402
    on_alconna,
    AlcResult,
    AlconnaMatch,
    Match,
)


recall_cmd = on_alconna(
    Alconna(
        "recall",
        Args["count", int]["group_id?", int],
        namespace=build_default_namespace(name="global"),
    ),
    priority=1,
    block=True,
    auto_send_output=False,
)


@recall_cmd.handle()
async def handle_group(
    bot: BaseBot,
    event: GroupMessageEvent,
    result: AlcResult,
    count: Match[int] = AlconnaMatch("count"),
    group_id: Match[int] = AlconnaMatch("group_id"),
):
    # 语法不匹配：静默
    if not result.matched:
        return

    # 仅 OneBot V11 平台生效（其他适配器静默）
    if not isinstance(bot, V11Bot):
        return

    target_group_id = group_id.result if group_id.available else event.group_id
    await recall_group(bot, target_group_id, count.result)

@recall_cmd.handle()
async def handle_friend(
    bot: BaseBot,
    event: PrivateMessageEvent,
    result: AlcResult,
    count: Match[int] = AlconnaMatch("count"),
    group_id: Match[int] = AlconnaMatch("group_id"),
):
    # 语法不匹配：静默
    if not result.matched:
        return

    # 仅 OneBot V11 平台生效（其他适配器静默）
    if not isinstance(bot, V11Bot):
        return

    if group_id.available:
        await recall_group(bot, group_id.result, count.result)
    else:
        await recall_friend(bot, event.user_id, count.result)
