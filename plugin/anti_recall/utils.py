"""通用工具函数。

尽量保持无副作用，避免在这里做 I/O 或读取配置。
"""

from __future__ import annotations

from typing import Any

from nonebot.adapters.onebot.v11 import Bot

from .constants import ONEBOT_V11_NAME


def is_onebot_v11(bot: Bot) -> bool:
    """仅在 OneBot V11 平台启用本插件逻辑。"""

    return bot.type == ONEBOT_V11_NAME


def safe_int(value: Any) -> int:
    """将值安全地转换为 int，失败返回 0。"""

    try:
        return int(value)
    except Exception:
        return 0


def bot_user_id(bot: Bot) -> int:
    """获取机器人自身 QQ 号（用于合并转发 node 的 user_id 字段）。

    说明：合并转发 node 的头像/气泡展示与 `user_id` 有关。
    当前策略为统一使用机器人自身 ID，避免出现“企鹅头像/乱头像”。
    """

    return safe_int(bot.self_id)

