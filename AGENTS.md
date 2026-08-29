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
- FastAPI responses use the unified format `{code, message, data}` and expose OpenAPI docs at `/docs`.

## Key Conventions

- Path alias `@/*` maps to `./src/*` in both Vite and tsconfig.
- `noUnusedLocals`/`noUnusedParameters` are disabled. ECharts types: use `Record<string, any>`.
- Borehole Excel "深度" = bottom depth; "厚度" = thickness. topDepth = depth - thickness.
- Location coordinates (columns: name/x/y/z) are Gauss-Kruger, normalized (project origin subtracted) for Three.js:
  - three_x = geo_x - cx, three_y = geo_z - cz (elevation → up), three_z = geo_y - cy
- Camera far clip: 500000; initial: (0, 6000, 9000); controls max distance: 200000.

## Data Files

| File | Location |
|------|----------|
| Model metadata | `server/data/models_meta.json` |
| Working face data | `server/data/workingfaces.json` |
| Borehole strata | `server/data/boreholes/*.xlsx` |
| Borehole coordinates | `server/data/location/钻孔位置.xlsx` |
| .glb models | `server/static/models/` |
