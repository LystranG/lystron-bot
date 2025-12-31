"""记录机器人“上一条发送消息”的信息（仅 OneBot V11）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from nonebot.adapters import Bot as BaseBot
from nonebot.adapters.onebot.v11 import Bot as V11Bot


@dataclass(frozen=True, slots=True)
class LastSentRecord:
    time: str
    api: str
    target: dict[str, Any]
    message: Any
    ok: bool
    exception: str | None


_last_sent: LastSentRecord | None = None


def get_last_sent() -> LastSentRecord | None:
    return _last_sent


def _extract_target(data: dict[str, Any]) -> dict[str, Any]:
    if "user_id" in data:
        return {"user_id": data.get("user_id")}
    if "group_id" in data:
        return {"group_id": data.get("group_id")}
    if "detail_type" in data:
        out = {"detail_type": data.get("detail_type")}
        if "user_id" in data:
            out["user_id"] = data.get("user_id")
        if "group_id" in data:
            out["group_id"] = data.get("group_id")
        return out
    return {}


@BaseBot.on_called_api
async def _record_last_sent(
    bot: BaseBot,
    exception: Exception | None,
    api: str,
    data: dict[str, Any],
    result: Any,
):
    """记录“上一条发送消息”。

    仅记录：
    - OneBot V11
    - API 名为发送类（send_*/forward_*）
    """

    if not isinstance(bot, V11Bot):
        return
    if not (api.startswith("send_") or api.startswith("forward_")):
        return

    payload = None
    if "message" in data:
        payload = data.get("message")
    elif "messages" in data:
        payload = data.get("messages")
    if payload is None:
        return

    global _last_sent
    _last_sent = LastSentRecord(
        time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        api=api,
        target=_extract_target(data),
        message=payload,
        ok=exception is None,
        exception=repr(exception) if exception is not None else None,
    )

