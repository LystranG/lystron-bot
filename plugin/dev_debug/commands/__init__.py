"""dev_debug 子命令实现包。
"""

from nb_shared.alconna_ns import build_default_namespace
from arclet.alconna import Alconna, Subcommand  # noqa: E402
from nonebot_plugin_alconna import on_alconna, AlcResult  # noqa: E402

# 主命令入口：test <subcommand>
test_cmd = on_alconna(
    Alconna(
        "test",
        Subcommand("send"),
        Subcommand("alconna"),
        namespace=build_default_namespace(name="global"),
    ),
    priority=1,
    block=True,
    auto_send_output=False,
)

# 导入子模块以完成注册（API hook / assign handler）
from . import test_send as _test_send
from . import test_alconna as _test_alconna
