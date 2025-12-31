"""JSON 配置存取（所有插件共用）。

设计目标：
- 一个 JSON 文件承载所有插件配置（按插件名分组）
- 支持通过 .env 指定配置文件路径
- 提供简单易用的 get/set API，并做原子写入，避免写坏文件

.env 配置项：
- NB_CONFIG_JSON_PATH=/path/to/config.json

推荐结构：
{
  "plugins": {
    "anti_recall": {
      "enabled": true
    }
  }
}
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
import json
import os
import threading


DEFAULT_ENV_KEY = "NB_CONFIG_JSON_PATH"
DEFAULT_PATH = "data/config.json"


def _split_path(path: str) -> list[str]:
    return [p for p in path.split(".") if p]


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True, slots=True)
class JsonConfigLocation:
    """配置文件位置。"""

    path: Path


class JsonConfigStore:
    """JSON 配置存储（带内存缓存与线程锁）。"""

    def __init__(self, location: JsonConfigLocation):
        self._location = location
        self._lock = threading.RLock()
        self._data: dict[str, Any] | None = None

    @property
    def path(self) -> Path:
        return self._location.path

    def _load_if_needed(self) -> dict[str, Any]:
        if self._data is not None:
            return self._data

        path = self._location.path
        if not path.exists():
            self._data = {}
            return self._data

        try:
            self._data = json.loads(path.read_text(encoding="utf-8") or "{}")
        except Exception:
            # 文件损坏/空文件等情况：保守降级为 {}，避免插件直接崩溃
            self._data = {}
        if not isinstance(self._data, dict):
            self._data = {}
        return self._data

    def reload(self) -> None:
        """强制从磁盘重新加载。"""

        with self._lock:
            self._data = None
            self._load_if_needed()

    def get(self, key: str, default: Any = None) -> Any:
        """通过点路径读取，例如 'plugins.anti_recall.enabled'。"""

        with self._lock:
            data = self._load_if_needed()
            cur: Any = data
            for part in _split_path(key):
                if not isinstance(cur, dict) or part not in cur:
                    return default
                cur = cur[part]
            return cur

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self.get(key, default)
        return bool(value)

    def set(self, key: str, value: Any) -> None:
        """通过点路径写入（只写内存，不自动保存）。"""

        with self._lock:
            data = self._load_if_needed()
            parts = _split_path(key)
            if not parts:
                return

            cur: dict[str, Any] = data
            for part in parts[:-1]:
                nxt = cur.get(part)
                if not isinstance(nxt, dict):
                    nxt = {}
                    cur[part] = nxt
                cur = nxt
            cur[parts[-1]] = value

    def save(self) -> None:
        """原子写入保存到磁盘。"""

        with self._lock:
            data = self._load_if_needed()
            path = self._location.path
            _ensure_parent(path)

            tmp = path.with_suffix(path.suffix + ".tmp")
            tmp.write_text(
                json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            os.replace(tmp, path)


_store_singleton: JsonConfigStore | None = None


def get_store() -> JsonConfigStore:
    """获取全局 JSON 配置 store（单例）。"""

    global _store_singleton
    if _store_singleton is not None:
        return _store_singleton

    path_str = os.getenv(DEFAULT_ENV_KEY, DEFAULT_PATH)
    path = Path(path_str)
    if not path.is_absolute():
        # 相对路径默认以当前工作目录为基准（与 bot.py 运行方式一致）
        path = (Path.cwd() / path).resolve()

    _store_singleton = JsonConfigStore(JsonConfigLocation(path=path))
    return _store_singleton


def plugin_key(plugin_name: str, key: str) -> str:
    """构造插件配置 key：plugins.<plugin>.<key>。"""

    return f"plugins.{plugin_name}.{key}"

