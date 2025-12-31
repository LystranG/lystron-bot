"""
防撤回插件
监听群消息撤回事件，将撤回的消息转发给配置的用户

配置说明:
在 .env 文件中添加:
RECALL_MONITOR_GROUPS=[123456789, 987654321]  # 监听的群号列表
RECALL_TARGET_USER_ID=[123456789, 987654321]  # 接收撤回消息的 QQ 号列表
RECALL_ARCHIVE_GROUP_ID=123456789  # 归档群号（仅转发消息需要；用于先归档再转发）
"""
from nonebot.plugin import PluginMetadata


__plugin_meta__ = PluginMetadata(
    name="防撤回插件",
    description="监听群消息撤回事件，将撤回的消息转发给配置的用户",
    usage="在 .env 中配置 RECALL_MONITOR_GROUPS、RECALL_TARGET_USER_ID 等",
    extra={"author": "HelloAGENTS"},
)

# 导入 handlers 模块以注册事件监听器（on_message / on_notice）
from . import handlers as _handlers  # noqa: F401

# 导入 commands 模块以注册 Alconna 命令
from . import commands as _commands  # noqa: F401
