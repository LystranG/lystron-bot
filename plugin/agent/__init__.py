"""
Agent 插件

目标：
- 提供一个可拓展的“需求提炼 -> 交给 n8n 执行”的入口
- 仅 OneBot V11 生效（本项目默认 NapCat 作为 OneBot 后端）

命令（Alconna）：
- a [文本]     # 启动/继续一次分析

说明：
- 这个插件会在需要更多信息时进入会话模式：后续用户消息会被该插件接管并继续追问/整理需求
- 当需求明确时，会将“普通文本 requirement”交给 n8n，由 n8n 决定如何执行与如何回复
"""

from nonebot.plugin import PluginMetadata

__plugin_meta__ = PluginMetadata(
    name="Agent（需求提炼）",
    description="使用 LLM 提炼用户的可执行需求，并将需求交给 n8n webhook 执行",
    usage="/a [开场词]",
    extra={"author": "Lystran"},
)

from . import config
from . import commands as _commands
