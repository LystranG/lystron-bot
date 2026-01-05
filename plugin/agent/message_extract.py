"""将 UniMessage 做结构化提取（文本/图片/语音/文件）。

约定：
- 本插件主要面向 OneBot V11，但提取逻辑尽量做到“能提多少提多少”
- 文件(File)目前直接判定为不支持（按你的需求），由 commands 层提示用户
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal, Union, List

from nonebot.adapters import Bot as BaseBot

from nonebot_plugin_alconna import Text, Image, Audio, UniMessage

from plugin.agent.adapter.router import get_audio_base64


Role = Literal["user", "assistant"]

class TextContent(BaseModel):
    type: Literal["text"] = "text"
    text: str

class ImageContent(BaseModel):
    type: Literal["image"] = "image"
    image: str
    file_name: str

class AudioContent(BaseModel):
    type: Literal["audio"] = "audio"
    audio: str

class ChatMessage(BaseModel):
    role: str
    content: List[Union[TextContent, ImageContent, AudioContent]]


async def extract_turn(bot: BaseBot, role: Role, msg: UniMessage) -> ChatMessage:
    """从 UniMessage 中提取结构化内容。"""

    res = ChatMessage(role=role, content=[])
    for seg in msg:
        match seg.type:
            case 'text':
                res.content.append(TextContent(text=seg.data.get("text")))
            case 'image':
                res.content.append(ImageContent(image=seg.data.get("url"), file_name=seg.data.get("id")))
            case 'voice':
                data = await get_audio_base64(bot, seg)
                res.content.append(AudioContent(audio=data))

    return res


__all__ = ["TextContent", "AudioContent", "ImageContent", "ChatMessage", "extract_turn"]

