
from nonebot import logger, require, on_message
from nonebot.adapters import Bot as BaseBot, Event

from nb_shared.validate import is_superuser

require("nonebot_plugin_alconna")

from nonebot_plugin_alconna import on_alconna, AlcResult  # noqa: E402
from nonebot_plugin_alconna import UniMsg, Image, Audio
from . import test_cmd

@test_cmd.assign("alconna")
async def test_alconna(msg: UniMsg, bot: BaseBot, event: Event, result: AlcResult):
    # 命令解析失败：静默
    if not result.matched:
        return

    # 仅 superuser 可用；无权限静默
    if not is_superuser(event):
        return

    if msg.startswith("stop"):
        await test_cmd.finish("end")
        return

    if msg.has(Image):
        await test_cmd.send("has image")
        img = msg.get(Image)

    await test_cmd.reject()


