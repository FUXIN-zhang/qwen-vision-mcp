# qwen-vision MCP Server

让支持 MCP（Model Context Protocol）的 AI 客户端获得"看图"能力：把本地图片发给阿里云百炼的 **Qwen-VL** 视觉模型，返回结构化描述或纯文字 OCR。

Works with Codex, Claude Code, Cursor and any MCP-capable client. Zero third-party dependencies — pure Python standard library.

## 功能 / Features

- `describe_image(path, focus)` — 结构化中文描述：内容、布局、配色、风格、可见文字；`focus` 可指定 `auto / layout / colors / text / code / style`
- `ocr_image(path)` — 提取图片中的全部文字，按阅读顺序返回
- 零依赖：仅 Python 标准库（可选 Pillow 用于自动压缩超大图片）
- 模型可配置：默认 `qwen-vl-max`，可用环境变量切换 `qwen-vl-plus` 等

## 前置要求 / Prerequisites

- Python 3.8+
- 阿里云百炼（DashScope）API Key：登录 [百炼控制台](https://bailian.console.aliyun.com) 创建 `sk-...` 密钥
- 支持 MCP 的客户端（Codex / Claude Code / Cursor 等）

## 安装 / Installation

### Codex CLI

```bash
codex mcp add qwen-vision \
  --env DASHSCOPE_API_KEY=sk-你的Key \
  -- python server.py
```

然后重启 Codex（新会话生效）。

### 手动配置（任何 MCP 客户端）

`~/.codex/config.toml` 示例：

```toml
[mcp_servers.qwen-vision]
command = "python"
args = ["/path/to/server.py"]

[mcp_servers.qwen-vision.env]
DASHSCOPE_API_KEY = "sk-你的Key"
```

Claude Code 的 `.mcp.json` 示例：

```json
{
  "mcpServers": {
    "qwen-vision": {
      "command": "python",
      "args": ["/path/to/server.py"],
      "env": { "DASHSCOPE_API_KEY": "sk-你的Key" }
    }
  }
}
```

## 使用 / Usage

配置完成后，直接对客户端说：

> 看一下这张图：`/path/to/image.png`（它会在需要时自动调用 `describe_image`）
> 提取这张截图里的文字：`ocr_image("/path/to/screenshot.png")`

## 配置项 / Configuration

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `DASHSCOPE_API_KEY` | （必填） | 阿里云百炼 API Key |
| `QWEN_VL_MODEL` | `qwen-vl-max` | 视觉模型名（如 `qwen-vl-plus`） |
| `QWEN_VL_TIMEOUT` | `120` | API 请求超时秒数 |

## 测试 / Test

无需 API Key 的协议冒烟测试：

```bash
python scripts/smoke_test.py
```

## License

MIT
