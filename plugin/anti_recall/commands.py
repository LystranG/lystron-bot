"""Alconna 命令：antirecall

用法：
- antirecall            # 切换开关
- antirecall on/off     # 显式开启/关闭
- antirecall status     # 查看状态

权限：
- 默认仅 superuser 可用（避免被群友随意关闭）
- 无权限/参数不合法：不做任何输出（尽量减少干扰）
"""

from __future__ import annotations

from nonebot import require
from nonebot.adapters import Event

require("nonebot_plugin_alconna")

from arclet.alconna import Alconna, Args  # noqa: E402
from nonebot_plugin_alconna import (  # noqa: E402
    on_alconna,
    AlconnaMatch,
    Match,
)

from nb_shared.auth import is_superuser  # noqa: E402
from .state import is_enabled, set_enabled  # noqa: E402


antirecall = on_alconna(
    Alconna(
        "antirecall",
        Args["action?", str],
    ),
    # 关闭自动输出（包括语法错误、帮助等），由我们自行决定什么时候回复
    auto_send_output=False,
)


@antirecall.handle()
async def _(event: Event, action: Match[str] = AlconnaMatch("action")):
    if not is_superuser(event):
        return

    current = is_enabled()
    if not action.available:
        new_value = not current
        set_enabled(new_value)
        await antirecall.finish("已开启" if new_value else "已关闭")

    cmd = action.result.strip().lower()
    if cmd in {"on", "enable", "start", "开启", "开"}:
        set_enabled(True)
        await antirecall.finish("已开启")
    elif cmd in {"off", "disable", "stop", "关闭", "关"}:
        set_enabled(False)
        await antirecall.finish("已关闭")
    elif cmd in {"status", "state", "状态"}:
        await antirecall.finish("开启" if current else "关闭")
    elif cmd in {"toggle", "switch", "切换"}:
        new_value = not current
        set_enabled(new_value)
        await antirecall.finish("已开启" if new_value else "已关闭")
    else:
        # 参数不合法：静默处理，避免刷屏
        return
