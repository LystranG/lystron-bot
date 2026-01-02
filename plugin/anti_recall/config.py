"""插件配置读取。

这里使用 driver.config / 环境变量（由 NoneBot 加载 .env，或容器直接注入环境变量）
并通过 pydantic 模型进行校验与默认值填充。
"""

from __future__ import annotations

from typing import Any
import json
import os
import re

from nonebot import get_driver, logger
from pydantic import BaseModel, Field
from pydantic import field_validator


def _coerce_int_list(value: Any) -> list[int]:
    """把输入值尽量规整为 list[int]。

用于兼容以下写法（无论来自 `.env` 还是直接环境变量）：
- 单个数字：RECALL_MONITOR_GROUPS=123
- JSON 数组：RECALL_MONITOR_GROUPS=[123,456]
- 逗号分隔：RECALL_MONITOR_GROUPS=123,456
"""

    if value is None:
        return []

    if isinstance(value, bool):
        # 避免 True/False 被当作 1/0
        return []

    if isinstance(value, int):
        return [value] if value else []

    if isinstance(value, (tuple, set)):
        value = list(value)

    if isinstance(value, list):
        out: list[int] = []
        for x in value:
            try:
                n = int(x)
            except Exception:
                continue
            if n and n not in out:
                out.append(n)
        return out

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
            if isinstance(parsed, int):
                return [parsed] if parsed else []
            if isinstance(parsed, list):
                return _coerce_int_list(parsed)

        # 其次：逗号/空白分隔（兼容 docker compose 环境变量里常见的写法）
        parts = [p for p in re.split(r"[,\s]+", s) if p]
        return _coerce_int_list(parts)

    return []


class Config(BaseModel):
    """防撤回插件配置模型（来自 `.env` 或直接环境变量）。"""

    recall_monitor_groups: list[int] = Field(default_factory=list, description="监听的群号列表")
    recall_target_user_id: list[int] = Field(
        default_factory=list, description="接收撤回消息的QQ号列表"
    )
    recall_archive_group_id: int = Field(
        default=0, description="转发消息归档群号（用于方案一：先归档后转发）"
    )

    @field_validator("recall_monitor_groups", mode="before")
    @classmethod
    def _coerce_monitor_groups(cls, value: Any):
        """把 RECALL_MONITOR_GROUPS 规整为 list[int]。"""

        return _coerce_int_list(value)

    @field_validator("recall_target_user_id", mode="before")
    @classmethod
    def _coerce_target_user_ids(cls, value: Any):
        """把 .env 的 RECALL_TARGET_USER_ID 规整为 list[int]。

        兼容以下写法：
        - 单个数字：RECALL_TARGET_USER_ID=123
        - JSON 数组：RECALL_TARGET_USER_ID=[123,456]
        - 逗号分隔：RECALL_TARGET_USER_ID=123,456
        """

        return _coerce_int_list(value)


def _env_first(*keys: str) -> str | None:
    """从环境变量中按顺序取第一个存在的值（兼容大小写写法）。"""

    for key in keys:
        if key in os.environ:
            return os.environ[key]
    return None


def load_config() -> Config:
    """加载插件配置。

为什么不用“只依赖 driver.config”？
- 线上容器里经常不挂载 `.env` 文件，而是直接通过环境变量注入配置；
- 不同运行方式/驱动实现下，driver.config 对“额外字段”的处理可能存在差异；
- 因此这里显式叠加 `os.environ` 中的同名变量，保证环境变量注入一定生效。
"""

    raw: dict[str, Any] = {}

    # 1) 尽量从 driver.config 拿（如果 NoneBot 尚未 init，则降级为空）
    try:
        driver = get_driver()
        raw.update(driver.config.model_dump())
    except ValueError:
        pass

    # 2) 再用环境变量覆盖（无论来自 .env 还是容器注入，最终都体现在 os.environ）
    # 注意：NoneBot 的 config 属性名会被规整为小写，因此同时兼容大小写两种 key。
    env_overrides = {
        "recall_monitor_groups": _env_first(
            "RECALL_MONITOR_GROUPS",
            "recall_monitor_groups",
            "NB_RECALL_MONITOR_GROUPS",
            "nb_recall_monitor_groups",
        ),
        "recall_target_user_id": _env_first(
            "RECALL_TARGET_USER_ID",
            "recall_target_user_id",
            "NB_RECALL_TARGET_USER_ID",
            "nb_recall_target_user_id",
        ),
        "recall_archive_group_id": _env_first(
            "RECALL_ARCHIVE_GROUP_ID",
            "recall_archive_group_id",
            "NB_RECALL_ARCHIVE_GROUP_ID",
            "nb_recall_archive_group_id",
        ),
    }
    for k, v in env_overrides.items():
        if v is not None:
            raw[k] = v

    cfg = Config.model_validate(raw)

    # 这里做一次“低噪声”告警，帮你在容器环境里快速定位配置是否生效。
    # 若你明确希望空列表表示“禁用/不监听”，可忽略该告警。
    if not cfg.recall_monitor_groups:
        logger.warning(
            "anti_recall 未配置 RECALL_MONITOR_GROUPS（监听群号列表为空），插件将不会处理任何群的撤回事件。"
        )
    if not cfg.recall_target_user_id:
        logger.warning(
            "anti_recall 未配置 RECALL_TARGET_USER_ID（接收撤回消息的 QQ 号列表为空），插件将不会转发撤回内容。"
        )

    return cfg


plugin_config: Config = load_config()

# 对外导出：监听群号 & 接收转发的目标 QQ 号
monitor_groups: list[int] = plugin_config.recall_monitor_groups
target_user_ids: list[int] = [int(x) for x in plugin_config.recall_target_user_id if int(x)]
archive_group_id: int = int(plugin_config.recall_archive_group_id or 0)
