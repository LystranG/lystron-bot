"""开发调试插件（dev-debug）。

约定：
- 每个子命令独立一个文件，避免 __init__ 过于臃肿
- 尽量少打扰正常群聊：无权限/不支持/参数错误直接静默
"""

from nonebot.plugin import PluginMetadata


__plugin_meta__ = PluginMetadata(
    name="开发调试",
    description="机器人内置开发调试命令集合",
    usage="test send：在控制台输出机器人最近一次发送消息的记录（仅 OneBot V11，superuser 可用）",
)

# 导入子模块以完成注册（API hook / matcher）
from . import record as _record  # noqa: F401
from .commands import test_send as _test_send  # noqa: F401
