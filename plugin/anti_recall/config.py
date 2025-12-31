"""插件配置读取。

这里使用 driver.config（由 NoneBot 加载 .env 等来源），并通过 pydantic 模型进行校验与默认值填充。
"""

from __future__ import annotations

from typing import Any
import json

from nonebot import get_driver
from pydantic import BaseModel, Field
from pydantic import field_validator


class Config(BaseModel):
    """防撤回插件配置模型（从 .env 读取）。"""

    recall_monitor_groups: list[int] = Field(default_factory=list, description="监听的群号列表")
    recall_target_user_id: list[int] = Field(
        default_factory=list, description="接收撤回消息的QQ号列表"
    )
    recall_archive_group_id: int = Field(
        default=0, description="转发消息归档群号（用于方案一：先归档后转发）"
    )

    @field_validator("recall_target_user_id", mode="before")
    @classmethod
    def _coerce_target_user_ids(cls, value: Any):
        """把 .env 的 RECALL_TARGET_USER_ID 规整为 list[int]。

        兼容以下写法：
        - 单个数字：RECALL_TARGET_USER_ID=123
        - JSON 数组：RECALL_TARGET_USER_ID=[123,456]
        - 逗号分隔：RECALL_TARGET_USER_ID=123,456
        """

        if value is None:
            return []

        if isinstance(value, int):
            return [value] if value else []

        if isinstance(value, (tuple, set)):
            value = list(value)

        if isinstance(value, list):
            return value

        if isinstance(value, str):
            s = value.strip()
            if not s:
                return []
            # 优先：JSON 数组
            if s.startswith("[") and s.endswith("]"):
                try:
                    parsed = json.loads(s)
                except Exception:
                    parsed = None
                if isinstance(parsed, list):
                    return parsed
                if isinstance(parsed, int):
                    return [parsed] if parsed else []
            # 其次：逗号分隔
            parts = [p.strip() for p in s.split(",")]
            ids: list[int] = []
            for p in parts:
                if not p:
                    continue
                try:
                    n = int(p)
                except Exception:
                    continue
                if n and n not in ids:
                    ids.append(n)
            return ids
        return value


driver = get_driver()
plugin_config: Config = Config.model_validate(driver.config.model_dump())

# 对外导出：监听群号 & 接收转发的目标 QQ 号
monitor_groups: list[int] = plugin_config.recall_monitor_groups
target_user_ids: list[int] = [int(x) for x in plugin_config.recall_target_user_id if int(x)]
archive_group_id: int = int(plugin_config.recall_archive_group_id or 0)
