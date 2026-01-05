"""开发调试插件（dev-debug）。

目标：
- 在本插件的 `__init__.py` 里定义“主命令入口”（Alconna 命令结构）
- 每个子命令独立一个文件实现（`plugin/dev_debug/commands/<sub>.py`）

设计约定：
- 尽量少打扰正常聊天：无权限/不支持/参数错误直接静默
- 仅 OneBot V11 生效
"""

from nonebot import require
from nonebot.plugin import PluginMetadata

from nb_shared.alconna_ns import build_default_namespace

require("nonebot_plugin_alconna")



__plugin_meta__ = PluginMetadata(
    name="开发调试",
    description="机器人内置开发调试命令集合",
    usage="test send：在控制台输出机器人最近一次发送消息的记录（仅 OneBot V11，superuser 可用）",
)

from . import record as _record
from . import commands
