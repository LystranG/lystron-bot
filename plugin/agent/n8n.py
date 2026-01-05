"""n8n webhook 调用封装。"""

from __future__ import annotations

from urllib.parse import urljoin

import httpx
from pydantic import BaseModel

from .config import config

class N8NRequest(BaseModel):
    requirement: str
    session_id: str


def _build_url() -> str:
    base = config.n8n_base_url.rstrip("/") + "/"
    path = config.n8n_webhook_path.lstrip("/")
    return urljoin(base, path)

async def webhook_request(payload: N8NRequest):
    """调用 webhook（POST JSON）。"""

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if config.n8n_api_key:
        headers["Authorization"] = config.n8n_api_key

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(_build_url(), json=payload.model_dump(), headers=headers)
        resp.raise_for_status()
        return resp

__all__ = ["N8NRequest", "webhook_request"]

