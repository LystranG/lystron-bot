"""鉴权/权限相关的通用辅助。

后续所有插件使用 Alconna 命令时，都可以复用这里的权限判断。
"""

from __future__ import annotations

from nonebot import get_driver
from nonebot.adapters import Event


def is_superuser(event: Event) -> bool:
    """判断当前事件是否来自 superuser。"""

    user_id = event.get_user_id()
    superusers = getattr(get_driver().config, "superusers", []) or []
    return str(user_id) in {str(x) for x in superusers}

