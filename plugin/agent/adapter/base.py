"""适配器策略基类（策略模式）。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from nonebot.adapters import Bot as BaseBot, Event
from nonebot_plugin_alconna import Segment


class AudioStrategy(ABC):
    """不同适配器下“语音/音频”解析策略。"""

    @abstractmethod
    async def extract_audio_base64(self, bot: BaseBot, seg: Segment) -> str:
        """提取语音为 base64。

说明：
- 为了方便 n8n 侧统一处理，这里约定返回 base64（不含 data:mime 前缀）
- 具体实现依赖适配器 API/平台能力，OneBot V11 下通常需要结合 get_record / NapCat 能力
"""

