# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Commands

### Frontend (GeoMine3D/)
```bash
npm run dev          # Start Vite dev server at localhost:5173
npm run build        # vue-tsc -b && vite build
npm run preview      # Preview production build
```

### Backend (backend/)
```bash
pip install -r requirements.txt
docker compose up -d mysql
alembic upgrade head
python scripts/import_server_data.py
uvicorn app.main:app --reload --port 8000
```

Backend tests use `pytest`. No frontend test or lint tooling is configured (no vitest/jest, no eslint/prettier).

## Project Structure

```
GeoMine3D/                  # Frontend: Vue3 + TS + Vite + Three.js + ECharts
├── src/
│   ├── api/                # workspace.ts — single Axios module for FastAPI /api/v1
│   ├── components/
│   │   ├── three/          # SceneCanvas and Three.js container components
│   │   └── workspace/      # Workbench panels: ResourceExplorer, InspectorPanel, PropertyPanel, AnalysisDock, BoreholeChart
│   ├── views/              # ProjectCenterView.vue (/projects), GeoWorkspaceView.vue (/workspace/:projectId)
│   ├── three/              # Three.js engine
│   │   ├── core/           # SceneManager, CameraManager, RenderManager
│   │   ├── loaders/        # GLTF loader with progress
│   │   ├── managers/       # ModelManager, LayerManager, HighlightManager, SelectionManager
│   │   └── tools/          # ClipTool, MeasureTool, AnnotationTool, StratumExplodeTool, etc.
│   ├── stores/             # 3 Pinia stores: scene, borehole, workspace (+ index)
│   ├── router/index.ts     # 2 routes + redirect / → /projects
│   └── types/              # TS interfaces (borehole, model, scene)
├── vite.config.ts          # Proxy /api /static /data → http://127.0.0.1:8000
└── tsconfig*.json          # @/* alias → ./src/*

backend/                    # Backend: FastAPI + SQLAlchemy + MySQL
├── app/                    # API, services, repositories, models and schemas
├── alembic/                # Database migrations
├── mcp_server.py           # 远程调试 MCP 服务（stdio）：把浏览器 __geomine 桥暴露为 MCP 工具
├── scripts/                # Data import helpers
└── tests/                  # Backend tests

server/                     # Preserved legacy data service and source assets (do not modify)
├── data/                   # JSON/Excel/SHP/TIFF business data files
└── static/models/          # .glb model files
```

## Architecture

- **No authentication** or user system.
- Business metadata is persisted in MySQL through SQLAlchemy; source data is imported from `server/data/` and model files remain in `server/static/models/`.
- The primary frontend is the project center (`/projects`) and the `/workspace/:projectId` visualization workbench.
- **Drag-and-drop** .glb files onto scene to load models.
- FastAPI success payloads are wrapped as `{data}` (list endpoints add `meta`); errors return `{code, message, details, requestId}`. OpenAPI docs at `/docs`.
- 原始交付包静态目录：`backend/app/main.py` 将 `server/static/models` 挂载在 `/static/models`，
  前端可直接取 `catalog` 资产与大体积固定数据集（如沉陷位移场 `/static/models/settlement/`）；
  模型详情/版本下载仍走 `/api/v1/models/{id}/file`。
- 远程调试 MCP：`backend/mcp_server.py`（stdio）把浏览器 `window.__geomine` 桥暴露为 29 个
  MCP 工具，链路 MCP → `POST /api/v1/remote/invoke` → WS `/api/v1/remote/ws` → 浏览器
  `remoteBridgeClient.ts`。门控：开发环境默认启用，生产需页面 URL 带 `?remote=1`（`run_js`
  仅 `?remote=1` 时放行）；总开关 `settings.remote_debug_enabled`。详见
  `docs/远程调试MCP指南.md`。注意 `mcp` 依赖固定在 1.x（2.x 强制 starlette>=1，会破坏 fastapi 0.116）。
- 钻孔建模引擎（移植自毕业论文细层化管线）：`backend/modeling_engine/` 把“14层汇总长表 +
  钻孔位置表”全自动建成三维地质模型交付包。链路：前端项目中心“上传钻孔建模” →
  `POST /api/v1/modeling-jobs`（202）→ 建独立项目 + `modeling_jobs` 行 → 子进程
  `python -m modeling_engine.generate`（同一 venv，共享趋势+ARD GP 插值 → 保序投影/尖灭折叠
  → TIN-GTP 建模 → GLB/LOD/VTU/z20 + catalog.json，约 25s）→ 注册进库
  （模型 `storage_scope="upload"`、`metadata.source="modeling"`；钻孔分层颜色按层名映射；
  `origin_restore` 写回 project）。产物在 `uploads/projects/<project_id>/web_package/`，
  任务输入/日志在 `uploads/modeling-jobs/<job_id>/`，删项目时一并清理。
  层序由上传表的层顶深度自动推导（不再需要 strat_order_refined.json）；网格规模由数据决定
  （锦界 182 孔 → 16641 节点）；不含 roadways/working_faces/沉陷场（锦界专属）。
  `import_server_data.py` 重跑时按 `metadata.source=="modeling"` 跳过建模资产、按“项目含建模
  内容则不劫持”匹配同名项目。E2E 冒烟：`backend/scripts/smoke_modeling_job.py`。

## Key Conventions

- Path alias `@/*` maps to `./src/*` in both Vite and tsconfig.
- `noUnusedLocals`/`noUnusedParameters` are disabled. ECharts types: use `Record<string, any>`.
- Borehole strata Excel has two column dialects (both headers read 深度/厚度); `detect_strata_convention` picks per file:
  - `bottom_thickness` (旧表 `地层汇总.xlsx`): 深度 = bottom depth, 厚度 = thickness → topDepth = 深度 - 厚度.
  - `top_bottom` (当前表 `地层汇总14层.xlsx`): 深度 = top depth, 厚度 column actually stores bottom depth → thickness = 厚度 - 深度.
- Only boreholes present in the strata table are imported/displayed; coordinates-only holes (in `钻孔位置.xlsx` but not in the strata table) are skipped and removed on re-import.
- 3D boreholes are drawn per layer with the same colors as the chart/table (`borehole_segments.color`); `BoreholeModelLoader` merges one hole's layers into a single `InstancedMesh` (unit cylinder + per-instance matrix/`instanceColor`, zero-thickness layers get no geometry). One `Object3D` per borehole is preserved so pick/remove/visibility/group-opacity keep working.
- Location coordinates (columns: name/x/y/z) are Gauss-Kruger, normalized (project origin subtracted) for Three.js:
  - three_x = geo_x - cx, three_y = geo_z - cz (elevation → up), three_z = geo_y - cy
- Camera far clip: 500000; initial: (0, 6000, 9000); controls max distance: 200000.

## Data Files

| File | Location |
|------|----------|
| Model package catalog | `server/static/models/web_package/catalog.json` |
| Working face data | `server/data/workingfaces.json` |
| Borehole strata (active) | `server/data/boreholes/地层汇总14层.xlsx`（182 孔 × 14 层，列语义 深度=层顶/厚度=层底，路径由 `settings.borehole_strata_file` 指定） |
| Borehole strata (legacy) | `server/data/boreholes/地层汇总.旧表-已停用.xlsx.bak`（旧表，已停用；列语义 深度=层底/厚度=层厚） |
| Borehole coordinates | `server/data/location/钻孔位置.xlsx`（210 孔，其中 28 孔无分层，导入时跳过） |
| .glb models | `server/static/models/web_package/`（L01–L10 分层、model_combined、roadways、working_faces） |
| 沉陷位移场 | `server/static/models/settlement/`（vertex_offsets.bin/.index.json，前端单模型变形用） |

Models are registered from `web_package/catalog.json` (no static-directory scan); the project origin and vertical scale (20×) come from the catalog `origin_restore`, so boreholes and models share one datum.
