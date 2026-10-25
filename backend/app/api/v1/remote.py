"""远程调试中继：浏览器桥 ↔ MCP 服务之间的命令转发。

链路：Agent → MCP 服务(stdio, backend/mcp_server.py) → 本模块 HTTP /invoke
→ WebSocket → 浏览器页面 remoteBridgeClient → window.__geomine → 结果原路返回。

浏览器侧连接地址：/api/v1/remote/ws?projectId=<id>，由
GeoMine3D/src/three/core/remoteBridgeClient.ts 在远程控制桥启用时接入。
一个浏览器标签页 = 一个会话；命令按 (project_id, session_id) 定位目标会话。
"""

import asyncio
import secrets
import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.schemas.common import DataResponse


router = APIRouter()
logger = get_logger("app.remote")

DEFAULT_TIMEOUT_S = 15.0
MAX_TIMEOUT_S = 120.0


class BrowserSession:
    """一个已接入的浏览器工作台（一个标签页一个会话）。

    invoke() 负责命令下发与等待回包；消息循环在 session_loop 里，
    收到 {"type":"result","id":...} 后唤醒对应的 Future。
    """

    def __init__(self, websocket: Any, project_id: str) -> None:
        self.id = secrets.token_hex(4)
        self.project_id = project_id
        self.websocket = websocket
        self.connected_at = time.time()
        self.last_seen_at = self.connected_at
        self._send_lock = asyncio.Lock()
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "projectId": self.project_id,
            "connectedAt": self.connected_at,
            "lastSeenAt": self.last_seen_at,
            "pending": len(self._pending),
        }

    async def send(self, payload: dict[str, Any]) -> None:
        async with self._send_lock:
            await self.websocket.send_json(payload)

    async def invoke(self, command: str, args: list[Any], timeout_s: float) -> Any:
        invoke_id = secrets.token_hex(8)
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._pending[invoke_id] = future
        try:
            await self.send({"type": "invoke", "id": invoke_id, "command": command, "args": args})
            payload = await asyncio.wait_for(future, timeout_s)
        except asyncio.TimeoutError:
            raise AppError(
                "REMOTE_TIMEOUT",
                f"浏览器 {timeout_s:.0f}s 内未返回命令 {command} 的结果（页面可能已关闭或命令卡住）",
                status_code=504,
            )
        except ConnectionError:
            raise AppError("REMOTE_SESSION_CLOSED", "浏览器会话已断开", status_code=502)
        finally:
            self._pending.pop(invoke_id, None)

        if not payload.get("ok"):
            error = payload.get("error") or {}
            raise AppError(
                "REMOTE_COMMAND_FAILED",
                str(error.get("message") or f"浏览器执行 {command} 失败"),
                status_code=502,
                details={"command": command, "error": error},
            )
        return payload.get("result")

    def resolve(self, message: dict[str, Any]) -> None:
        future = self._pending.get(str(message.get("id") or ""))
        if future is not None and not future.done():
            future.set_result(message)

    def fail_all(self, reason: str) -> None:
        for future in self._pending.values():
            if not future.done():
                future.set_exception(ConnectionError(reason))
        self._pending.clear()


class SessionRegistry:
    def __init__(self) -> None:
        self._sessions: dict[str, BrowserSession] = {}

    def register(self, websocket: Any, project_id: str) -> BrowserSession:
        session = BrowserSession(websocket, project_id)
        self._sessions[session.id] = session
        return session

    def remove(self, session: BrowserSession) -> None:
        self._sessions.pop(session.id, None)

    def list(self) -> list[BrowserSession]:
        return list(self._sessions.values())

    def pick(self, project_id: str | None, session_id: str | None) -> BrowserSession:
        """按 sessionId > projectId > 唯一会话的优先级选定目标。"""

        available = [s.summary() for s in self._sessions.values()]
        if session_id:
            session = self._sessions.get(session_id)
            if session is None:
                raise AppError(
                    "REMOTE_SESSION_NOT_FOUND",
                    f"会话 {session_id} 不在线",
                    status_code=404,
                    details={"available": available},
                )
            if project_id and session.project_id != project_id:
                raise AppError(
                    "REMOTE_SESSION_MISMATCH",
                    f"会话 {session_id} 属于项目 {session.project_id}，而非 {project_id}",
                    status_code=409,
                )
            return session

        sessions = self.list()
        if project_id:
            sessions = [s for s in sessions if s.project_id == project_id]
        if not sessions:
            raise AppError(
                "REMOTE_SESSION_NOT_FOUND",
                "当前没有在线的浏览器会话。请先打开工作台页面并启用远程桥："
                "/workspace/<projectId>?remote=1（开发环境不带参数也可）",
                status_code=404,
                details={"available": available},
            )
        if len(sessions) > 1 and not project_id:
            raise AppError(
                "REMOTE_SESSION_AMBIGUOUS",
                "有多个在线会话，请指定 project_id 或 session_id",
                status_code=409,
                details={"available": available},
            )
        return sessions[0]


registry = SessionRegistry()


async def session_loop(session: BrowserSession, registry: SessionRegistry) -> None:
    """读取浏览器消息并分发；断开后清理会话并失败所有等待中的命令。"""

    try:
        while True:
            try:
                message = await session.websocket.receive_json()
            except ValueError:
                logger.debug("忽略非 JSON 消息 session=%s", session.id)
                continue
            session.last_seen_at = time.time()
            mtype = message.get("type")
            if mtype == "result":
                session.resolve(message)
            elif mtype == "ping":
                await session.send({"type": "pong", "time": time.time()})
            else:
                logger.debug("忽略未知消息 type=%s session=%s", mtype, session.id)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        registry.remove(session)
        session.fail_all("浏览器会话已断开")
        logger.info("浏览器会话断开 session=%s project=%s", session.id, session.project_id)


def ensure_remote_enabled() -> None:
    if not settings.remote_debug_enabled:
        raise AppError("REMOTE_DEBUG_DISABLED", "远程调试已在后端配置中关闭", status_code=403)


class InvokeRequest(BaseModel):
    command: str = Field(min_length=1, description="__geomine 上的方法名（白名单内）")
    args: list[Any] = Field(default_factory=list, description="位置参数列表，逐个传给方法")
    project_id: str | None = Field(default=None, description="目标项目 id（会话注册时携带）")
    session_id: str | None = Field(default=None, description="明确指定会话时使用")
    timeout_s: float = Field(default=DEFAULT_TIMEOUT_S, gt=0, le=MAX_TIMEOUT_S)


class InvokeResponse(BaseModel):
    ok: bool
    result: Any = None


@router.post("/remote/invoke", response_model=InvokeResponse)
async def remote_invoke(request: InvokeRequest) -> InvokeResponse:
    ensure_remote_enabled()
    session = registry.pick(request.project_id, request.session_id)
    result = await session.invoke(request.command, request.args, request.timeout_s)
    return InvokeResponse(ok=True, result=result)


@router.get("/remote/sessions", response_model=DataResponse[list[dict[str, Any]]])
async def list_remote_sessions() -> DataResponse[list[dict[str, Any]]]:
    ensure_remote_enabled()
    return DataResponse(data=[s.summary() for s in registry.list()])


@router.websocket("/remote/ws")
async def remote_ws(websocket: WebSocket, projectId: str = "default") -> None:
    if not settings.remote_debug_enabled:
        await websocket.close(code=1008, reason="remote debug disabled")
        return
    await websocket.accept()
    session = registry.register(websocket, projectId)
    logger.info("浏览器会话接入 session=%s project=%s", session.id, session.project_id)
    try:
        await session.send({"type": "hello", "sessionId": session.id, "projectId": session.project_id})
        await session_loop(session, registry)
    except Exception:
        registry.remove(session)
        session.fail_all("中继异常")
        raise
