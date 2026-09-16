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
