"""插件配置读取。

这里使用 driver.config（由 NoneBot 加载 .env 等来源），并通过 pydantic 模型进行校验与默认值填充。
"""

from __future__ import annotations

from nonebot import get_driver
from pydantic import BaseModel, Field


class Config(BaseModel):
    """防撤回插件配置模型（从 .env 读取）。"""

    recall_monitor_groups: list[int] = Field(default_factory=list, description="监听的群号列表")
    recall_target_user_id: int = Field(default=0, description="接收撤回消息的QQ号")
    recall_forward_max_depth: int = Field(
        default=4, description="合并转发最大嵌套层数（包含第一层）"
    )
    recall_archive_group_id: int = Field(
        default=0, description="转发消息归档群号（用于方案一：先归档后转发）"
    )


driver = get_driver()
plugin_config: Config = Config.model_validate(driver.config.model_dump())

# 对外导出：监听群号 & 接收转发的目标 QQ 号
monitor_groups: list[int] = plugin_config.recall_monitor_groups
target_user_id: int = plugin_config.recall_target_user_id
forward_max_depth: int = max(1, int(plugin_config.recall_forward_max_depth))
archive_group_id: int = int(plugin_config.recall_archive_group_id or 0)
