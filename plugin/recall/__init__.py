"""
撤回插件
撤回机器人自己的信息

"""

from nonebot.plugin import PluginMetadata


__plugin_meta__ = PluginMetadata(
    name="撤回插件",
    description="撤回机器人自己的消息",
    usage="recall <数量> [群聊ID]",
    extra={"author": "Lystran"},
)
