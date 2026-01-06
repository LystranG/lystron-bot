from nonebot_plugin_alconna.pattern import Audio

from plugin.agent.message_extract import ChatMessage, TextContent, ImageContent, AudioContent
from ..config import config
from .router import system_prompt, AiResponse


async def request(messages: list[ChatMessage]) -> AiResponse:
    """调用 Gemini（google-genai）并返回严格 JSON 字符串。

    约定：
    - `messages` 为对话历史，最后一条为用户最新输入
    - 上下文最多取最近 15 条
    - 支持多模态：图片 URL、音频 base64(mp3)
    - 支持联网搜索：Google Search grounding（若模型/网关不支持则自动降级）
    """

    import asyncio
    import base64
    import json
    import re
    from typing import Any

    try:
        from google import genai
        from google.genai import types
    except Exception as e:
        raise RuntimeError(
            "缺少依赖：请安装 google-genai（Python 包名通常为 google-genai）。"
        ) from e

    base_url = (config.gemini_base_url or "").strip()
    api_key = (config.gemini_api_key or "").strip()
    model = (config.gemini_model or "").strip()

    if not api_key:
        raise RuntimeError("Gemini API Key 为空：请配置 AGENT__GEMINI_API_KEY。")
    if not model:
        raise RuntimeError("Gemini model 为空：请配置 AGENT__GEMINI_MODEL。")

    def _strip_data_url_prefix(data: str) -> str:
        if "," in data and data.strip().lower().startswith("data:"):
            return data.split(",", 1)[1]
        return data

    def _guess_image_mime_type(file_name: str) -> str:
        clean = file_name.lower()
        if clean.endswith(".png"):
            return "image/png"
        if clean.endswith(".webp"):
            return "image/webp"
        if clean.endswith(".gif"):
            return "image/gif"
        if clean.endswith(".bmp"):
            return "image/bmp"
        if clean.endswith(".tiff") or clean.endswith(".tif"):
            return "image/tiff"
        # 兜底：多数场景可用
        return "image/jpeg"

    def _parts_from_message(msg: ChatMessage) -> list[Any]:
        parts: list[Any] = []
        for c in msg.content:
            if isinstance(c, TextContent):
                c: TextContent = c
                text = c.text
                if text:
                    parts.append(types.Part.from_text(text=text))
                continue

            if isinstance(c, ImageContent):
                c: ImageContent = c
                url = c.image
                if url:
                    parts.append(
                        types.Part.from_uri(
                            file_uri=url,
                            mime_type=_guess_image_mime_type(c.file_name),
                        )
                    )
                continue

            if isinstance(c, AudioContent):
                c: AudioContent = c
                try:
                    audio_bytes = base64.b64decode(c.audio)
                except Exception:
                    # 不让整条请求失败：把原始内容作为文本兜底给模型
                    parts.append(types.Part.from_text(text=f"[语音base64解析失败] {c.audio[:80]}"))
                else:
                    parts.append(types.Part.from_bytes(data=audio_bytes, mime_type="audio/mp3"))
                continue

        # 如果整条消息没有可用 parts，避免构造空 content
        return parts

    def _build_contents(history: list[ChatMessage]) -> list[Any]:
        contents: list[Any] = []
        for m in history:
            role = (m.role or "").strip().lower()
            genai_role = "user" if role == "user" else "model"
            parts = _parts_from_message(m)
            if not parts:
                continue
            contents.append(types.Content(role=genai_role, parts=parts))
        return contents

    def _parse(text: str) -> AiResponse:
        raw = (text or "").strip()
        if not raw:
            return AiResponse()

        # “```json ... ```”
        fence = re.search(r"```(?:json)?\\s*(\\{.*?\\})\\s*```", raw, flags=re.S)
        if fence:
            raw = fence.group(1).strip()

        try:
            obj = json.loads(raw)
        except Exception:
            # 把模型输出塞到 question，确保上层始终拿到 JSON
            return AiResponse(response=raw)

        if not isinstance(obj, dict):
            return AiResponse(response=raw)
        # 规范化字段，避免缺 key

        return AiResponse(
            trigger_n8n=bool(obj.get("is_clarify", False)),
            payload=str(obj.get("requirement", "") or ""),
            response=str(obj.get("question", "") or "")
        )

    # 上下文最多 15 条（含最后一条用户输入）
    trimmed = messages[-15:]

    response_schema: dict[str, Any] = {
        "type": "OBJECT",
        "required": ["is_clarify", "requirement", "question"],
        "properties": {
            "is_clarify": {"type": "BOOLEAN"},
            "requirement": {"type": "STRING"},
            "question": {"type": "STRING"},
        },
    }

    client_kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        # 兼容自建网关/反代
        client_kwargs["http_options"] = {"base_url": base_url}

    client = genai.Client(**client_kwargs)

    contents = _build_contents(trimmed)
    req_config: dict[str, Any] = {
        "system_instruction": system_prompt.strip(),
        "response_mime_type": "application/json",
        "response_schema": response_schema,
    }

    async def _call_generate(cfg: dict[str, Any]):
        return await asyncio.to_thread(
            client.models.generate_content,
            model=model,
            contents=contents,
            config=cfg,
        )

    try:
        response = await _call_generate(req_config)
    except Exception:
        response = ""

    parsed = _parse(getattr(response, "text", "") or "")
    return parsed
