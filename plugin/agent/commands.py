"""Agent 命令与会话接管。

核心行为（按你的最新需求实现）：
1) 仅 superuser 可用
2) 仅 OneBot V11 私聊生效
3) 必须通过 `/a` 开启会话：
   - `/a <text>`：<text> 作为开场词（第一句），立即进入分析
   - `/a`：只开启会话，下一条普通私聊消息作为开场词（无需再带 /a）
4) 会话中每条消息进入 LLM（python-ai-sdk + Gemini）：
   - 需求不明确 => 追问（此时 bot 回复 + 会话继续）
   - 需求明确 => 把 requirement（普通文本）+ session_id POST 给 n8n webhook，随后结束会话
"""

from __future__ import annotations

from typing import Any

from nonebot import on_message, require
from nonebot.adapters import Bot as BaseBot, Event
from nonebot.log import logger
from nonebot.permission import SUPERUSER

from nb_shared.alconna_ns import build_default_namespace
from .n8n import webhook_request, N8NRequest

require("nonebot_plugin_alconna")

from arclet.alconna import Alconna, Args
from nonebot_plugin_alconna import (
    AlcResult,
    AlconnaMatch,
    Match,
    UniMsg,
    on_alconna,
)
from nonebot_plugin_alconna.uniseg import UniMessage  # noqa: E402

from .message_extract import extract_turn
from .session import SessionStore
from .ai.router import request


_sessions = SessionStore()

# 运行时缓存：避免每条消息都重建 client
_runtime_cache: dict[str, Any] = {}


def _session_key(bot: BaseBot, event: Event) -> str:
    return f"{bot.self_id}:{event.get_session_id()}"



agent_cmd = on_alconna(
    Alconna(
        "a",
        Args["text?", str],
        namespace=build_default_namespace(name="global"),
    ),
    permission=SUPERUSER,
    priority=1,
    block=True,
    auto_send_output=False,
)


@agent_cmd.handle()
async def open_session(
    bot: BaseBot,
    event: Event,
    result: AlcResult,
    text: Match[str] = AlconnaMatch("text"),
):
    # 语法不匹配：静默
    if not result.matched:
        return

    key = _session_key(bot, event)

    opening = text.result.strip() if text.available else ""

    sess = _sessions.create(key) if not _sessions.has(key) else _sessions.get(key)

    if not opening:
        await agent_cmd.finish("start")
        return

    user_msg = UniMessage.text(opening)
    sess.add(await extract_turn(bot, "user", user_msg))

    await _process_session_turn(bot, event, sess)


def _in_session_rule():
    async def _checker(bot: BaseBot, event: Event) -> bool:
        key = _session_key(bot, event)  # type: ignore[arg-type]
        return _sessions.has(key)

    return _checker


session_msg = on_message(
    rule=_in_session_rule(),
    priority=2,
    block=True,
    permission=SUPERUSER
)


@session_msg.handle()
async def handle_session_message(bot: BaseBot, event: Event, msg: UniMsg):

    key = _session_key(bot, event)
    sess = _sessions.get(key)

    # 用户输入结构化
    user_msg: UniMessage = msg
    structured = await extract_turn(bot, "user", user_msg)

    sess.add(structured)

    await _process_session_turn(bot, event, sess)


async def _process_session_turn(
    bot: BaseBot,
    event: Event,
    sess
) -> None:
    """把一条用户消息交给 LLM 处理，并按约定决定是否回复/结束会话。"""

    try:
        history = [t for t in sess.turns]
        decision = await request(history)
    except Exception as e:
        logger.exception("LLM 执行失败")
        await bot.send(event=event, message=f"LLM 执行失败：{e}")
        return

    if not decision.trigger_n8n:
        await bot.send(event=event, message=decision.response)
        sess.add(await extract_turn(bot, "assistant", UniMessage.text(decision.response)))
        return

    # 需求明确：交给 n8n。n8n 侧再决定是否/如何让机器人回复。
    try:
        await webhook_request(N8NRequest(requirement=decision.payload, session_id=sess.n8n_session_id))
    except Exception as e:
        logger.exception("调用 n8n 失败")
        await bot.send(event=event, message=f"调用 n8n 失败：{e}")
        return

    key = _session_key(bot, event)
    _sessions.pop(key)
