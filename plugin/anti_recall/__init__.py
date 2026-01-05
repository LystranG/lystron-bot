"""
防撤回插件
监听群消息撤回事件，将撤回的消息转发给配置的用户

配置说明:
在 .env 文件中添加:
ANTI_RECALL__MONITOR_GROUPS=[...]
ANTI_RECALL__TARGET_USER_ID=[...]
ANTI_RECALL__ARCHIVE_GROUP_ID=...
"""
from nonebot.plugin import PluginMetadata
from nonebot import get_plugin_config

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="防撤回插件",
    description="监听群消息撤回事件，将撤回的消息转发给配置的用户",
    usage="在 .env 中配置 RECALL_MONITOR_GROUPS、RECALL_TARGET_USER_ID 等",
    extra={"author": "Lystran"},
)

from . import config as _config

# 导入 handlers 模块以注册事件监听器（on_message / on_notice）
from . import handlers as _handlers

# 导入 commands 模块以注册 Alconna 命令
from . import commands as _commands
