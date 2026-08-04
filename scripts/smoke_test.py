#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MCP 协议冒烟测试：验证 initialize 与 tools/list，无需 API Key。"""

import json
import os
import subprocess
import sys

SERVER = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server.py"))

def main():
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "smoke-test", "version": "0.0.0"},
            },
        },
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ]
    payload = "\n".join(json.dumps(m, ensure_ascii=False) for m in messages) + "\n"
    proc = subprocess.run(
        [sys.executable, SERVER],
        input=payload,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        print("server crashed:", proc.stderr)
        sys.exit(1)
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    if len(lines) != 2:
        print("expected 2 responses, got %d" % len(lines))
        sys.exit(1)
    init = json.loads(lines[0])
    listing = json.loads(lines[1])
    assert init["result"]["serverInfo"]["name"] == "qwen-vision", init
    tools = [tool["name"] for tool in listing["result"]["tools"]]
    assert "describe_image" in tools and "ocr_image" in tools, tools
    print("smoke test passed. tools:", ", ".join(tools))

if __name__ == "__main__":
    main()
