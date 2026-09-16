<p align="center">
  <img src="./GeoMine3D/public/icon.svg" width="80" alt="GeoMine3D Logo" />
</p>

<h1 align="center">GeoMine3D</h1>
<p align="center"><strong>矿区三维地质可视化分析平台</strong></p>

<p align="center">
  <img src="https://img.shields.io/badge/Vue_3-4FC08D?style=flat-square&logo=vuedotjs&logoColor=white" alt="Vue 3" />
  <img src="https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript" />
  <img src="https://img.shields.io/badge/Three.js-000000?style=flat-square&logo=threedotjs&logoColor=white" alt="Three.js" />
  <img src="https://img.shields.io/badge/ECharts-AA344D?style=flat-square&logo=apacheecharts&logoColor=white" alt="ECharts" />
  <img src="https://img.shields.io/badge/Element_Plus-409EFF?style=flat-square&logo=element&logoColor=white" alt="Element Plus" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Pinia-FFD859?style=flat-square&logo=pinia&logoColor=black" alt="Pinia" />
  <img src="https://img.shields.io/badge/Vite-646CFF?style=flat-square&logo=vite&logoColor=white" alt="Vite" />
</p>

---

## 目录

- [项目介绍](#项目介绍)
- [主要功能](#主要功能)
- [技术栈](#技术栈)
- [工程结构](#工程结构)
- [快速开始](#快速开始)
- [配置与日志](#配置与日志)
- [API 概览](#api-概览)
- [数据与坐标约定](#数据与坐标约定)
- [相关文档](#相关文档)

---

## 项目介绍

GeoMine3D 是一个面向煤矿行业的**三维地质可视化分析平台原型**，将地质勘探数据以三维形式直观呈现，辅助矿山工程人员对地层结构、钻孔信息和工作面状态进行可视化分析与浏览。

### 项目亮点

- **三维场景交互** — 基于 Three.js 构建完整三维场景，支持地层、钻孔、工作面的模型加载与实时操控
- **钻孔数据驱动** — 通过 Excel 导入钻孔分层数据，自动解析并生成三维钻孔柱状图
- **场景工具集** — 提供剖切、测量、标注、炸开、高亮等多种三维分析工具
- **业务联动分析** — 三维场景与二维图表双向联动，点击地层/钻孔即可查看对应属性与统计数据
- **前后端分离架构** — Vue 3 前端 + FastAPI 后端，使用 SQLAlchemy 和 MySQL 持久化业务数据

---

## 主要功能

| 功能模块 | 说明 |
|---------|------|
| **三维场景展示** | 加载并展示地层 (strata)、钻孔 (borehole)、工作面 (working face) 的 3D 模型，支持拖拽 `.glb` 文件到场景直接加载 |
| **场景交互控制** | 轨道控制（旋转/平移/缩放）、对象拾取与高亮、相机复位与飞行定位 |
| **图层管理** | 按类型控制显隐与透明度，支持地层子层的单独控制（显隐、颜色、透明度、边线） |
| **三维分析工具** | 剖切工具（X/Y/Z 轴剖切、位置调节）、测量工具（两点距离）、标注工具（文本标签）、地层炸开工具、包围盒、坐标轴 |
| **钻孔可视化** | 从 Excel 解析钻孔分层数据，生成带地层颜色的三维柱状图，点击查看详情 |
| **钻孔柱状图分析** | 底部分析 Dock 展示钻孔摘要（总深度、层数等指标）与 ECharts 地层柱状图，自适应尺寸 |
| **项目中心** | 基于 MySQL 持久化的项目与模型资源列表，一键进入对应三维工作台 |
| **沉陷位移场** | 通过静态位移场数据集驱动单模型顶点变形演示 |

---

## 技术栈

### 前端

| 技术 | 用途 |
|------|------|
| **Vue 3**（Composition API + `<script setup>`） | UI 框架 |
| **TypeScript** | 类型安全 |
| **Vite** | 构建工具与开发服务器 |
| **Three.js** + GLTF/DRACOLoader + EffectComposer | 三维场景渲染与后期处理 |
| **ECharts** | 统计图表 |
| **Element Plus** | UI 组件库 |
| **Pinia** | 状态管理 |
| **Vue Router** | 路由管理 |
| **axios** | HTTP 客户端 |

### 后端

| 技术 | 用途 |
|------|------|
| **Python 3.10+** + **FastAPI** | Web 框架与 REST API |
| **SQLAlchemy 2.0** + **MySQL 8** | ORM 与业务数据持久化（异步 asyncmy 驱动） |
| **Alembic** | 数据库版本迁移 |
| **openpyxl** | Excel 钻孔数据解析 |
| **pyproj** | 地理坐标投影转换 |

---

## 工程结构

```
GeoMine3D/
├── GeoMine3D/                           # 前端项目 (Vue 3 + TS + Vite)
│   ├── src/
│   │   ├── api/                         # API 接口层
│   │   │   └── workspace.ts             # FastAPI /api/v1 统一接口模块
│   │   ├── components/
│   │   │   ├── workspace/               # 工作台面板：资源树、属性、检查器、分析 Dock、钻孔图表
│   │   │   └── three/                   # 3D 场景画布组件
│   │   ├── views/
│   │   │   ├── ProjectCenterView.vue    # 项目中心 (/projects)
│   │   │   └── GeoWorkspaceView.vue     # 三维地质工作台 (/workspace/:projectId)
│   │   ├── three/                       # Three.js 引擎模块
│   │   │   ├── core/                    # 场景/相机/渲染器/控制器/灯光
│   │   │   ├── loaders/                 # 模型加载器
│   │   │   ├── managers/                # 模型/图层/高亮/选择管理
│   │   │   └── tools/                   # 剖切/测量/标注/炸开/包围盒/坐标轴
│   │   ├── stores/                      # Pinia 状态管理 (scene / borehole / workspace)
│   │   ├── router/                      # 路由配置
│   │   └── types/                       # TypeScript 类型定义
│   └── vite.config.ts                   # /api /static /data 代理至后端
│
├── backend/                             # FastAPI 后端项目
│   ├── app/
│   │   ├── api/                         # HTTP 路由与依赖注入
│   │   ├── core/                        # 配置、数据库、日志、异常处理
│   │   ├── models/                      # SQLAlchemy 实体
│   │   ├── repositories/                # 查询封装
│   │   ├── schemas/                      # Pydantic 输入输出模型
│   │   ├── services/                    # 业务规则与事务边界
│   │   └── main.py                      # 应用入口、中间件、静态资源挂载
│   ├── alembic/                         # 数据库迁移
│   ├── scripts/import_server_data.py    # 历史数据导入
│   ├── tests/                           # 后端测试 (pytest)
│   ├── docker-compose.yml               # 本地 MySQL
│   └── .env.example                     # 环境变量样例
│
├── server/                              # 保留的交付数据目录（不修改）
│   ├── data/                            # 钻孔、坐标和工作面源数据
│   └── static/models/                   # 本地 GLB 模型与沉陷位移场
│
├── start.sh / start.bat                 # 一键构建前端并在单端口启动服务
├── REFACTOR_ISSUES.md                   # 重构问题记录
└── AGENTS.md / CLAUDE.md                # 协作约定
```

---

## 快速开始

### 前置准备

- **Node.js** v18+
- **Python** 3.10+（推荐 Conda 或 venv 虚拟环境）
- **Docker**（用于启动本地 MySQL 8）

### 方式一：一键启动（推荐）

`start.sh` / `start.bat` 会在 `dist` 缺失时自动构建前端，然后用后端单端口托管整个应用：

```bash
# Git Bash / Linux / macOS
./start.sh          # dist 缺失时自动构建，再启动服务
./start.sh build    # 强制重新构建前端
./start.sh server   # 跳过构建，仅启动服务
```

```bat
REM Windows CMD
start.bat
start.bat build
start.bat server
```

启动后访问：`http://127.0.0.1:8000`（局域网同网段可用打印出的 LAN 地址），接口文档 `http://127.0.0.1:8000/docs`。

### 方式二：前后端分离开发

#### 1. 后端

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 准备环境变量
cp .env.example .env

# 启动 MySQL 并初始化数据库
docker compose up -d mysql
alembic upgrade head

# 导入 server 下的钻孔、地层、工作面与模型元数据
python scripts/import_server_data.py

# 启动 FastAPI
uvicorn app.main:app --reload --port 8000
```

后端 API：`http://localhost:8000/api/v1/`，接口文档：`http://localhost:8000/docs`

#### 2. 前端

```bash
cd GeoMine3D

npm install
npm run dev        # 开发服务器 http://localhost:5173
npm run build      # 类型检查 + 生产构建，产物在 GeoMine3D/dist
npm run preview    # 预览生产构建
```

Vite 已把 `/api`、`/static`、`/data` 代理到 `http://127.0.0.1:8000`（可用 `VITE_BACKEND_URL` 覆盖）。

### 数据准备

- `.glb` 模型放入 `server/static/models/`，钻孔/坐标源数据放入 `server/data/`；
- 执行 `python scripts/import_server_data.py` 将业务元数据同步到 MySQL；
- 模型按 `server/static/models/web_package/catalog.json` 逐层注册，不扫描静态目录；命令可重复执行，业务记录按项目与业务键更新，并新增 `import_runs` 审计记录。

### 运行测试

```bash
cd backend
pytest
```

---

## 配置与日志

### 环境变量

后端配置通过 `backend/.env`（参考 `.env.example`）注入，常用变量：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `APP_ENV` | `development` | 运行环境标识 |
| `DEBUG` | `false` | FastAPI 调试模式（影响异常详情，**不再连带打印 SQL**） |
| `LOG_LEVEL` | `INFO` | 应用日志级别（`DEBUG` / `INFO` / `WARNING` / `ERROR`） |
| `ACCESS_LOG` | `true` | 是否输出 HTTP 访问日志 |
| `DB_ECHO` | `false` | 是否打印 SQLAlchemy 生成的 SQL 语句 |
| `DATABASE_URL` | MySQL asyncmy 连接串 | 数据库连接 |
| `CORS_ORIGINS` | `localhost:5173` | 允许跨域来源（JSON 数组） |
| `SOURCE_DATA_DIR` | `../server/data` | 源数据目录 |
| `SOURCE_MODEL_DIR` | `../server/static/models` | 模型目录 |
| `SOURCE_MODEL_CATALOG` | `.../web_package/catalog.json` | 模型清单 |
| `BOREHOLE_LOCATION_FILE` | `location/钻孔位置.xlsx` | 钻孔坐标表（相对源数据目录） |
| `BOREHOLE_STRATA_FILE` | `boreholes/地层汇总14层.xlsx` | 钻孔分层表 |
| `SERVE_FRONTEND` | `true` | 是否由后端托管前端 `dist` |
| `FRONTEND_DIST_DIR` | `../GeoMine3D/dist` | 前端构建产物目录 |

### 日志规范

日志由 `app/core/logging.py` 统一配置，输出到 **stdout**，格式固定、列对齐，便于检索：

```
2026-09-16 16:54:23 | INFO    | app.access                 | rid=8fcaa177 | GET /health -> 200 0.3ms
```

要点：

- **统一格式** — `时间 | 级别 | logger 名称 | rid | 内容`，级别与 logger 名称定宽对齐；
- **统一出口** — 全部写 stdout，方便容器收集与重定向，不额外写文件；
- **分层命名** — 业务日志按模块走 `app.*`（如 `app.api`、`app.services`），一眼看出来源；
- **请求关联** — 每个请求自动分配 `requestId`（前 8 位写入日志，完整值通过响应头 `X-Request-ID` 返回），可与业务日志串联；
- **SQL 默认关闭** — SQL 语句由 `DB_ECHO` 单独控制，`DEBUG=true` 不再刷屏；开启后 SQL 走 `sqlalchemy.engine` logger；
- **访问日志去重** — 禁用 uvicorn 自带 access 日志，由 `app.access` 输出一行结构化访问日志；API 请求记 `INFO`，静态资源记 `DEBUG`；
- **第三方压噪** — SQLAlchemy、asyncmy、watchfiles、multipart、httpx 等默认仅保留 `WARNING` 及以上。

### 静态资源与缓存

- `/static/models` 由后端托管 `server/static/models`（交付包资产、沉陷位移场等），统一加 `Cache-Control: no-cache`，避免模型/位移场更新后被浏览器启发式缓存；
- 模型文件本体不写入 MySQL，数据库只保存路径、版本、hash、包围盒等元数据：导入的 GLB 留在 `server/static/models`，新上传版本保存在 `backend/uploads/models`。

---

## API 概览

### 响应格式

成功响应统一包裹在 `data` 字段中（列表接口为 `data` + `meta` 分页元信息）：

```json
{ "data": ... }
```

```json
{ "data": [...], "meta": { "page": 1, "page_size": 20, "total": 182 } }
```

失败响应携带业务错误码与请求 ID，便于与日志中的 `rid` 对齐：

```json
{
  "code": "PROJECT_NOT_FOUND",
  "message": "项目不存在",
  "details": null,
  "requestId": "d40841a6429846ada884d7c1fcfcfb2e"
}
```

| 方法 | 路径 | 说明 |
|------|------|------|
| GET / POST | `/api/v1/projects` | 项目列表与创建 |
| GET / PATCH / DELETE | `/api/v1/projects/{project_id}` | 项目详情、更新与删除 |
| GET / POST | `/api/v1/projects/{project_id}/models` | 项目模型列表与创建 |
| GET / PATCH / DELETE | `/api/v1/models/{model_id}` | 模型元数据管理 |
| GET | `/api/v1/models/{model_id}/file` | 获取模型文件 |
| POST | `/api/v1/models/{model_id}/versions` | 上传模型版本 |
| GET / POST | `/api/v1/projects/{project_id}/boreholes` | 钻孔列表与创建 |
| GET / PATCH / DELETE | `/api/v1/boreholes/{borehole_id}` | 钻孔详情与管理 |
| PUT | `/api/v1/boreholes/{borehole_id}/segments` | 替换钻孔分层数据 |
| GET / POST | `/api/v1/projects/{project_id}/scenes` | 场景配置列表与创建 |
| GET / PUT / DELETE | `/api/v1/scenes/{scene_id}` | 场景配置管理 |
| GET | `/api/v1/projects/{project_id}/working-faces` | 工作面列表 |
| GET | `/api/v1/projects/{project_id}/imports` | 数据导入审计记录 |
| GET | `/health` | 健康检查 |

---

## 数据与坐标约定

- 业务元数据持久化在 MySQL；源数据从 `server/data/` 导入，模型文件保留在 `server/static/models/`；
- 钻孔分层 Excel 存在两种列语义，导入时按文件自动判定：
  - `bottom_thickness`（旧表）：深度 = 层底深度，厚度 = 层厚 → `topDepth = 深度 - 厚度`；
  - `top_bottom`（当前表 `地层汇总14层.xlsx`）：深度 = 层顶深度，厚度列实际为层底深度 → `thickness = 厚度 - 深度`；
- 仅在分层表中出现的钻孔会被导入/展示，只有坐标而无分层的孔在重导时跳过并移除；
- 位置坐标为高斯-克吕格，需归一化后供 Three.js 使用（项目原点由 catalog `origin_restore` 提供，20× 垂直缩放）：
  - `three_x = geo_x - cx`，`three_y = geo_z - cz`（高程向上），`three_z = geo_y - cy`；
- 相机远裁剪面 `500000`，初始位置 `(0, 6000, 9000)`，轨道最大距离 `200000`。

---

## 相关文档

| 文档 | 说明 |
|------|------|
| [backend/README.md](./backend/README.md) | 后端目录职责、数据导入与开发说明 |
| [REFACTOR_ISSUES.md](./REFACTOR_ISSUES.md) | 重构期间的问题、决策与处理记录 |
| [AGENTS.md](./AGENTS.md) | 仓库结构与开发约定速查 |
