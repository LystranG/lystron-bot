"""插件运行开关（持久化到共享 JSON 配置）。"""

from __future__ import annotations

from nb_shared.json_config import get_store, plugin_key


PLUGIN_NAME = "anti_recall"
ENABLED_KEY = plugin_key(PLUGIN_NAME, "enabled")


def is_enabled() -> bool:
    """是否启用反撤回逻辑（默认启用）。"""

    return get_store().get_bool(ENABLED_KEY, True)


def set_enabled(enabled: bool) -> None:
    store = get_store()
    store.set(ENABLED_KEY, bool(enabled))
    store.save()

