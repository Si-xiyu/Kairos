from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
import queue
import re
import subprocess
import threading
from pathlib import Path
from typing import Any

from kairos.config import KairosPaths
from kairos.tools.registry import ToolResult, ToolSpec


@dataclass(frozen=True)
class McpServerConfig:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None
    timeout_seconds: float = 10.0


@dataclass(frozen=True)
class McpToolDefinition:
    server: str
    name: str
    description: str
    input_schema: dict[str, Any]
    runtime_name: str


def build_mcp_tool_specs(paths: KairosPaths) -> list[ToolSpec]:
    specs: list[ToolSpec] = []
    for server in load_mcp_servers(paths):
        try:
            tools = list_mcp_tools(paths, server)
        except Exception:
            continue
        for tool in tools:
            specs.append(
                ToolSpec(
                    name=tool.runtime_name,
                    description=f"[MCP:{server.name}] {tool.description or tool.name}",
                    input_schema=tool.input_schema,
                    risk_level="medium",
                    source="mcp",
                    handler=lambda _server=server, _tool=tool, **arguments: call_mcp_tool(
                        paths, _server, _tool.name, arguments
                    ),
                )
            )
    return specs


def load_mcp_servers(paths: KairosPaths) -> list[McpServerConfig]:
    config_path = _mcp_config_path(paths)
    if config_path is None:
        return []
    data = json.loads(config_path.read_text(encoding="utf-8"))
    servers = data.get("servers", {})
    if not isinstance(servers, dict):
        return []
    configs: list[McpServerConfig] = []
    for name, raw in servers.items():
        if not isinstance(raw, dict) or not raw.get("command"):
            continue
        args = raw.get("args", [])
        env = raw.get("env", {})
        configs.append(
            McpServerConfig(
                name=_safe_identifier(str(name)),
                command=str(raw["command"]),
                args=[str(item) for item in args] if isinstance(args, list) else [],
                env={str(key): str(value) for key, value in env.items()} if isinstance(env, dict) else {},
                cwd=str(raw["cwd"]) if raw.get("cwd") else None,
                timeout_seconds=float(raw.get("timeout_seconds", 10.0)),
            )
        )
    return configs


def list_mcp_tools(paths: KairosPaths, server: McpServerConfig) -> list[McpToolDefinition]:
    with _McpSession(paths, server) as session:
        response = session.request("tools/list", {})
    raw_tools = response.get("tools", [])
    if not isinstance(raw_tools, list):
        return []
    tools: list[McpToolDefinition] = []
    for raw in raw_tools:
        if not isinstance(raw, dict) or not raw.get("name"):
            continue
        name = str(raw["name"])
        runtime_name = f"mcp.{server.name}.{_safe_identifier(name)}"
        schema = raw.get("inputSchema", {"type": "object", "properties": {}})
        tools.append(
            McpToolDefinition(
                server=server.name,
                name=name,
                description=str(raw.get("description", "")),
                input_schema=schema if isinstance(schema, dict) else {"type": "object"},
                runtime_name=runtime_name,
            )
        )
    return tools


def call_mcp_tool(
    paths: KairosPaths,
    server: McpServerConfig,
    tool_name: str,
    arguments: dict[str, Any],
) -> ToolResult:
    with _McpSession(paths, server) as session:
        response = session.request(
            "tools/call",
            {"name": tool_name, "arguments": arguments},
        )
    content = response.get("content", [])
    preview = _mcp_preview(content)
    return ToolResult(
        "ok",
        preview,
        {"server": server.name, "tool": tool_name, "response": response},
    )


class _McpSession:
    def __init__(self, paths: KairosPaths, server: McpServerConfig) -> None:
        self.paths = paths
        self.server = server
        self._next_id = 1
        self._lines: queue.Queue[str] = queue.Queue()
        cwd = _resolve_cwd(paths, server.cwd)
        env = os.environ.copy()
        env.update(server.env)
        self.process = subprocess.Popen(
            [server.command, *server.args],
            cwd=str(cwd),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        assert self.process.stdout is not None
        self.reader = threading.Thread(target=self._read_stdout, daemon=True)
        self.reader.start()

    def __enter__(self) -> "_McpSession":
        self.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "kairos", "version": "0.1.0"},
            },
        )
        self.notify("notifications/initialized", {})
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        deadline = self.server.timeout_seconds
        while True:
            try:
                line = self._lines.get(timeout=deadline)
            except queue.Empty as exc:
                raise TimeoutError(f"MCP server timed out during {method}: {self.server.name}") from exc
            message = json.loads(line)
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise RuntimeError(f"MCP {method} failed: {message['error']}")
            result = message.get("result", {})
            return result if isinstance(result, dict) else {"result": result}

    def notify(self, method: str, params: dict[str, Any]) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def _send(self, payload: dict[str, Any]) -> None:
        if self.process.stdin is None:
            raise RuntimeError(f"MCP server stdin is unavailable: {self.server.name}")
        self.process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self.process.stdin.flush()

    def _read_stdout(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            stripped = line.strip()
            if stripped:
                self._lines.put(stripped)


def _mcp_config_path(paths: KairosPaths) -> Path | None:
    candidates = [
        paths.home / "mcp.json",
        paths.root / "mcp.json",
        paths.root / ".mcp.json",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def _resolve_cwd(paths: KairosPaths, raw_cwd: str | None) -> Path:
    if raw_cwd is None:
        return paths.root
    candidate = (paths.root / raw_cwd).resolve()
    if not candidate.is_relative_to(paths.root):
        raise ValueError(f"MCP cwd escapes project root: {raw_cwd}")
    return candidate


def _mcp_preview(content: object) -> str:
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        if parts:
            return "\n".join(parts)[:1000]
    return json.dumps(content, ensure_ascii=False)[:1000]


def _safe_identifier(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    return cleaned or "tool"
