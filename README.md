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

## 项目介绍

GeoMine3D 是一个面向煤矿行业的**三维地质可视化分析平台原型**，将地质勘探数据以三维形式直观呈现，辅助矿山工程人员对地层结构、钻孔信息和工作面状态进行可视化分析与浏览。

### 项目亮点

- **三维场景交互** — 基于 Three.js 构建完整三维场景，支持地层、钻孔、工作面的模型加载与实时操控
- **钻孔数据驱动** — 通过 Excel 导入钻孔分层数据，自动解析并生成三维钻孔柱状图
- **场景工具集** — 提供剖切、测量、标注、炸开、高亮等多种三维分析工具
- **业务联动分析** — 三维场景与二维图表双向联动，点击地层/钻孔即可查看对应属性与统计数据
- **前后端分离架构** — Vue 3 前端 + FastAPI 后端，使用 SQLAlchemy 和 MySQL 持久化业务数据

### 主要功能

| 功能模块 | 说明 |
|---------|------|
| **三维场景展示** | 加载并展示地层 (strata)、钻孔 (borehole)、工作面 (working face) 的 3D 模型，支持拖拽 `.glb` 文件到场景直接加载 |
| **场景交互控制** | 轨道控制（旋转/平移/缩放）、对象拾取与高亮、相机复位与飞行定位 |
| **图层管理** | 按类型控制显隐与透明度，支持地层子层的单独控制（显隐、颜色、透明度、边线） |
| **三维分析工具** | 剖切工具（X/Y/Z 轴剖切、位置调节）、测量工具（两点距离）、标注工具（文本标签）、地层炸开工具 |
| **钻孔可视化** | 从 Excel 解析钻孔分层数据，生成带地层颜色的三维柱状图，点击查看详情 |
| **统计分析** | 4 种 ECharts 图表（地层厚度分布、钻孔深度分布、钻孔散点分布、地层频次统计），支持点击交互联动 |
| **数据检索定位** | 钻孔/工作面关键字搜索，一键定位到三维场景中的对应位置 |
| **管理页面** | 模型管理、钻孔管理、工作面管理三个数据管理页面，支持筛选、搜索与详情查看 |

---

## 主要技术栈

### 前端

| 技术 | 用途 |
|------|------|
| **Vue 3** (Composition API + `<script setup>`) | UI 框架 |
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
| **Python** + **FastAPI** | Web 框架与 REST API |
| **SQLAlchemy** + **MySQL** | ORM 与业务数据持久化 |
| **Alembic** | 数据库版本迁移 |
| **openpyxl** | Excel 钻孔数据解析 |
| **pyproj** | 地理坐标投影转换 |

---

## 工程结构

```
GeoMine3D/
├── GeoMine3D/                           # 前端项目
│   ├── src/
│   │   ├── api/                         # API 接口层
│   │   │   ├── request.ts               # axios 实例与拦截器
│   │   │   └── modules/                 # 各业务模块接口
│   │   ├── components/
│   │   │   ├── common/                  # MainLayout、PageContainer
│   │   │   ├── panels/                  # 图层面板、属性面板、搜索面板
│   │   │   ├── charts/                  # 钻孔柱状图、统计图表
│   │   │   └── three/                   # 3D 场景画布组件
│   │   ├── views/
│   │   │   ├── dashboard/               # 三维分析主页面
│   │   │   ├── model-management/        # 模型管理
│   │   │   ├── borehole-management/     # 钻孔管理
│   │   │   ├── workingface-management/  # 工作面管理
│   │   │   └── analysis/               # 统计分析
│   │   ├── three/                       # Three.js 引擎模块
│   │   │   ├── core/                    # 场景/相机/渲染器/控制器/灯光
│   │   │   ├── loaders/                 # 模型加载器
│   │   │   ├── managers/                # 模型/图层/高亮/选择管理
│   │   │   └── tools/                   # 剖切/测量/标注/炸开/坐标轴
│   │   ├── stores/                      # Pinia 状态管理
│   │   ├── router/                      # 路由配置
│   │   └── types/                       # TypeScript 类型定义
│   └── package.json
│
├── backend/                             # FastAPI 后端项目
│   ├── app/                             # API、服务、仓储、模型和 Schema
│   ├── alembic/                         # 数据库迁移
│   ├── scripts/import_server_data.py    # 历史数据导入
│   └── tests/                           # 后端测试
└── server/                              # 保留的数据服务与源数据目录
    ├── data/                            # 钻孔、坐标和工作面源数据
    └── static/models/                   # 本地 GLB 模型
```

---

## 快速启动

### 前置准备

- **Node.js** (v18+)
- **Python** (3.10+)
- 推荐使用 Conda 或 venv 创建 Python 虚拟环境

### 后端启动

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 启动 MySQL 并初始化数据库
docker compose up -d mysql
alembic upgrade head

# 导入 server 下的钻孔和模型数据
python scripts/import_server_data.py

# 启动 FastAPI
uvicorn app.main:app --reload --port 8000
```

后端 API 地址：`http://localhost:8000/api/v1/`，接口文档：`http://localhost:8000/docs`

### 前端启动

```bash
cd GeoMine3D

# 安装依赖
npm install

# 启动 Vite 开发服务器
npm run dev
```

前端地址：`http://localhost:5173`

> 开发服务器已配置代理，`/api` 请求转发至 FastAPI；旧数据和静态模型仍由 `server/` 目录提供。

### 数据准备

将 `.glb` 模型文件放入 `server/static/models/`，钻孔源数据放入 `server/data/`，然后执行 `python scripts/import_server_data.py` 将业务元数据同步到 MySQL。

---

## API 概览

所有接口返回统一格式：

```json
{ "code": 0, "message": "success", "data": ... }
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
