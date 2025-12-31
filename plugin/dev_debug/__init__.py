"""开发调试插件（dev-debug）。

目标：
- 提供一些仅 superuser 可用的调试命令
- 尽量少打扰正常群聊：无权限/不支持场景直接静默
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
import json
import html
import re

from nonebot import logger, on_command
from nonebot.adapters import Bot as BaseBot, Event
from nonebot.adapters.onebot.v11 import Bot as V11Bot
from nonebot.plugin import PluginMetadata
from nonebot.params import CommandArg

from nb_shared.auth import is_superuser


__plugin_meta__ = PluginMetadata(
    name="开发调试",
    description="机器人内置开发调试命令集合",
    usage="test-send：在控制台输出机器人最近一次成功发送的消息（仅 OneBot V11，superuser 可用）",
)


@dataclass(frozen=True, slots=True)
class LastSentRecord:
    time: str
    api: str
    target: dict[str, Any]
    message: Any


_last_sent: LastSentRecord | None = None


# 匹配形如：[CQ:forward,id=123]（注意：日志中可能会被 HTML 转义，调用前会 html.unescape）
_FORWARD_CQ_RE = re.compile(r"\[CQ:forward,([^\]]+)\]")


def _extract_forward_ids_from_text(text: str) -> set[str]:
    """从 CQ 字符串（含可能的 HTML 转义）中提取 forward id。"""

    ids: set[str] = set()
    raw = html.unescape(text or "")
    for m in _FORWARD_CQ_RE.finditer(raw):
        params = m.group(1).split(",")
        for p in params:
            p = p.strip()
            if p.startswith("id=") and len(p) > 3:
                ids.add(p[3:])
            elif p.startswith("resid=") and len(p) > 6:
                ids.add(p[6:])
    return ids


def _collect_forward_ids(value: Any, out: set[str]) -> None:
    """递归扫描结构，收集 forward_id/resid。"""

    if value is None:
        return
    if isinstance(value, str):
        out.update(_extract_forward_ids_from_text(value))
        return
    if isinstance(value, dict):
        if value.get("type") == "forward":
            data = value.get("data") if isinstance(value.get("data"), dict) else {}
            fid = (
                data.get("id")
                or data.get("resid")
                or data.get("res_id")
                or data.get("forward_id")
            )
            if fid:
                out.add(str(fid))
        for v in value.values():
            _collect_forward_ids(v, out)
        return
    if isinstance(value, (list, tuple)):
        for v in value:
            _collect_forward_ids(v, out)
        return


def _safe_dump(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


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
    - 调用成功（exception is None）
    - API 名以 send_ 开头（发送类）
    """

    if exception is not None:
        return
    if not isinstance(bot, V11Bot):
        return
    if not api.startswith("send_"):
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
    )


test_send = on_command("test-send", priority=1, block=True)


@test_send.handle()
async def _(bot: BaseBot, event: Event):
    """在控制台输出机器人最近一次发送的消息（不回消息）。"""

    # 只在 OneBot V11 生效
    if not isinstance(bot, V11Bot):
        return
    # 仅 superuser 可用；无权限静默
    if not is_superuser(event):
        return

    if _last_sent is None:
        logger.info("[test-send] 暂无记录")
        return

    # NoneBot 的 logger 基于 loguru，使用 {} 风格格式化（而不是 logging 的 %s）。
    logger.info(
        "[test-send] {} api={} target={} message={}",
        _last_sent.time,
        _last_sent.api,
        _safe_dump(_last_sent.target),
        _safe_dump(_last_sent.message),
    )
    return


test_forwardid = on_command("test-forwardid", priority=1, block=True)


@test_forwardid.handle()
async def _(bot: BaseBot, event: Event):
    """从“上一条机器人发送的消息”里提取 forward_id，并输出到控制台（不回消息）。"""

    if not isinstance(bot, V11Bot):
        return
    if not is_superuser(event):
        return
    if _last_sent is None:
        logger.info("[test-forwardid] 暂无记录")
        return

    ids: set[str] = set()
    _collect_forward_ids(_last_sent.message, ids)
    if not ids:
        logger.info("[test-forwardid] 未发现 forward_id")
        return

    logger.info("[test-forwardid] {}", sorted(ids))
    return


test_forward = on_command("test-forward", priority=1, block=True)


@test_forward.handle()
async def _(bot: BaseBot, event: Event, arg=CommandArg()):
    """在控制台打印 get_forward_msg 的原始返回（不回消息）。

    用法：test-forward <forward_id>
    """

    if not isinstance(bot, V11Bot):
        return
    if not is_superuser(event):
        return

    forward_id = str(arg).strip()
    if not forward_id:
        return

    try:
        data = await bot.get_forward_msg(id=forward_id, _timeout=10)
    except Exception as e:
        logger.info("[test-forward] id={} exception={}", forward_id, repr(e))
        return

    if not isinstance(data, dict):
        logger.info("[test-forward] id={} bad_type={}", forward_id, type(data))
        logger.info("[test-forward] raw={}", _safe_dump(data)[:2000])
        return

    msgs = data.get("messages", [])
    logger.info(
        "[test-forward] id={} keys={} messages_len={}",
        forward_id,
        list(data.keys()),
        len(msgs) if isinstance(msgs, list) else "not_list",
    )

    if isinstance(msgs, list):
        for idx, item in enumerate(msgs[:3], start=1):
            if not isinstance(item, dict):
                logger.info("[test-forward] item#{} bad_item_type={}", idx, type(item))
                continue
            sender = item.get("sender", {}) if isinstance(item.get("sender"), dict) else {}
            content = item.get("content")
            if content is None and "message" in item:
                content = item.get("message")
            logger.info(
                "[test-forward] item#{} sender={} content_preview={}",
                idx,
                _safe_dump(sender)[:500],
                _safe_dump(content)[:800],
            )

    # 额外：尽量输出可能包含 res_id 的字段，便于定位 NapCat 映射
    for k in ("res_id", "resid", "resId", "forward_id", "forwardId"):
        if k in data:
            logger.info("[test-forward] {}={}", k, _safe_dump(data.get(k))[:800])
