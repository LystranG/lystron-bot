import nonebot
from nonebot.adapters.onebot import V11Adapter
from nonebot.adapters.console import Adapter as ConsoleAdapter

nonebot.init()

driver = nonebot.get_driver()
driver.register_adapter(V11Adapter)
# driver.register_adapter(ConsoleAdapter)

# nonebot.load_plugin("thirdparty_plugin")
nonebot.load_plugins("plugin")

if __name__ == "__main__":
    nonebot.run()
