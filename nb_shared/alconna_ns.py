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

    try:
        driver = get_driver()
    except ValueError:
        # NoneBot 尚未初始化（例如单独 import 模块做静态检查时）
        return ["/"]

    starts = _to_str_list(getattr(driver.config, "command_start", None))
    return starts or ["/"]


def get_command_separators() -> list[str]:
    """读取 NoneBot 的 COMMAND_SEP（driver.config.command_sep）。

    说明：
    - NoneBot 的 COMMAND_SEP 主要用于原生命令解析（例如 `foo.bar` 形式的命令名分隔）
    - Alconna 的 separators 会影响解析行为；直接把 COMMAND_SEP 映射过来很容易导致
      `antirecall status` 这类“空格参数”无法匹配（例如 COMMAND_SEP=["."] 时会要求使用点分隔）
    - 因此此函数仅提供读取能力，默认不建议把它用于 Alconna 的 separators
    """

    try:
        driver = get_driver()
    except ValueError:
        return []
    return _to_str_list(getattr(driver.config, "command_sep", None))


def build_default_namespace(*, name: str = "nonebot"):
    """构造一个默认 Namespace，使用 NoneBot 的 COMMAND_START。

    注意：这里**只对齐 COMMAND_START**，避免把 NoneBot 的 COMMAND_SEP 误映射到
    Alconna 的 separators 导致解析异常。
    """

    # 延迟导入：避免在未安装 Alconna 时导入失败（部分脚本/工具场景）
    from arclet.alconna import Namespace, config  # noqa: WPS433

    ns = Namespace(name, prefixes=get_command_starts())
    # Alconna 内部会通过 `config.namespaces[command.namespace]` 取 namespace 配置；
    # 因此这里需要把命名空间挂载到全局配置里，避免 KeyError。
    config.namespaces[name] = ns
    return ns
