"""test send：在控制台输出机器人最近一次发送的消息（不回消息）。"""

from __future__ import annotations

from typing import Any
import json

from nonebot import logger, require
from nonebot.adapters import Bot as BaseBot, Event
from nonebot.adapters.onebot.v11 import Bot as V11Bot

from nb_shared.auth import is_superuser
from nb_shared.alconna_ns import build_default_namespace
from ..record import get_last_sent


require("nonebot_plugin_alconna")

from arclet.alconna import Alconna, Subcommand  # noqa: E402
from nonebot_plugin_alconna import on_alconna, AlcResult  # noqa: E402


def _safe_dump(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


test = on_alconna(
    Alconna(
        "test",
        Subcommand("send"),
        namespace=build_default_namespace(name="global"),
    ),
    priority=1,
    block=True,
    auto_send_output=False,
)


@test.handle()
async def _(bot: BaseBot, event: Event, result: AlcResult):
    # 命令解析失败/缺参数：静默
    if not result.matched:
        return

    # 只在 OneBot V11 生效
    if not isinstance(bot, V11Bot):
        return

    # 仅 superuser 可用；无权限静默
    if not is_superuser(event):
        return

    last = get_last_sent()
    if last is None:
        logger.info("[test send] 暂无记录")
        return

    logger.info(
        "[test send] {} ok={} api={} target={} message={} exception={}",
        last.time,
        last.ok,
        last.api,
        _safe_dump(last.target),
        _safe_dump(last.message),
        last.exception,
    )

