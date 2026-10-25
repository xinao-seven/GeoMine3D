"""GeoMine3D 远程调试 MCP 服务（stdio 传输）。

把浏览器工作台里的 window.__geomine 远程控制桥暴露成 MCP 工具，让支持 MCP 的
AI Agent（ZCode / Claude 等）能够远程调试三维场景：查场景结构、摆相机、调地层
颜色/透明度/显隐、三轴剖切、地层炸开、沉陷对比参数、读渲染统计与页面控制台
日志，并把当前画面截图带回去"看"。

链路：Agent → 本服务(stdio) → FastAPI POST /api/v1/remote/invoke
      → WebSocket /api/v1/remote/ws → 浏览器 remoteBridgeClient → __geomine。

使用前提：后端已启动，且浏览器打开了工作台页面（开发环境默认启用远程桥，
生产构建需 /workspace/<projectId>?remote=1）。可用 list_sessions 工具确认。

环境变量：
    GEOMINE_API_BASE  后端地址，默认 http://127.0.0.1:8000
    GEOMINE_PROJECT   默认 projectId（可选；工具的 project 参数留空时生效）

Agent 宿主配置示例（mcpServers JSON）：
    "geomine": {
        "command": "python",
        "args": ["<仓库>/backend/mcp_server.py"],
        "env": {"GEOMINE_API_BASE": "http://127.0.0.1:8000"}
    }
"""

import base64
import json
import logging
import os
import sys
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP, Image

# stdio 通道只跑协议帧，日志一律走 stderr
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("geomine.mcp")

API_BASE = os.environ.get("GEOMINE_API_BASE", "http://127.0.0.1:8000").rstrip("/")
DEFAULT_PROJECT = (os.environ.get("GEOMINE_PROJECT") or "").strip() or None

server = FastMCP(
    "geomine",
    instructions=(
        "GeoMine3D 三维地质工作台的远程调试工具集。\n"
        "调用前浏览器须已打开工作台并启用远程桥；先用 list_sessions 确认在线会话。\n"
        "典型调试流程：scene_info 摸清场景 → set_view/fit_view 摆机位 → "
        "capture_screenshot 看画面 → list_strata + set_strata_style 调整地层 → "
        "enable_clip / set_explode 检查内部结构 → get_console_logs / get_render_stats 排查页面问题。\n"
        "所有工具的 project 参数留空时使用 GEOMINE_PROJECT；未设置且只有一个在线会话时自动选定。\n"
        "坐标说明：场景 y 轴为高程方向（竖向 20 倍夸张），x/z 为投影平面。"
    ),
)


def _text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


async def _invoke(
    command: str,
    args: list[Any] | None = None,
    *,
    project: str | None = None,
    timeout: float = 15.0,
) -> Any:
    """调后端中继，让浏览器执行一条 __geomine 命令并取回结果。"""

    payload: dict[str, Any] = {"command": command, "args": args or [], "timeout_s": timeout}
    target = (project or "").strip() or DEFAULT_PROJECT
    if target:
        payload["project_id"] = target

    async with httpx.AsyncClient(base_url=API_BASE, timeout=timeout + 15.0) as client:
        response = await client.post("/api/v1/remote/invoke", json=payload)

    if response.status_code >= 400:
        try:
            body = response.json()
        except Exception:
            body = {}
        code = body.get("code") or f"HTTP_{response.status_code}"
        message = body.get("message") or response.text[:300]
        details = body.get("details")
        if details:
            message = f"{message} | details: {_text(details)[:500]}"
        raise RuntimeError(f"[{code}] {message}")

    try:
        result = response.json().get("result")
    except Exception as error:
        raise RuntimeError(f"中继返回解析失败: {error}")

    # __geomine 约定业务失败返回 {"error": "..."}（非异常），在此统一转为工具错误
    if isinstance(result, dict) and set(result.keys()) == {"error"}:
        raise RuntimeError(f"浏览器返回错误: {result['error']}")
    return result


@server.tool(structured_output=False)
async def list_sessions() -> str:
    """列出当前在线的浏览器调试会话（id / projectId / 连接时间）。

    没有会话说明浏览器还没打开工作台页面（或未启用远程桥），后续工具都会失败。
    """
    async with httpx.AsyncClient(base_url=API_BASE, timeout=15.0) as client:
        response = await client.get("/api/v1/remote/sessions")
    if response.status_code >= 400:
        raise RuntimeError(f"查询会话失败: HTTP {response.status_code} {response.text[:200]}")
    return _text(response.json().get("data"))


@server.tool(structured_output=False)
async def scene_info(project: str | None = None) -> str:
    """场景概况：已加载模型列表、地层单元控制项、相机位姿、场景包围盒与坐标原点/竖向倍率。"""
    return _text(await _invoke("info", project=project))


@server.tool(structured_output=False)
async def list_strata(project: str | None = None) -> str:
    """列出所有地层单元控制项：key、层名、显隐、透明度、当前颜色。"""
    return _text(await _invoke("listStrata", project=project))


@server.tool(structured_output=False)
async def set_view(
    project: str | None = None,
    azimuth: float = 45.0,
    elevation: float = 35.0,
    distance_factor: float = 1.15,
    target: list[float] | None = None,
) -> str:
    """按球坐标摆相机并返回最终位姿。

    azimuth：方位角（度，绕竖轴，0=+x 方向）；elevation：仰角（度，0=平视，90=正俯视）；
    distance_factor：相对"适配全场景"距离的倍数（1=刚好框住，>1 拉远）；target：观察点 [x,y,z]，默认场景中心。
    """
    opts: dict[str, Any] = {
        "azimuth": azimuth,
        "elevation": elevation,
        "distanceFactor": distance_factor,
    }
    if target:
        opts["target"] = [float(v) for v in target]
    return _text(await _invoke("setView", [opts], project=project))


@server.tool(structured_output=False)
async def get_view(project: str | None = None) -> str:
    """读取当前相机位置与观察点（可用 set_camera 恢复）。"""
    return _text(await _invoke("getView", project=project))


@server.tool(structured_output=False)
async def set_camera(
    project: str | None = None,
    position: list[float] = [0, 6000, 9000],
    target: list[float] = [0, 0, 0],
) -> str:
    """直接设置相机位置 position 与观察点 target（均为场景坐标 [x,y,z]）。"""
    return _text(await _invoke("setCamera", [[float(v) for v in position], [float(v) for v in target]], project=project))


@server.tool(structured_output=False)
async def fit_view(project: str | None = None, factor: float = 1.0) -> str:
    """适配全场景（保持当前观察方向）；factor>1 更远，<1 更近。"""
    return _text(await _invoke("fitView", [factor], project=project))


@server.tool(structured_output=False)
async def set_background(project: str | None = None, color: str | None = None) -> str:
    """设置场景背景色（hex，如 "#0b1020"）；传 null 恢复默认。"""
    return _text(await _invoke("setBackground", [color], project=project))


@server.tool(structured_output=False)
async def set_exposure(project: str | None = None, value: float = 1.0) -> str:
    """设置色调映射曝光（1 = 默认亮度）。"""
    return _text(await _invoke("setExposure", [value], project=project))


@server.tool()
async def capture_screenshot(
    project: str | None = None,
    background: str | None = None,
    pixel_ratio: float = 1.0,
    exposure: float = 0.0,
    hide_gizmo: bool = True,
) -> Image:
    """渲染当前画面并截图，返回 PNG 图像（可直接"看"）。

    background：临时背景色（如 "#ffffff"），仅本帧生效；pixel_ratio：超采样倍率（1~4）；
    exposure：临时曝光（0=保持当前）；hide_gizmo：隐藏坐标轴小控件让画面干净。
    """
    ratio = min(max(float(pixel_ratio), 1.0), 4.0)
    opts: dict[str, Any] = {"pixelRatio": ratio, "hideGizmo": bool(hide_gizmo)}
    if background:
        opts["background"] = background
    if exposure:
        opts["exposure"] = float(exposure)
    data_url = await _invoke("capture", [opts], project=project, timeout=60.0)
    if not isinstance(data_url, str) or not data_url.startswith("data:image/png;base64,"):
        raise RuntimeError(f"意外的截图返回: {str(data_url)[:200]}")
    return Image(data=base64.b64decode(data_url.split(",", 1)[1]), format="png")


@server.tool(structured_output=False)
async def set_strata_style(
    project: str | None = None,
    match: str = "",
    color: str | None = None,
    opacity: float | None = None,
    visible: bool | None = None,
) -> str:
    """按层名/key 子串匹配（不区分大小写）批量调整地层样式，可同时给 color / opacity / visible。

    例：match="煤" 会命中所有层名含"煤"的地层。返回更新后的地层控制项列表。
    """
    if not match:
        raise RuntimeError("必须提供 match 匹配串")
    results: list[Any] = []
    if color is not None:
        results.append(await _invoke("setStratumColor", [match, color], project=project))
    if opacity is not None:
        results.append(await _invoke("setStratumOpacity", [match, float(opacity)], project=project))
    if visible is not None:
        results.append(await _invoke("setStratumVisible", [match, bool(visible)], project=project))
    updated = await _invoke("listStrata", project=project)
    return _text({"applied": len(results), "strata": updated})


@server.tool(structured_output=False)
async def set_strata_colors(project: str | None = None, colors: dict[str, str] | None = None) -> str:
    """批量设置地层颜色：{层名子串: "#rrggbb"}。返回更新后的地层控制项列表。"""
    if not colors:
        raise RuntimeError("必须提供 colors 映射，如 {\"煤3-1\": \"#333333\"}")
    return _text(await _invoke("setStrataColors", [colors], project=project))


@server.tool(structured_output=False)
async def set_layer_visible(project: str | None = None, layer_type: str = "stratum", visible: bool = True) -> str:
    """一级图层显隐。layer_type ∈ stratum(地层) | borehole(钻孔) | workingface(工作面) | roadway(巷道)。"""
    return _text(await _invoke("setLayerVisible", [layer_type, bool(visible)], project=project))


@server.tool(structured_output=False)
async def set_group_opacity(project: str | None = None, layer_type: str = "stratum", value: float = 1.0) -> str:
    """一级图层整体透明度系数（0.05~1）。layer_type 同 set_layer_visible。"""
    return _text(await _invoke("setGroupOpacity", [layer_type, float(value)], project=project))


@server.tool(structured_output=False)
async def set_show_edges(project: str | None = None, visible: bool = True) -> str:
    """地层边缘线显隐。"""
    return _text(await _invoke("setShowEdges", [bool(visible)], project=project))


@server.tool(structured_output=False)
async def set_vertical_scale(project: str | None = None, value: float = 20.0) -> str:
    """全场景竖向夸张倍数（项目基准值见 scene_info 的 verticalScale，默认 20）。"""
    return _text(await _invoke("setVerticalScale", [float(value)], project=project))


@server.tool(structured_output=False)
async def enable_clip(
    project: str | None = None,
    axis: str = "x",
    position: float = 0.0,
    keep_lower: bool = True,
) -> str:
    """启用三轴剖切。axis ∈ x|y|z；position 为剖切面位置（场景局部坐标，y 为夸张后高程）；
    keep_lower=true 保留低侧。配合 capture_screenshot 检查地层内部。"""
    return _text(await _invoke("enableClip", [{"axis": axis, "position": float(position), "keepLower": bool(keep_lower)}], project=project))


@server.tool(structured_output=False)
async def disable_clip(project: str | None = None) -> str:
    """关闭剖切工具。"""
    return _text(await _invoke("disableClip", project=project))


@server.tool(structured_output=False)
async def set_explode(project: str | None = None, on: bool = True, gap: float | None = None) -> str:
    """地层炸开。on=true 炸开 / false 复位；gap 为层间距（世界显示单位，默认保持当前值）。"""
    args = [bool(on)] if gap is None else [bool(on), float(gap)]
    return _text(await _invoke("setExplode", args, project=project))


@server.tool(structured_output=False)
async def select_layer(project: str | None = None, match: str = "") -> str:
    """按层名/key 子串选中一个地层（属性检查器 + 描边高亮）。"""
    if not match:
        raise RuntimeError("必须提供 match 匹配串")
    return _text(await _invoke("selectByLayer", [match], project=project))


@server.tool(structured_output=False)
async def clear_selection(project: str | None = None) -> str:
    """清除当前选中与描边高亮。"""
    return _text(await _invoke("clearSelection", project=project))


@server.tool(structured_output=False)
async def project_layer(project: str | None = None, match: str = "") -> str:
    """求某地层包围盒中心的屏幕坐标与世界坐标（配合外部像素级点击/校验）。"""
    if not match:
        raise RuntimeError("必须提供 match 匹配串")
    result = await _invoke("projectLayer", [match], project=project)
    if result is None:
        return _text({"error": f"未找到匹配地层: {match}"})
    return _text(result)


@server.tool(structured_output=False)
async def settlement_enable(project: str | None = None, on: bool = True) -> str:
    """开关沉陷位移场对比（首次启用会加载位移场数据，稍等片刻再截图）。"""
    return _text(await _invoke("settlement.enable", [bool(on)], project=project))


@server.tool(structured_output=False)
async def settlement_set(
    project: str | None = None,
    time: float | None = None,
    exaggeration: float | None = None,
    color_mode: str | None = None,
) -> str:
    """调整沉陷对比参数。

    time：变形进程 0=沉陷前 ~ 1=沉陷后；exaggeration：位移显示夸大倍数；
    color_mode ∈ original(原色) | dz(垂移着色) | magnitude(位移量着色)。
    """
    opts: dict[str, Any] = {}
    if time is not None:
        opts["time"] = float(time)
    if exaggeration is not None:
        opts["exaggeration"] = float(exaggeration)
    if color_mode:
        opts["colorMode"] = color_mode
    return _text(await _invoke("settlement.set", [opts], project=project))


@server.tool(structured_output=False)
async def settlement_info(project: str | None = None) -> str:
    """读取沉陷对比状态：启停、进程、夸大倍数、着色模式、最大沉降/水平位移、绑定情况与加载错误。"""
    return _text(await _invoke("settlement.info", project=project))


@server.tool(structured_output=False)
async def get_render_stats(project: str | None = None) -> str:
    """读取渲染统计：draw calls、三角面数、几何/纹理数量、程序数、视口尺寸与 FPS。"""
    return _text(await _invoke("renderStats", project=project))


@server.tool(structured_output=False)
async def get_console_logs(
    project: str | None = None,
    level: str = "all",
    limit: int = 200,
) -> str:
    """读取页面控制台日志（含未捕获异常与 Promise 拒绝），按时间正序返回。

    level ∈ all | log | info | warn | error；limit 最多 500。
    """
    return _text(await _invoke("getConsoleLogs", [level, int(limit)], project=project))


@server.tool(structured_output=False)
async def clear_console_logs(project: str | None = None) -> str:
    """清空页面控制台日志缓冲（便于复现问题后只看新日志）。"""
    return _text(await _invoke("clearConsoleLogs", project=project))


@server.tool(structured_output=False)
async def run_js(project: str | None = None, expression: str = "") -> str:
    """调试逃生舱：在浏览器页面执行任意 JS 并返回结果（JSON 序列化）。

    仅当页面 URL 显式带 ?remote=1 时浏览器侧才允许执行；可访问 __geomine、
    Three.js 场景句柄（__geomine.handles）等。仅用于调试，勿在生产使用。
    """
    if not expression:
        raise RuntimeError("必须提供 expression")
    return _text(await _invoke("eval", [expression], project=project))


def main() -> None:
    logger.info("GeoMine3D MCP 服务启动 api_base=%s default_project=%s", API_BASE, DEFAULT_PROJECT or "-")
    server.run("stdio")


if __name__ == "__main__":
    main()
