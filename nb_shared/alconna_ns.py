"""Alconna 与 NoneBot 配置对齐（所有插件共用）。

目标：
- 让 Alconna 命令也遵循 NoneBot 的 `.env` 配置（例如 COMMAND_START）
- 避免每个插件重复写一套“前缀/分隔符”适配逻辑
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from nonebot import get_driver


def _to_str_list(value: Any) -> list[str]:
    """把配置值尽量规整为 list[str]（保持顺序）。"""

    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable):
        out: list[str] = []
        for x in value:
            if x is None:
                continue
            out.append(str(x))
        return out
    return [str(value)]


def get_command_starts() -> list[str]:
    """读取 NoneBot 的 COMMAND_START（driver.config.command_start）。

    注意：
    - NoneBot 的配置通常是 set/list/tuple[str]
    - 若未配置则使用 NoneBot 默认（通常会包含 "/"），这里做一个保守默认
    """

    starts = _to_str_list(getattr(get_driver().config, "command_start", None))
    return starts or ["/"]


def get_command_separators() -> list[str]:
    """读取 NoneBot 的 COMMAND_SEP（driver.config.command_sep）。

    部分项目不需要对齐 COMMAND_SEP，但提供出来便于未来统一。
    """

    return _to_str_list(getattr(get_driver().config, "command_sep", None))


def build_default_namespace(*, name: str = "nonebot"):
    """构造一个默认 Namespace，使用 NoneBot 的 command_start/command_sep。"""

    # 延迟导入：避免在未安装 Alconna 时导入失败（部分脚本/工具场景）
    from arclet.alconna import Namespace  # noqa: WPS433

    ns = Namespace(name, prefixes=get_command_starts())
    seps = get_command_separators()
    if seps:
        ns.separators = seps
    return ns

