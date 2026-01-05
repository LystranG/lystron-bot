"""适配器路由（策略选择）。"""

from __future__ import annotations

from nonebot.adapters import Bot as BaseBot
from nonebot_plugin_alconna import Segment

from nb_shared.validate import is_onebot_v11

from ..exceptions import UnsupportedAdapterError
from .base import AudioStrategy
from .onebot_v11 import OneBotV11AudioStrategy


async def get_audio_base64(bot: BaseBot, seg: Segment) -> str:
    if is_onebot_v11(bot):
        strategy = OneBotV11AudioStrategy()
    else:
        raise UnsupportedAdapterError("暂不支持该平台的语音解析（仅 OneBot V11）。")

    return await strategy.extract_audio_base64(bot, seg)

__all__ = ["get_audio_base64"]

