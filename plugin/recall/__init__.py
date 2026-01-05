"""
撤回插件（recall）

用途：
- 提供命令让机器人撤回自己最近发送的消息
- 仅 OneBot V11 平台生效

命令语法（Alconna）：
- recall <数量> [群聊id]
"""

from nonebot.plugin import PluginMetadata


__plugin_meta__ = PluginMetadata(
    name="撤回工具",
    description="撤回机器人自己发送的消息（仅 OneBot V11）",
    usage="recall <数量> [群聊id]",
)

# 导入 commands 模块以注册 Alconna 命令
from . import commands as _commands

