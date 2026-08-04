#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Qwen-VL vision MCP server (stdio, zero-dependency).

Exposes two tools:
  - describe_image(path, focus)  -> structured Chinese description of an image
  - ocr_image(path)              -> raw text found in the image

Backed by Alibaba DashScope OpenAI-compatible API (Qwen-VL models).
Configuration via environment:
  DASHSCOPE_API_KEY  (required)
  QWEN_VL_MODEL      (optional, default: qwen-vl-max)
  QWEN_VL_TIMEOUT    (optional, default: 120)
"""

import base64
import io
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request

API_KEY = os.environ.get("DASHSCOPE_API_KEY", "").strip()
MODEL = os.environ.get("QWEN_VL_MODEL", "qwen-vl-max").strip() or "qwen-vl-max"
API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
try:
    TIMEOUT = int(os.environ.get("QWEN_VL_TIMEOUT", "120"))
except ValueError:
    TIMEOUT = 120

PROTOCOL_VERSION = "2025-03-26"
SERVER_INFO = {"name": "qwen-vision", "version": "1.0.0"}

FOCUS_PROMPTS = {
    "auto": (
        "请详细分析这张图片，用中文输出：\n"
        "1) 整体内容与主题\n"
        "2) 布局与构图（如果包含界面/网页，请描述其结构）\n"
        "3) 主要颜色与视觉风格\n"
        "4) 图中所有可见文字（原样提取）\n"
        "5) 值得注意的细节或明显问题\n"
        "请分点输出，不要编造图中不存在的内容。"
    ),
    "layout": (
        "请只描述这张图片的布局与构图：元素位置、区块划分、对齐方式、留白与层级关系。"
        "如果是界面，说明导航、正文、图片、按钮各在什么位置。用中文输出。"
    ),
    "colors": (
        "请分析这张图片的配色方案：主色、辅助色、背景色（尽量给出近似色值），"
        "以及整体色调和色彩氛围。用中文输出。"
    ),
    "text": (
        "请提取这张图片中的所有文字内容，按阅读顺序原样输出，并说明文字所在的区域。用中文输出。"
    ),
    "code": (
        "这张图片可能包含代码或终端截图。请完整提取可见的代码/命令文本，"
        "保持缩进和字符原样，不要解释。如果图片不是代码，请说明。"
    ),
    "style": (
        "请描述这张图片的设计风格与视觉语言：字体气质、材质感、氛围、参考的艺术方向等。用中文输出。"
    ),
}

OCR_PROMPT = (
    "请只输出这张图片中的所有文字内容，按阅读顺序排列，不要添加任何解释、"
    "标题或格式标记。识别不出的部分用 [无法识别] 标注。"
)

TOOLS = [
    {
        "name": "describe_image",
        "description": (
            "分析一张本地图片并返回结构化中文描述（内容、布局、颜色、风格、文字等）。"
            "当任务涉及查看、理解或评审图片/截图/设计稿时调用。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "图片文件的绝对路径"},
                "focus": {
                    "type": "string",
                    "description": "分析重点：auto/layout/colors/text/code/style",
                    "enum": ["auto", "layout", "colors", "text", "code", "style"],
                    "default": "auto",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "ocr_image",
        "description": "提取本地图片中的全部文字（OCR），按阅读顺序返回。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "图片文件的绝对路径"},
            },
            "required": ["path"],
        },
    },
]


def _encode_image(path):
    """Read an image file and return a data URL, downscaling oversized images via PIL when possible."""
    if not os.path.isfile(path):
        raise ValueError("文件不存在: %s" % path)
    mime = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as handle:
        data = handle.read()
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(data))
        width, height = img.size
        if max(width, height) > 2048 or len(data) > 5 * 1024 * 1024:
            scale = 2048 / max(width, height)
            img = img.resize((max(1, int(width * scale)), max(1, int(height * scale))))
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=85)
            data = buf.getvalue()
            mime = "image/jpeg"
    except Exception:
        pass  # PIL unavailable or decode failed; send the original bytes
    return "data:%s;base64,%s" % (mime, base64.b64encode(data).decode("ascii"))


def _call_qwen(image_data_url, prompt):
    if not API_KEY:
        return (
            "错误：未配置 DASHSCOPE_API_KEY 环境变量。\n"
            "设置方式：export DASHSCOPE_API_KEY=sk-xxx（或写入 MCP 客户端的 env 配置，"
            "例如 Codex 的 ~/.codex/config.toml [mcp_servers.qwen-vision.env]），然后重启客户端。"
        )
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                    {"type": "text", "text": prompt},
                ],
            }
        ],
        "max_tokens": 1500,
    }
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + API_KEY,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            result = json.loads(response.read().decode("utf-8"))
        return result["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        return "DashScope API 错误 HTTP %s: %s" % (error.code, body[:600])
    except Exception as error:
        return "调用 Qwen-VL 失败: %s" % error


def _handle_tool_call(name, arguments):
    arguments = arguments or {}
    path = str(arguments.get("path", "")).strip().strip('"')
    if not path:
        return True, "缺少参数 path（图片的绝对路径）。"
    try:
        image_data_url = _encode_image(path)
    except Exception as error:
        return True, "读取图片失败: %s" % error

    if name == "describe_image":
        focus = str(arguments.get("focus", "auto") or "auto")
        prompt = FOCUS_PROMPTS.get(focus, FOCUS_PROMPTS["auto"])
    elif name == "ocr_image":
        prompt = OCR_PROMPT
    else:
        return True, "未知工具: %s" % name

    text = _call_qwen(image_data_url, prompt)
    is_error = text.startswith("错误：") or text.startswith("DashScope API 错误") or text.startswith("调用 Qwen-VL 失败")
    return is_error, text


def _send(message):
    sys.stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main():
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(message, dict):
            continue

        method = message.get("method")
        message_id = message.get("id")

        if method == "initialize":
            requested = (message.get("params") or {}).get("protocolVersion")
            _send(
                {
                    "jsonrpc": "2.0",
                    "id": message_id,
                    "result": {
                        "protocolVersion": requested or PROTOCOL_VERSION,
                        "capabilities": {"tools": {}},
                        "serverInfo": SERVER_INFO,
                    },
                }
            )
        elif method == "notifications/initialized" or method == "notifications/cancelled":
            continue  # notification, no reply
        elif method == "ping":
            _send({"jsonrpc": "2.0", "id": message_id, "result": {}})
        elif method == "tools/list":
            _send(
                {
                    "jsonrpc": "2.0",
                    "id": message_id,
                    "result": {"tools": TOOLS},
                }
            )
        elif method == "tools/call":
            params = message.get("params") or {}
            is_error, text = _handle_tool_call(params.get("name", ""), params.get("arguments") or {})
            _send(
                {
                    "jsonrpc": "2.0",
                    "id": message_id,
                    "result": {
                        "content": [{"type": "text", "text": text}],
                        "isError": is_error,
                    },
                }
            )
        elif message_id is not None:
            _send(
                {
                    "jsonrpc": "2.0",
                    "id": message_id,
                    "error": {"code": -32601, "message": "Method not found: %s" % method},
                }
            )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
