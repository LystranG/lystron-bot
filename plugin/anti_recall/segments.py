"""OneBot v11 消息段与合并转发节点构造。

这里集中处理：
- Message <-> segments 的转换
- 合并转发 node 的构造
- reply 段的展开（转为“纯文本摘要”，避免频繁无法获取）
"""

from __future__ import annotations

from typing import Any, Callable, NamedTuple
import json

from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11.message import Message, MessageSegment

from . import cache
from .utils import safe_int


Segment = cache.Segment
ForwardNode = cache.ForwardNode


class ReplyLookupResult(NamedTuple):
    sender_name: str
    sender_user_id: int
    quoted_segments: list[Segment]
    offset_up: int | None


def _strip_all_ws(text: str) -> str:
    """去除所有空白字符（消除空格/换行/制表等）。"""

    return "".join(text.split())


def _normalize_name(name: str) -> str:
    name = _strip_all_ws(str(name or ""))
    return name or "未知"


def _summarize_reply_segments(segments: list[Segment], *, offset_up: int | None) -> str | None:
    """将被回复内容归一为纯文本摘要。

    规则：
    - 纯文本：输出文本
    - 纯图片：输出 [图片：往上第XXX条]（若无法计算则用 ?）
    - 图片+文字混合：图片替换为 [图片] 占位，文本原样（已去空白）
    - 其他情况：返回 None（表示无法获取）
    """

    allowed = {"text", "image"}
    if any(not isinstance(seg, dict) or seg.get("type") not in allowed for seg in segments):
        return None

    image_count = 0
    has_text = False
    for seg in segments:
        if seg.get("type") == "image":
            image_count += 1
            continue
        data = seg.get("data") if isinstance(seg.get("data"), dict) else {}
        if _strip_all_ws(str(data.get("text") or "")):
            has_text = True

    # 纯图片
    if image_count and not has_text:
        if offset_up is None or offset_up <= 0:
            return "[图片：往上第?条]"
        return f"[图片：往上第{offset_up}条]"

    # 纯文本（无图片）
    if image_count == 0 and has_text:
        texts: list[str] = []
        for seg in segments:
            if seg.get("type") != "text":
                continue
            data = seg.get("data") if isinstance(seg.get("data"), dict) else {}
            text = _strip_all_ws(str(data.get("text") or ""))
            if text:
                texts.append(text)
        return "".join(texts) if texts else None

    # 图片 + 文字混合
    if image_count and has_text:
        parts: list[str] = []
        for seg in segments:
            if seg.get("type") == "image":
                parts.append("[图片]")
                continue
            data = seg.get("data") if isinstance(seg.get("data"), dict) else {}
            text = _strip_all_ws(str(data.get("text") or ""))
            if text:
                parts.append(text)
        return "".join(parts) if parts else None

    return None


def _format_reply_line(*, sender_name: str, summary: str | None) -> str:
    """生成 reply 前置行 + 分隔符（下一行才是当前消息内容）。"""

    name = _normalize_name(sender_name)
    if summary is None:
        summary = "无法获取"
    else:
        summary = _strip_all_ws(summary)
    return f"回复(用户：{name})：{summary}\n────────────\n"


def message_to_segments(message: Message) -> list[Segment]:
    """将 NoneBot 的 Message 转为 OneBot message 数组（list[segment]）。"""

    return [{"type": seg.type, "data": dict(seg.data)} for seg in message]


def segments_to_cq(segments: list[Segment]) -> str:
    """把 message 数组转为 CQ 字符串。

    说明：
    - NapCat 在 send_*_forward_msg 的自定义 node 中，通常更稳定地解析字符串形式的 content
    - 因此 forward node 的 content 统一用 CQ 字符串输出（图片/视频等会以 CQ 码表示）
    """

    msg = Message()
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        seg_type = seg.get("type")
        data = seg.get("data")
        if not seg_type or not isinstance(data, dict):
            continue
        msg.append(MessageSegment(str(seg_type), dict(data)))
    return str(msg)


def _normalize_sendable_segments(segments: list[Segment]) -> list[Segment]:
    """尽量把“可接收但不可发送”的字段形态修正为更通用的发送形态。

    经验规则（适配不同 OneBot 实现差异）：
    - image/video/file 段：若只有 url，没有 file，则尝试把 file 补成 url（很多实现支持 file=url）。
    """

    for seg in segments:
        if not isinstance(seg, dict):
            continue
        seg_type = seg.get("type")
        if seg_type not in {"image", "video", "file"}:
            continue
        data = seg.get("data")
        if not isinstance(data, dict):
            continue
        if not data.get("file") and data.get("url"):
            data["file"] = str(data["url"])
    return segments


def normalize_content_to_segments(content: Any) -> list[Segment]:
    """把任意内容规整为 OneBot message 数组。

    说明：
    - 合并转发 node 的 content 推荐使用 message 数组，而不是 CQ 字符串
    - 图片/文件/视频等段才能被客户端正确渲染
    """

    if content is None:
        return [{"type": "text", "data": {"text": "（空内容）"}}]

    if isinstance(content, str):
        # 关键：NapCat/部分实现会把 message 以 CQ 字符串形式返回（例如包含 [CQ:forward]），
        # 这里用 OneBot Message 解析，才能识别嵌套 forward/image 等段并继续展开。
        return _normalize_sendable_segments(message_to_segments(Message(content)))

    if isinstance(content, Message):
        return _normalize_sendable_segments(message_to_segments(content))

    if isinstance(content, MessageSegment):
        return _normalize_sendable_segments([{"type": content.type, "data": dict(content.data)}])

    # OneBot 常见格式：{"type": "...", "data": {...}} 或其列表
    if isinstance(content, dict) and content.get("type") and isinstance(content.get("data"), dict):
        return _normalize_sendable_segments([content])  # type: ignore[return-value]

    if isinstance(content, list) and all(
        isinstance(x, dict) and x.get("type") and isinstance(x.get("data"), dict) for x in content
    ):
        return _normalize_sendable_segments(content)  # type: ignore[return-value]

    return [{"type": "text", "data": {"text": json.dumps(content, ensure_ascii=False)}}]


def make_forward_node(*, user_id: int, nickname: str, content: Any) -> ForwardNode:
    """构造 send_private_forward_msg / send_group_forward_msg 需要的 node。"""

    # 兼容策略：优先使用 go-cqhttp/OneBot v11 常见字段（NapCat 更可能按此解析为 PacketMsg）
    # - user_id: 发送者 QQ 号（用 int，避免实现端类型严格导致丢弃）
    # - nickname: 昵称（必须与转发记录一致）
    # - content: CQ 字符串（NapCat 解析更稳定）
    segments = normalize_content_to_segments(content)
    cq = segments_to_cq(segments)
    return {
        "type": "node",
        "data": {
            "user_id": int(user_id),
            "nickname": nickname,
            "content": cq,
        },
    }


def extract_forward_ids(message: Message) -> list[str]:
    """从消息中提取 forward 段 id。"""

    ids: list[str] = []
    for seg in message:
        if seg.type != "forward":
            continue
        # 兼容不同 OneBot 实现的字段命名差异
        forward_id = (
            seg.data.get("id")
            or seg.data.get("forward_id")
            or seg.data.get("res_id")
            or seg.data.get("file")
        )
        if forward_id:
            ids.append(str(forward_id))
    return ids


def extract_sender_user_id(sender: dict[str, Any]) -> int:
    """从不同实现返回的 sender 字段中尽量提取 user_id。"""

    for key in ("user_id", "uin", "qq", "id", "uid", "userId"):
        user_id = safe_int(sender.get(key))
        if user_id:
            return user_id
    return 0


def reply_preview_segments(*, sender_name: str, sender_user_id: int, message: Message) -> list[Segment]:
    """把 “reply 事件预解析” 的被回复消息转成一段可读预览块。"""

    summary = _summarize_reply_segments(message_to_segments(message), offset_up=None)
    return [{"type": "text", "data": {"text": _format_reply_line(sender_name=sender_name, summary=summary)}}]


async def expand_reply_segments(
    bot: Bot,
    segments: list[Segment],
    *,
    timeout: int = 10,
    current_message_id: int | None = None,
    local_reply_lookup: Callable[[int], ReplyLookupResult | None] | None = None,
) -> list[Segment]:
    """将 message 数组中的 reply 段展开为“引用预览”文本块。

    备注：
    - QQ 合并转发中通常不会渲染 reply 气泡
    - 且 reply 引用的 message_id 在撤回后/内层消息场景经常无法通过 get_msg 获取
    - 所以优先走本插件缓存（cache.get），不行再尝试 bot.get_msg
    """

    expanded: list[Segment] = []

    for seg in segments:
        if not (isinstance(seg, dict) and seg.get("type") == "reply"):
            expanded.append(seg)
            continue

        data = seg.get("data") if isinstance(seg.get("data"), dict) else {}
        reply_message_id = safe_int(data.get("id") or data.get("message_id") or data.get("messageId") or 0)
        if not reply_message_id:
            # 部分实现的 reply 段可能不提供可用 id，此时在 forward 场景下回退到“上一条”
            if local_reply_lookup is not None:
                found = local_reply_lookup(0)
                if found is not None:
                    summary = _summarize_reply_segments(found.quoted_segments, offset_up=found.offset_up)
                    expanded.append(
                        {
                            "type": "text",
                            "data": {
                                "text": _format_reply_line(sender_name=found.sender_name, summary=summary)
                            },
                        }
                    )
                    continue
            expanded.append({"type": "text", "data": {"text": _format_reply_line(sender_name="未知", summary=None)}})
            continue

        # 1) 优先：本次合并转发内部可解析的 reply（例如引用了同一转发里的上一条消息）
        if local_reply_lookup is not None:
            found = local_reply_lookup(reply_message_id)
            if found is not None:
                summary = _summarize_reply_segments(found.quoted_segments, offset_up=found.offset_up)
                expanded.append({"type": "text", "data": {"text": _format_reply_line(sender_name=found.sender_name, summary=summary)}})
                continue

        # 2) 其次：本插件缓存（最近 100 条）
        cached = cache.get(reply_message_id)
        if cached is not None:
            offset = None
            if current_message_id is not None:
                offset = cache.offset_up(current_message_id, reply_message_id)
            summary = _summarize_reply_segments(message_to_segments(cached.message), offset_up=offset)
            expanded.append({"type": "text", "data": {"text": _format_reply_line(sender_name=cached.sender_name, summary=summary)}})
            continue

        # 3) 最后：尝试通过后端 API 获取
        try:
            msg_data = await bot.get_msg(message_id=reply_message_id, _timeout=timeout)
        except Exception:
            expanded.append({"type": "text", "data": {"text": _format_reply_line(sender_name="未知", summary=None)}})
            continue

        sender = msg_data.get("sender", {}) if isinstance(msg_data, dict) else {}
        nickname = str(sender.get("card") or sender.get("nickname") or "未知")
        quoted = None
        if isinstance(msg_data, dict):
            quoted = msg_data.get("message")
            if quoted is None and "content" in msg_data:
                quoted = msg_data.get("content")

        quoted_segments = normalize_content_to_segments(quoted)
        summary = _summarize_reply_segments(quoted_segments, offset_up=None)
        expanded.append({"type": "text", "data": {"text": _format_reply_line(sender_name=nickname, summary=summary)}})

    return expanded
