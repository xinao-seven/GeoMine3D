"""backend/mcp_server.py 的冒烟测试：工具注册与本地逻辑（不走 stdio/网络）。"""

import base64

import httpx
import pytest

import mcp_server


def _patch_http(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    """把 _invoke 的出站 HTTP 指到 MockTransport，隔离真实后端。"""

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs.pop("transport", None)
        return original(transport=transport, **kwargs)

    monkeypatch.setattr(mcp_server.httpx, "AsyncClient", factory)


@pytest.mark.asyncio
async def test_all_tools_registered_with_unique_names() -> None:
    tools = await mcp_server.server.list_tools()
    names = [tool.name for tool in tools]
    assert len(names) == len(set(names))
    assert {
        "list_sessions",
        "scene_info",
        "list_strata",
        "set_view",
        "get_view",
        "set_camera",
        "fit_view",
        "set_background",
        "set_exposure",
        "capture_screenshot",
        "set_strata_style",
        "set_strata_colors",
        "set_layer_visible",
        "set_group_opacity",
        "set_show_edges",
        "set_vertical_scale",
        "enable_clip",
        "disable_clip",
        "set_explode",
        "select_layer",
        "clear_selection",
        "project_layer",
        "settlement_enable",
        "settlement_set",
        "settlement_info",
        "get_render_stats",
        "get_console_logs",
        "clear_console_logs",
        "run_js",
    } <= set(names)


@pytest.mark.asyncio
async def test_every_tool_has_description() -> None:
    tools = await mcp_server.server.list_tools()
    assert all((tool.description or "").strip() for tool in tools)


@pytest.mark.asyncio
async def test_capture_tool_decodes_png(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = b"\x89PNG-fake-bytes"
    data_url = "data:image/png;base64," + base64.b64encode(raw).decode()
    seen: dict = {}

    async def fake_invoke(command: str, args=None, **kwargs):
        seen["command"] = command
        seen["args"] = args
        seen["kwargs"] = kwargs
        return data_url

    monkeypatch.setattr(mcp_server, "_invoke", fake_invoke)
    image = await mcp_server.capture_screenshot(
        project=None, background="#ffffff", pixel_ratio=2, exposure=0, hide_gizmo=True
    )
    assert image.data == raw
    assert seen["command"] == "capture"
    assert seen["args"][0]["background"] == "#ffffff"
    assert seen["args"][0]["pixelRatio"] == 2
    assert seen["kwargs"]["timeout"] > 30


@pytest.mark.asyncio
async def test_invoke_converts_browser_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_http(monkeypatch, lambda request: httpx.Response(
        200, json={"ok": True, "result": {"error": "no models loaded"}}
    ))
    with pytest.raises(RuntimeError, match="no models loaded"):
        await mcp_server._invoke("setView", [{}])


@pytest.mark.asyncio
async def test_invoke_surfaces_relay_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_http(monkeypatch, lambda request: httpx.Response(
        404, json={"code": "REMOTE_SESSION_NOT_FOUND", "message": "当前没有在线的浏览器会话"}
    ))
    with pytest.raises(RuntimeError, match="REMOTE_SESSION_NOT_FOUND"):
        await mcp_server._invoke("info")


@pytest.mark.asyncio
async def test_set_explode_omits_gap_only_when_none(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list] = []

    async def fake_invoke(command: str, args=None, **kwargs):
        calls.append(args or [])
        return {"exploded": True}

    monkeypatch.setattr(mcp_server, "_invoke", fake_invoke)
    await mcp_server.set_explode(project=None, on=True, gap=None)
    await mcp_server.set_explode(project=None, on=True, gap=500)
    assert calls == [[True], [True, 500.0]]
