"""插件配置读取。

这里使用 driver.config / 环境变量（由 NoneBot 加载 .env，或容器直接注入环境变量）
并通过 pydantic 模型进行校验与默认值填充。
"""

from __future__ import annotations
from pydantic import BaseModel, Field
from nonebot import get_plugin_config

class ScopeConfig(BaseModel):
    monitor_groups: list[int] = Field(default_factory=list, description="监听的群号列表")
    target_user_id: list[int] = Field(
        default_factory=list, description="接收撤回消息的QQ号列表"
    )
    archive_group_id: int = Field(
        default=0, description="转发消息归档群号（用于方案一：先归档后转发）"
    )

class Config(BaseModel):
    anti_recall: ScopeConfig

plugin_config = get_plugin_config(Config).anti_recall

monitor_groups: list[int] = plugin_config.monitor_groups
target_user_ids: list[int] = [int(x) for x in plugin_config.target_user_id if int(x)]
archive_group_id: int = int(plugin_config.archive_group_id or 0)
