"""Agent 插件自定义异常。

说明：
- 通过显式异常把“暂不支持的适配器/平台”等情况从业务逻辑中解耦出来
- commands 层负责捕获并转成用户可读的提示（或静默）
"""

from __future__ import annotations


class AgentError(Exception):
    """Agent 插件基础异常。"""


class UnsupportedAdapterError(AgentError):
    """当前适配器/平台暂不支持。"""

