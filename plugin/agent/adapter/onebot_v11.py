"""OneBot V11 策略实现（语音/音频解析）。

注意：
- 这里的 extract_audio_base64 暂时留空，由你按 NapCat/OneBot 具体行为补全
- 我们保持接口稳定：返回 base64（不含 data: 前缀），并尽量不要在这里做业务判断
"""

from __future__ import annotations

from typing import Any

from nonebot.adapters import Bot as BaseBot, Event
from nonebot_plugin_alconna import Segment

from nonebot.adapters.onebot.v11 import Bot as V11Bot

from .base import AudioStrategy


class OneBotV11AudioStrategy(AudioStrategy):
    async def extract_audio_base64(self, bot: BaseBot, seg: Segment) -> str:
        voice_id: str = seg.data.get("id")
        if voice_id is None:
            return ""

        if not isinstance(bot, V11Bot):
            return ""

        try:
            bot: V11Bot = bot
            res = await bot.get_record(file=voice_id, out_format="mp3")
        except Exception:
            return ""

        return res.get("base64")

__all__ = ["OneBotV11AudioStrategy"]

