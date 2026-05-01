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
  <img src="https://img.shields.io/badge/Django-092E20?style=flat-square&logo=django&logoColor=white" alt="Django" />
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
- **前后端分离架构** — Vue 3 前端 + Django REST 后端，接口化数据交互

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
| **Python** + **Django** | Web 框架 |
| **Django REST Framework** | REST API |
| **pandas** + **openpyxl** | Excel 钻孔数据解析 |
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
└── backend/                             # 后端项目
    ├── config/                          # Django 配置
    │   ├── settings.py
    │   └── urls.py
    ├── apps/
    │   ├── common/                      # 统一响应与异常处理
    │   └── geology/                     # 业务模块
    │       ├── urls.py                  # 17 个 REST 接口定义
    │       ├── views.py                 # 视图层
    │       └── services/                # 业务服务层
    │           ├── model_service.py
    │           ├── borehole_excel_service.py
    │           ├── workingface_service.py
    │           └── analysis_service.py
    ├── data/                            # 业务数据文件
    │   ├── boreholes/                   # 钻孔 Excel 数据
    │   ├── location/                    # 钻孔坐标数据
    │   ├── models_meta.json             # 模型元数据
    │   └── workingfaces.json            # 工作面数据
    ├── static/models/                   # .glb 3D 模型文件
    │   ├── strata/
    │   ├── boreholes/
    │   └── workingfaces/
    └── scripts/                         # 工具脚本
        └── create_sample_data.py
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

# （可选）生成示例钻孔 Excel 数据
python scripts/create_sample_data.py

# 启动 Django 开发服务器
python manage.py runserver 8000
```

后端 API 地址：`http://localhost:8000/api/`

### 前端启动

```bash
cd GeoMine3D

# 安装依赖
npm install

# 启动 Vite 开发服务器
npm run dev
```

前端地址：`http://localhost:5173`

> 开发服务器已配置代理，`/api`、`/static`、`/data` 请求自动转发至后端。

### 数据准备

将 `.glb` 模型文件放入 `backend/static/models/` 对应子目录（`strata/`、`boreholes/`、`workingfaces/`），后端会自动扫描并提供元数据接口。钻孔数据使用 `scripts/create_sample_data.py` 生成示例，或按格式自行准备 Excel 文件。

---

## API 概览

所有接口返回统一格式：

```json
{ "code": 0, "message": "success", "data": ... }
```

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/dashboard/summary` | 总览聚合数据 |
| GET | `/api/models` | 模型列表（支持 `type`/`keyword` 筛选） |
| GET | `/api/models/{id}` | 模型详情 |
| GET | `/api/models/{id}/resource` | 模型资源路径 |
| GET | `/api/boreholes` | 钻孔列表（支持 `keyword`/`min_depth`/`max_depth`） |
| GET | `/api/boreholes/{id}` | 钻孔详情（含分层数据） |
| GET | `/api/boreholes/search` | 钻孔搜索 |
| GET | `/api/workingfaces` | 工作面列表（支持 `status` 筛选） |
| GET | `/api/workingfaces/{id}` | 工作面详情 |
| GET | `/api/analysis/thickness-distribution` | 地层厚度分布统计 |
| GET | `/api/analysis/borehole-depth-distribution` | 钻孔深度分布统计 |
| GET | `/api/analysis/workingface-status` | 工作面状态统计 |
| GET | `/api/analysis/borehole-count` | 钻孔数量统计 |
| GET | `/api/analysis/layer-frequency` | 地层频次统计 |
| GET | `/api/analysis/borehole-xy-raw` | 钻孔 XY 散点坐标 |
