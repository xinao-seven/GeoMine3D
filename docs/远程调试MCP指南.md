# 远程调试 MCP 指南

让支持 MCP 的 AI Agent（ZCode / Claude / Codex 等）远程调试浏览器里的三维工作台：
查场景、摆相机、调地层、剖切/炸开、沉陷对比、读渲染统计与页面控制台日志，
并把当前画面**截图带回给模型"看"**。

## 架构与链路

```
Agent (ZCode / Claude 等)
   │  stdio（MCP 协议）
   ▼
backend/mcp_server.py（Agent 宿主按需拉起，无需常驻）
   │  HTTP POST /api/v1/remote/invoke
   ▼
FastAPI 中继（backend/app/api/v1/remote.py）
   │  WebSocket /api/v1/remote/ws?projectId=<id>
   ▼
浏览器工作台 remoteBridgeClient.ts → window.__geomine → 场景引擎
   └────────── 结果 / 截图 PNG 原路返回 ──────────┘
```

- 一个浏览器标签页 = 一个会话，按 `projectId` 注册；多个标签页时工具需指定目标。
- 命令按白名单分发：仅 `__geomine` 上暴露的方法；`handles`（引擎原始句柄）永不外泄。
- 门控沿用远程控制桥：**开发环境默认启用，生产构建需页面 URL 显式带 `?remote=1`**。
  `run_js` 逃生舱更严：仅当 URL 显式带 `?remote=1` 时浏览器侧才放行。
- 后端总开关：`settings.remote_debug_enabled`（默认 true，`.env` 可关）。

## 使用步骤

1. 启动后端：`uvicorn app.main:app --reload --port 8000`
2. 打开工作台：`http://localhost:5173/workspace/<projectId>`
   （开发环境即可；生产构建加 `?remote=1`）
3. 在 Agent 宿主里注册 MCP 服务（见下），工具即出现（`mcp__geomine__*`）。
4. 调试前先调 `list_sessions` 确认浏览器在线。

## Agent 宿主配置

通用 mcpServers JSON（ZCode / Claude Desktop / Cline 等）：

```json
{
  "mcpServers": {
    "geomine": {
      "command": "E:/code/GeoMine3D/backend/.venv/Scripts/python.exe",
      "args": ["E:/code/GeoMine3D/backend/mcp_server.py"],
      "env": {
        "GEOMINE_API_BASE": "http://127.0.0.1:8000",
        "GEOMINE_PROJECT": "default"
      }
    }
  }
}
```

或 Claude Code CLI：

```bash
claude mcp add geomine --env GEOMINE_API_BASE=http://127.0.0.1:8000 \
  -- E:/code/GeoMine3D/backend/.venv/Scripts/python.exe E:/code/GeoMine3D/backend/mcp_server.py
```

环境变量：

| 变量 | 默认 | 说明 |
|------|------|------|
| `GEOMINE_API_BASE` | `http://127.0.0.1:8000` | 后端地址 |
| `GEOMINE_PROJECT` | 空 | 默认 projectId；不设时工具的 `project` 参数留空即自动选定唯一在线会话 |

## 工具清单（29 个）

| 类别 | 工具 | 对应 `__geomine` |
|------|------|------------------|
| 会话 | `list_sessions` | —（中继 /remote/sessions） |
| 感知 | `scene_info` / `list_strata` | `info` / `listStrata` |
| 相机 | `set_view` / `get_view` / `set_camera` / `fit_view` | `setView` / `getView` / `setCamera` / `fitView` |
| 画面 | `capture_screenshot`（返回 PNG 图像） | `capture` |
| 渲染 | `set_background` / `set_exposure` | `setBackground` / `setExposure` |
| 地层 | `set_strata_style`（颜色/透明度/显隐合一）/ `set_strata_colors` | `setStratumColor` 等 |
| 图层 | `set_layer_visible` / `set_group_opacity` / `set_show_edges` / `set_vertical_scale` | 同名方法 |
| 剖切/炸开 | `enable_clip` / `disable_clip` / `set_explode` | `enableClip` 等 |
| 选择 | `select_layer` / `clear_selection` / `project_layer` | `selectByLayer` 等 |
| 沉陷 | `settlement_enable` / `settlement_set` / `settlement_info` | `settlement.*` |
| 调试 | `get_render_stats` / `get_console_logs` / `clear_console_logs` | `renderStats` 等（前端遥测采集） |
| 逃生舱 | `run_js`（仅 `?remote=1` 时放行） | `eval` |

典型调试流程：`scene_info` 摸清场景 → `set_view`/`fit_view` 摆机位 →
`capture_screenshot` 看画面 → `list_strata` + `set_strata_style` 调整 →
`enable_clip`/`set_explode` 检查内部 → `get_console_logs`/`get_render_stats` 排查页面问题。

## 错误语义

- 无在线会话 → `[REMOTE_SESSION_NOT_FOUND]`（404），提示先打开工作台。
- 浏览器执行失败（含 `__geomine` 返回 `{error}`）→ `[REMOTE_COMMAND_FAILED]`（502）。
- 页面超时无响应 → `[REMOTE_TIMEOUT]`（504；默认 15s，截图放宽至 60s）。

## 测试

后端测试覆盖中继往返/超时/断开清理/注册规则与 MCP 工具注册（`pytest`，15 例）。
修改桥或中继后建议手动跑一遍端到端：起后端 + 打开工作台 + 用 Agent 调一次
`scene_info` 和 `capture_screenshot`。

## 安全注意

- 仅用于本地/可信内网调试：中继会把浏览器场景的控制权交给任何能访问后端
  `/api/v1/remote/invoke` 的进程，生产环境请保持 `remote_debug_enabled: false`
  （或不要以 `?remote=1` 打开页面）。
- `run_js` 可在页面执行任意 JS，只在显式 `?remote=1` 时可用，勿在生产使用。
