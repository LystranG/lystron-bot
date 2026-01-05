"""Agent 插件配置读取。

设计目标：
- 容器环境常见做法是“不挂载 .env，而是直接注入环境变量”，因此这里显式支持 os.environ 覆盖
- 同时兼容 NoneBot driver.config（如果存在）

推荐环境变量（不包含敏感值的可写入 .env.example）：
- AGENT__N8N_BASE_URL=http://n8n:5678
- AGENT__N8N_API_KEY=xxxxxx
- AGENT__N8N_WEBHOOK_PATH=xxx  # 历史命名，实际为 agent webhook 路径

模型相关（Gemini，建议写到环境变量/密钥系统，不要提交到仓库）：
- AGENT__GEMINI_BASE_URL=http://xxx
- AGENT__GEMINI_API_KEY=xxxxxx
- AGENT__GEMINI_MODEL=gemini-2.5-flash
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, AliasChoices

from nonebot import get_plugin_config


class ScopedConfig(BaseModel):
    """Agent 插件配置。"""

    n8n_base_url: str = Field(default="", description="n8n Base URL，例如 http://n8n:5678")
    n8n_api_key: str = Field(default="", description="n8n API Key")
    n8n_webhook_path: str = Field(
        description="n8n webhook 路径（由后端进行路由/执行）",
    )

    provider: Literal["gemini"] = Field(default="gemini", description="Model provider")

    gemini_base_url: str = Field(default="", description="Gemini Base Url")
    gemini_api_key: str = Field(default="", description="Gemini API Key")
    gemini_model: str = Field(
        default="gemini-2.5-flash",
        description="gemini model",
    )


class Config(BaseModel):
    agent: ScopedConfig


config = get_plugin_config(Config).agent
