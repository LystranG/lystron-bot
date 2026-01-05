"""test send：在控制台输出机器人最近一次发送的消息（不回消息）。"""

from __future__ import annotations

from typing import Any
import json

from nonebot import logger
from nonebot.adapters import Bot as BaseBot, Event
from nonebot.adapters.onebot.v11 import Bot as V11Bot

from nb_shared.validate import is_superuser
from ..record import get_last_sent

from nonebot_plugin_alconna import AlcResult  # noqa: E402
from . import test_cmd


def _safe_dump(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


@test_cmd.assign("send")
async def handle_test_send(bot: BaseBot, event: Event, result: AlcResult):
    """输出最近一次发送消息记录（仅日志输出，不回复）。"""

    # 命令解析失败：静默
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
