# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
python scripts/create_sample_data.py   # Generate boreholes.xlsx
python manage.py runserver 8000        # Start Django at localhost:8000
```

No test or lint tooling is configured (no vitest/jest, no eslint/prettier, no pytest).

## Project Structure

```
GeoMine3D/                  # Frontend: Vue3 + TS + Vite + Three.js + ECharts
├── src/
│   ├── api/                # Axios API modules (geology, model, upload)
│   ├── components/         # Shared components (charts, panels, three, common)
│   ├── views/              # 6 pages: dashboard, cesium, *-management, analysis
│   ├── three/              # Three.js engine
│   │   ├── core/           # SceneManager, CameraManager, RenderManager
│   │   ├── loaders/        # GLTF loader with progress
│   │   ├── managers/       # ModelManager, LayerManager, BoreholeManager
│   │   └── tools/          # ClipTool, MeasureTool, etc.
│   ├── stores/             # 5 Pinia stores: scene, borehole, analysis, project, index
│   ├── router/index.ts     # 6 routes + redirect / → /dashboard
│   └── types/              # TS interfaces
├── vite.config.ts          # Proxy /api /static /data → localhost:8000
└── tsconfig*.json          # @/* alias → ./src/*

backend/                    # Backend: Django 4.2 + DRF (no auth, no DB for biz data)
├── config/                 # settings.py, urls.py
├── apps/
│   ├── common/             # Unified JSON response + exception handling
│   └── geology/            # Views, URLs, services (model, borehole, workingface, analysis, boundary, geotiff)
├── data/                   # JSON/Excel/SHP/TIFF business data files
├── scripts/                # Helper scripts
└── static/models/          # .glb model files
```

## Architecture

- **No authentication** or user system.
- **No database** for business data — all data comes from JSON/Excel files in `backend/data/`. SQLite exists only for Django internals. Borehole strata Excel files in `backend/data/boreholes/` are auto-scanned.
- **Three.js scene** does NOT auto-load on mount — user clicks "加载场景" button in overlay to trigger `loadSceneData()`.
- **ECharts** on `/analysis` page uses 2x2 grid layout via `useResizeObserver`.
- **Drag-and-drop** .glb files onto scene to load models.
- Backend API returns unified format: `{code, message, data}`. CORS is fully open.

## Key Conventions

- Path alias `@/*` maps to `./src/*` in both Vite and tsconfig.
- `noUnusedLocals`/`noUnusedParameters` are disabled. ECharts types: use `Record<string, any>`.
- Borehole Excel "深度" = bottom depth; "厚度" = thickness. topDepth = depth - thickness.
- Location coordinates (columns: name/x/y/z) are Gauss-Kruger, normalized (centroid subtracted) for Three.js:
  - three_x = geo_x - cx, three_y = geo_z - cz (elevation → up), three_z = geo_y - cy
- Camera far clip: 500000; initial: (0, 6000, 9000); controls max distance: 200000.

## Data Files

| File | Location |
|------|----------|
| Model metadata | `backend/data/models_meta.json` |
| Working face data | `backend/data/workingfaces.json` |
| Borehole strata | `backend/data/boreholes/*.xlsx` (auto-scanned) |
| Borehole coordinates | `backend/data/location/钻孔位置.xlsx` |
| .glb models | `backend/static/models/` |
