"""远程调试中继(app/api/v1/remote.py)的测试。

用 FakeWebSocket 直接驱动 BrowserSession + session_loop 做命令往返/超时/
浏览器侧报错/断开清理的单测；HTTP 端点用 TestClient 验证空会话路径。
"""

import asyncio

import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient

from app.api.v1.remote import (
    AppError,
    BrowserSession,
    SessionRegistry,
    session_loop,
)
from app.main import app


class FakeWebSocket:
    """模拟 starlette WebSocket 的最小接口，供 session_loop 驱动。"""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.incoming: asyncio.Queue = asyncio.Queue()
        self.closed = False

    async def send_json(self, payload: dict) -> None:
        if self.closed:
            raise RuntimeError("connection closed")
        self.sent.append(payload)

    async def receive_json(self) -> dict:
        item = await self.incoming.get()
        if isinstance(item, Exception):
            raise item
        return item


async def wait_for_sent(ws: FakeWebSocket, count: int = 1) -> dict:
    for _ in range(200):
        if len(ws.sent) >= count:
            return ws.sent[count - 1]
        await asyncio.sleep(0.01)
    raise AssertionError(f"等待第 {count} 条下发消息超时")


@pytest.mark.asyncio
async def test_invoke_roundtrip() -> None:
    ws = FakeWebSocket()
    session = BrowserSession(ws, "p1")
    registry = SessionRegistry()
    loop = asyncio.create_task(session_loop(session, registry))

    pending = asyncio.create_task(session.invoke("info", [], timeout_s=5.0))
    message = await wait_for_sent(ws)
    assert message["type"] == "invoke"
    assert message["command"] == "info"
    assert message["args"] == []

    await ws.incoming.put({"type": "result", "id": message["id"], "ok": True, "result": {"models": []}})
    assert await asyncio.wait_for(pending, 2.0) == {"models": []}

    ws.closed = True
    await ws.incoming.put(WebSocketDisconnect())
    await asyncio.wait_for(loop, 2.0)


@pytest.mark.asyncio
async def test_invoke_timeout_raises() -> None:
    ws = FakeWebSocket()
    session = BrowserSession(ws, "p1")
    registry = SessionRegistry()
    loop = asyncio.create_task(session_loop(session, registry))

    with pytest.raises(AppError) as exc_info:
        await session.invoke("capture", [], timeout_s=0.05)
    assert exc_info.value.code == "REMOTE_TIMEOUT"

    ws.closed = True
    await ws.incoming.put(WebSocketDisconnect())
    await asyncio.wait_for(loop, 2.0)


@pytest.mark.asyncio
async def test_invoke_browser_error_surfaces() -> None:
    ws = FakeWebSocket()
    session = BrowserSession(ws, "p1")
    registry = SessionRegistry()
    loop = asyncio.create_task(session_loop(session, registry))

    pending = asyncio.create_task(session.invoke("setView", [{}], timeout_s=5.0))
    message = await wait_for_sent(ws)
    await ws.incoming.put({
        "type": "result",
        "id": message["id"],
        "ok": False,
        "error": {"message": "no models loaded"},
    })

    with pytest.raises(AppError) as exc_info:
        await asyncio.wait_for(pending, 2.0)
    assert exc_info.value.code == "REMOTE_COMMAND_FAILED"
    assert exc_info.value.message == "no models loaded"

    ws.closed = True
    await ws.incoming.put(WebSocketDisconnect())
    await asyncio.wait_for(loop, 2.0)


@pytest.mark.asyncio
async def test_disconnect_fails_pending_invokes() -> None:
    ws = FakeWebSocket()
    registry = SessionRegistry()
    session = registry.register(ws, "p1")
    loop = asyncio.create_task(session_loop(session, registry))

    pending = asyncio.create_task(session.invoke("info", [], timeout_s=5.0))
    await wait_for_sent(ws)

    ws.closed = True
    await ws.incoming.put(WebSocketDisconnect())
    await asyncio.wait_for(loop, 2.0)

    with pytest.raises(AppError) as exc_info:
        await asyncio.wait_for(pending, 2.0)
    assert exc_info.value.code == "REMOTE_SESSION_CLOSED"
    assert registry.list() == []


def test_registry_pick_rules() -> None:
    registry = SessionRegistry()
    with pytest.raises(AppError) as exc_info:
        registry.pick(None, None)
    assert exc_info.value.code == "REMOTE_SESSION_NOT_FOUND"

    first = registry.register(FakeWebSocket(), "p1")
    second = registry.register(FakeWebSocket(), "p2")
    assert registry.pick("p2", None) is second
    assert registry.pick(None, first.id) is first
    with pytest.raises(AppError) as exc_info:
        registry.pick(None, None)
    assert exc_info.value.code == "REMOTE_SESSION_AMBIGUOUS"
    with pytest.raises(AppError) as exc_info:
        registry.pick("p1", second.id)
    assert exc_info.value.code == "REMOTE_SESSION_MISMATCH"


def test_sessions_endpoint_empty() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/remote/sessions")
    assert response.status_code == 200
    assert response.json()["data"] == []


def test_invoke_without_session_returns_404() -> None:
    with TestClient(app) as client:
        response = client.post("/api/v1/remote/invoke", json={"command": "info", "args": []})
    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "REMOTE_SESSION_NOT_FOUND"
    assert "remote=1" in body["message"]
