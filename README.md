# GeoMine3D — 矿区三维地质可视化分析平台

> 前后端分离 · 无登录 · 无数据库 · Vue3 + Three.js + Django REST

---

## 项目简介

GeoMine3D 是一个矿区三维地质可视化分析平台原型，以 `.glb` 三维模型文件和 `.xlsx` 钻孔数据为核心输入，展示三维场景管理、业务对象联动、图表分析。

---

## 技术栈

### 前端
| 库 | 版本 | 用途 |
|---|---|---|
| Vue 3 | ^3.5 | 核心框架 |
| TypeScript | ~5.9 | 类型系统 |
| Vite | ^8.0 | 构建工具 |
| Vue Router | 4 | 路由管理 |
| Pinia | latest | 状态管理 |
| Element Plus | latest | UI 组件库 |
| Three.js | latest | 三维场景渲染 |
| ECharts | latest | 二维图表 |
| axios | latest | HTTP 客户端 |

### 后端
| 库 | 版本 | 用途 |
|---|---|---|
| Python | 3.10+ | 运行环境 |
| Django | 4.2 | Web 框架 |
| Django REST Framework | 3.14 | REST API |
| django-cors-headers | 4.3 | 跨域支持 |
| pandas + openpyxl | latest | Excel 解析 |

---

## 工程结构

```
GeoMine3D/
├── GeoMine3D/                    # 前端项目（Vue3 + TS + Vite）
│   ├── src/
│   │   ├── api/                  # axios 接口封装
│   │   │   ├── request.ts        # axios 实例 + 拦截器
│   │   │   └── modules/          # 模型/钻孔/工作面/分析接口
│   │   ├── components/
│   │   │   ├── common/           # MainLayout, PageContainer
│   │   │   ├── charts/           # BoreholeChart, StatsChart
│   │   │   ├── panels/           # LayerPanel, PropertyPanel, SearchPanel
│   │   │   └── three/            # SceneCanvas
│   │   ├── views/
│   │   │   ├── dashboard/        # 三维分析主页
│   │   │   ├── model-management/ # 模型管理
│   │   │   ├── borehole-management/  # 钻孔管理
│   │   │   ├── workingface-management/ # 工作面管理
│   │   │   └── analysis/         # 统计分析
│   │   ├── three/                # Three.js 模块
│   │   │   ├── core/             # SceneManager/CameraManager/...
│   │   │   ├── loaders/          # 模型加载器
│   │   │   ├── managers/         # ModelManager/LayerManager/...
│   │   │   └── tools/            # ClipTool/MeasureTool（占位）
│   │   ├── stores/               # Pinia 状态管理
│   │   ├── router/               # Vue Router
│   │   └── types/                # TypeScript 类型定义
│   └── package.json
│
└── backend/                      # 后端项目（Django）
    ├── config/                   # Django 配置
    │   ├── settings.py
    │   └── urls.py
    ├── apps/
    │   ├── common/               # 统一响应/异常处理
    │   └── geology/              # 业务视图 + 路由 + Service
    │       └── services/
    │           ├── model_service.py
    │           ├── borehole_excel_service.py
    │           ├── workingface_service.py
    │           └── analysis_service.py
    ├── data/
    │   ├── models_meta.json      # 模型元数据
    │   ├── workingfaces.json     # 工作面数据
    │   └── boreholes/boreholes.xlsx  # 钻孔原始数据
    ├── static/models/            # .glb 模型文件目录（按需放入）
    └── requirements.txt
```

---

## 快速启动

### 后端

```bash
cd backend

# 1. 安装依赖
pip install -r requirements.txt

# 2. 生成示例钻孔 Excel 数据（首次运行）
python scripts/create_sample_data.py

# 3. 启动服务
python manage.py runserver 8000
```

后端接口地址：`http://localhost:8000/api/`

### 前端

```bash
cd GeoMine3D

# 1. 安装依赖
npm install

# 2. 启动开发服务器
npm run dev
```

前端地址：`http://localhost:5173`

---

## API 接口说明

所有接口响应格式统一为：

```json
{
  "code": 0,
  "message": "success",
  "data": ...
}
```

### 模型接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/models` | 模型列表，支持 `?type=stratum&keyword=` |
| GET | `/api/models/{id}` | 模型详情 |
| GET | `/api/models/{id}/resource` | 模型资源路径 |

### 钻孔接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/boreholes` | 钻孔列表，支持 `?keyword=&min_depth=&max_depth=` |
| GET | `/api/boreholes/search?keyword=` | 钻孔搜索 |
| GET | `/api/boreholes/{id}` | 钻孔详情（含分层） |

### 工作面接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/workingfaces` | 工作面列表，支持 `?status=开采中` |
| GET | `/api/workingfaces/{id}` | 工作面详情 |

### 统计分析接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/analysis/thickness-distribution` | 地层厚度分布 |
| GET | `/api/analysis/borehole-depth-distribution` | 钻孔深度分布 |
| GET | `/api/analysis/workingface-status` | 工作面状态统计 |
| GET | `/api/analysis/borehole-count` | 钻孔数量统计 |
| GET | `/api/analysis/layer-frequency` | 地层频次统计 |
| GET | `/api/dashboard/summary` | 总览聚合数据 |

---

## 数据说明

### 模型文件

- 格式：`.glb`
- 存放目录：`backend/static/models/{stratum|workingface|borehole}/`
- 路径由后端接口返回，前端通过 `GLTFLoader` 动态加载
- **如果 `.glb` 文件不存在**，前端自动使用占位几何体替代，不影响功能演示

### 钻孔 Excel 数据

- 文件：`backend/data/boreholes/boreholes.xlsx`
- 表头：`钻孔名称` / `地层名称` / `深度` / `厚度`
- 深度字段语义：`topDepth = 深度`，`bottomDepth = 深度 + 厚度`
- 字段映射封装在 `borehole_excel_service.py`，修改表头只需更新 `_FIELD_MAP`

---

## 当前阶段限制

- **无登录/无权限系统** — 所有接口均可直接访问
- **无数据库** — 所有业务数据来自本地文件系统（`.glb` / `.xlsx` / `.json`）
- **无文件上传** — 上传/删除模型按钮为 UI 占位
- **钻孔无坐标** — 第一版钻孔对象位置在场景中随机生成
- **剖切/测量/标注工具** — 剖切有基础实现，测量/标注为占位

---

## 后续扩展规划

- 接入 Django ORM + PostgreSQL 作为业务存储
- 接入权限系统（JWT + RBAC）
- 接入真实文件上传（对象存储 OSS/MinIO）
- 集成 Cesium 实现 GIS 地图底图
- 真实 `.glb` 模型加载与相机定位
- 钻孔坐标导入与三维精确定位
