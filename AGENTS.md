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
├── scripts/                # Data import helpers（含 preprocess_basemap.py 底图预处理）
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
  渲染网格保留内部三棱柱壁（`LayerResult.render_mesh`，`keep_shared_walls` 把相邻体元共享侧面
  单份保留）：L*.glb/model_combined/z20/lods 用含壁网格，剖切后内部呈柱状实体；`shells/` 存逐层闭合
  壳（surface_mesh）供剖面求交等分析。渲染网格相邻层底面整体下移 `RENDER_INTERFACE_GAP=0.05m`
  抗界面共面闪烁。`build_web_package` 支持 `--z-origin` 显式高程基准（替换既有包时保持对齐）。
  锦界交付包已用本引擎重新生成替换（原包备份 `server/static/models/_backup_web_package_20261026/`）。
- **几何双轨（渲染轨 / 分析轨）**：每个交付包同时含两套几何，注册进库时分别写到
  `metadata.source_file`（渲染轨 `L*.glb`，含内部壁、非水密、渲染端必须 `DoubleSide`）与
  `metadata.shell_file`（分析轨 `shells/L*_shell.glb`，闭合壳），另存 `metadata.lod_urls`
  （逐层 LOD 的公开地址，LOD 自渲染轨减面，上传项目也能用）。下载接口
  `GET /api/v1/models/{id}/file?variant=render|shell`（默认 `render`；旧包无分析轨时 404 而
  不是隐式回退）。剖面/体积/等值线一律读壳（`section_service.resolve_layer_files` 优先
  `metadata.shell_file`）。前端在剖切/炸开/沉陷期间抑制 LOD 切低模（低模内部壁已被减面抹平）。
  既有包重建：`python scripts/rebuild_web_package.py --package <交付包> --npz <曲面npz>
  [--project-id <项目>]`（保持原 `z_origin`，保留 `act_params/source/workings_glb` 等元数据，
  `--project-id` 时同步刷新资产 metadata 与版本 size/hash）。
  合并场景同样双轨：`model_combined.glb`（含壁）与 `model_combined_shell.glb`（壳，约 20MB/包）。
- 工作台资源树对每个带 `metadata.shell_file` 的模型提供两个加载按钮：主按钮=含壁版、
  `空心壳`按钮=闭合壳版（互斥，场景图层名带“（空心壳）”后缀，壳版本不参与 LOD）。
- 分析与出图功能（`/api/v1/projects/{id}/analysis/*`，纯函数在 `app/services/analysis_service.py`）：
  - `overview` 厚度分布/深度分布/地层频率/工作面状态统计（前端 AnalysisDock 场景概览与体积储量页签消费）。
  - `virtual-borehole`(POST) 任意点 IDW 插值虚拟钻孔；`reserves` 工作面 shp 圈闭面积×圈内钻孔
    煤厚×密度估算资源量；`contours?layer=` 顶板埋深等值线（IDW 网格 + Marching Squares，
    返回投影坐标线段）。
  - `section`(POST) 两点剖面线对分层闭合壳（`shells/*_shell.glb`）平面求交
    （`app/services/section_service.py`，numpy 自实现三角面求交 + 环线组装，1mm 法向偏移规避
    网格对齐退化），返回逐层 s-z 折线环；前端勘探线剖面图消费。
  - `boundaries` 读取井田边界/工作面 shp 折线（pyshp，`settings.*_boundary_shp`，mtime 缓存）。
- 三维工作台叠加层与工具（SceneCanvas 工具箱“显示/分析”分组）：矿区边界贴地线框
  （`BoundaryOverlay`，钻孔孔口平均高程为基准面）、地层颜色图例、标注持久化
  （`annotations` 表 API，项目模式自动保存/恢复）、测量/标注单条删除与 CSV 导出、
  虚拟钻孔点击查询、剖面工具（两点定义剖面线 → `ClipTool.setCustomPlane` 任意垂直面裁剪 +
  勘探线剖面图对话框，走廊 ±300m 钻孔投影）、分层体积估算（四面体符号体积/竖向比例）、
  埋深等值线（`ContourOverlay` 按埋深配色）、地层 LOD（`StratumLodController` 按相机距离
  切换 `web_package/lods/*_lod50.glb`，沉陷/炸开时自动抑制；由 catalog `source_file` 推导地址；
  LOD 由闭合壳减面生成、不含内部壁）。地层模型默认不透明（加载透明度 0.95→1.0，透明度仍由
  图层控制）。场景保存/快照：头部按钮 → `scene_configs` API（视角/图层/剖切/炸开序列化）与 PNG 导出；
  状态栏鼠标坐标读数（投影面求交 + 悬停表面点高程）。
  GeoTIFF 底图：`scripts/preprocess_basemap.py` 把 UTM49N DEM 重投影到矿区 GK37 带生成
  `/static/models/basemap/`（jpg+json），前端 `BasemapOverlay` 按元数据铺平面纹理；
  交付包 `server/data/tif/20260211.tif` 实测有效区与矿区不重叠（偏东北约 25km），未生成底图。

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
| .glb models | `server/static/models/web_package/`（L01–L14 分层、model_combined、roadways、working_faces；L*/合并为含内部棱柱壁的渲染网格，shells/ 为逐层闭合壳） |
| 沉陷位移场 | `server/static/models/settlement/`（vertex_offsets.bin/.index.json，前端单模型变形用） |

Models are registered from `web_package/catalog.json` (no static-directory scan); the project origin and vertical scale (20×) come from the catalog `origin_restore`, so boreholes and models share one datum.
