# Task: GeoMine3D（前后端联调版，无登录 / 无数据库）

## 1. 项目背景

当前已有一个基于 Three.js 的三维地质模型展示 demo，已经具备以下基础能力：

- 可加载并展示三维地质模型
- 支持地层分层展示
- 已有部分真实项目资源，包括：
  - 地质模型（`.glb`）
  - 工作面模型（`.glb`）
  - 钻孔原始数据（`.xlsx`）

本任务目标是在现有 demo 基础上，构建一个**前后端分离的工程化平台原型**，用于展示以下能力：

- Vue 3 + TypeScript 工程化能力
- Three.js 三维场景封装能力
- ECharts 二维图表联动能力
- Element Plus 业务界面组织能力
- Django 后端接口设计与实现能力
- 前后端联调能力
- axios 接口统一封装能力
- 对 `.glb` 模型资源与 `.xlsx` 钻孔数据的工程化管理能力

---

## 2. 本阶段边界

### 2.1 本阶段要做

- 前端项目
- 后端项目
- 前后端接口联调
- 静态资源驱动的接口服务
- 三维展示、查询、分析、管理页面
- axios API 统一封装
- Django REST 风格接口
- `.glb` 模型资源管理
- `.xlsx` 钻孔数据解析与结构化返回

### 2.2 本阶段明确不做

- 不做登录
- 不做用户系统
- 不做角色权限
- 不接 PostgreSQL
- 不接 MySQL
- 不做业务数据库持久化
- 不做 Django ORM 业务存储
- 不做真实文件上传落库
- 不做复杂地质剖面计算
- 不做复杂空间分析算法
- 不做生产部署
- 不做 WebSocket
- 不做消息队列
- 不做 Cesium 集成（本阶段可预留扩展，但不强制）

说明：
- Django 项目可以保留默认 sqlite 仅用于框架最低运行要求，但**禁止作为业务数据主存储**。
- 本阶段业务数据统一来自本地文件系统：
  - `.glb` 模型文件
  - `.xlsx` 钻孔数据文件
  - 少量补充配置 `.json`

---

## 3. 项目目标

构建一个可运行的前后端分离原型系统，名称为：

**GeoMine3D**

系统至少包含以下能力：

### 3.1 前端侧
1. 三维分析主页
2. 模型管理页
3. 钻孔管理页
4. 工作面管理页
5. 统计分析页

### 3.2 后端侧
1. 提供统一 REST 风格接口
2. 提供模型、钻孔、工作面、统计分析等接口
3. 使用本地 `.glb`、`.xlsx`、`.json` 文件作为数据来源
4. 不依赖数据库
5. 响应结构统一
6. 便于后续平滑切换到数据库和对象存储

### 3.3 联调侧
1. 前端统一使用 axios 封装 API 请求
2. 页面展示数据均来自后端接口
3. 不允许前端直接读取本地 Excel / JSON 替代接口调用
4. 模型资源路径由后端提供，前端按接口返回的 URL 加载

---

## 4. 技术栈要求

### 4.1 前端必须使用
- Vue 3
- TypeScript
- Vite
- Vue Router
- Pinia
- Element Plus
- Three.js
- ECharts
- axios

### 4.2 后端必须使用
- Python
- Django
- Django REST Framework（推荐）
- django-cors-headers（用于跨域）
- pandas 或 openpyxl（用于解析 `.xlsx` 钻孔数据）

### 4.3 当前阶段禁止使用
- PostgreSQL 作为业务存储
- MySQL 作为业务存储
- SQLite 作为业务主存储
- 登录鉴权框架
- JWT
- Django 用户认证流程

---

## 5. 真实数据约束

## 5.1 模型文件格式

当前模型文件统一为：

- `.glb`

模型类别至少包括：

- 地层模型
- 工作面模型
- 钻孔模型（如果有对应 `.glb` 资源则加载；如果没有，可先用后端钻孔数据在前端生成简化几何表示）

说明：
- 前端 Three.js 加载模型时使用 `GLTFLoader`
- 模型资源路径不能硬编码在页面中
- 必须由后端接口返回模型元数据与资源 URL

---

## 5.2 钻孔数据格式

钻孔原始数据统一来自 `.xlsx` 文件。

### Excel 表头固定为：
- 钻孔名称
- 地层名称
- 深度
- 厚度

### 数据组织方式：
- 一层一行

示意：

- 第 1 行：钻孔 A，地层 1，深度 0，厚度 3
- 第 2 行：钻孔 A，地层 2，深度 3，厚度 2
- 第 3 行：钻孔 B，地层 1，深度 0，厚度 4

### 后端需要完成的解析逻辑：
1. 按“钻孔名称”分组
2. 每个钻孔下聚合多个层段
3. 每一行表示一个层段对象
4. 后端将 Excel 解析为前端可消费的结构化 JSON

### 第一版深度字段约定：
- 默认将 Excel 中的“深度”解释为**该层底界深度**
- 则：
  - `topDepth = 深度`
  - `thickness = 厚度`
  - `bottomDepth = 深度 + 厚度`

### 重要要求：
- 将“Excel 字段映射和深度语义转换逻辑”封装在后端 service 中
- 不要把字段解释硬编码到 view 中
- 后续如果业务确认“深度”代表别的含义，应能方便替换

---

## 6. 系统范围

## 6.1 前端页面范围

### A. 三维分析主页 `/dashboard`

这是系统核心页面。

建议布局：

- 顶部工具栏
- 左侧图层 / 资源面板
- 中间三维场景区
- 右侧属性 / 图表联动面板

功能要求：

#### 1）三维场景展示
- 加载地层 `.glb` 模型
- 加载工作面 `.glb` 模型
- 加载钻孔对象
- 支持相机旋转、缩放、平移
- 支持场景 resize
- 支持初始视角定位

#### 2）图层控制
- 地层显隐
- 钻孔显隐
- 工作面显隐
- 地层透明度调节
- 单层高亮

#### 3）对象拾取与属性展示
- 点击对象后高亮
- 右侧属性面板展示对象信息
- 至少支持以下三类对象：
  - 地层
  - 钻孔
  - 工作面

#### 4）搜索与定位
- 按钻孔名称搜索
- 按工作面名称搜索
- 搜索后可高亮目标或相机飞到目标附近

#### 5）分析工具预留
- 剖切按钮（允许先做简单占位或基础 plane clipping）
- 测量按钮（允许占位）
- 标注按钮（允许占位）

#### 6）联动功能
- 点击钻孔后，右侧展示该钻孔的层段柱状图
- 柱状图数据来自钻孔详情接口
- 点击柱状图层段后，可同步高亮当前钻孔或更新说明信息

---

### B. 模型管理页 `/model-management`

功能要求：

- 展示模型列表
- 按模型类型筛选（地层 / 钻孔 / 工作面）
- 显示模型基础信息：
  - 名称
  - 类型
  - 版本
  - 文件格式
  - 描述
- 点击“查看”后跳转到三维分析主页并定位到对应对象
- 提供“上传模型”“删除模型”按钮
  - 本阶段只做 UI 与接口占位
  - 后端可以返回“暂未实现”或假成功

---

### C. 钻孔管理页 `/borehole-management`

功能要求：

- 表格展示钻孔列表
- 支持关键字搜索
- 支持按钻孔名称筛选
- 支持按总深度筛选
- 点击钻孔查看详情
- 详情展示：
  - 钻孔名称
  - 总深度
  - 分层信息
- 支持“定位到三维场景”按钮

说明：
- 当前 Excel 中未提供坐标字段，因此第一版钻孔详情**不强制显示 x/y/z**
- 若后续补充坐标文件或模型映射，再扩展钻孔空间定位逻辑
- 当前“定位到三维场景”可以通过钻孔名称匹配前端已有钻孔对象或简化代理对象

---

### D. 工作面管理页 `/workingface-management`

功能要求：

- 展示工作面列表
- 展示工作面基础属性
- 支持点击查看详情
- 支持定位到三维场景
- 展示状态字段：
  - 开采中
  - 已完成
  - 规划中

---

### E. 统计分析页 `/analysis`

至少实现 3~4 个 ECharts 图表，例如：

- 地层厚度分布图
- 钻孔总深度分布图
- 工作面状态统计图
- 钻孔数量统计图

要求：

- 图表数据来自后端接口
- 图表组件要封装，不要把所有 option 堆在页面中
- 至少实现一次：
  - 图表点击 -> 跳转到 dashboard
  - 或图表点击 -> 设置联动对象 / 筛选条件

---

## 6.2 后端范围

后端负责提供前端所需的所有接口，但**不接数据库**。

实现原则：

- 使用 Django 提供 REST API
- 模型资源来自本地 `.glb` 文件目录
- 钻孔数据来自本地 `.xlsx` 文件
- 工作面和统计分析数据可来自本地 `.json` 或 service 层整理生成
- API 响应结构统一
- 代码结构清晰，便于后续接数据库

后端至少提供以下能力：

1. 模型列表接口
2. 模型详情接口
3. 模型资源地址接口
4. 钻孔列表接口（由 `.xlsx` 解析生成）
5. 钻孔详情接口（由 `.xlsx` 解析生成）
6. 工作面列表接口
7. 工作面详情接口
8. 统计分析接口
9. 搜索接口
10. Dashboard 聚合概览接口（推荐）

---

## 7. 工程结构要求

## 7.1 前端目录建议

```text
frontend/
├─ src/
│  ├─ assets/
│  ├─ components/
│  │  ├─ common/
│  │  ├─ charts/
│  │  ├─ panels/
│  │  └─ three/
│  ├─ views/
│  │  ├─ dashboard/
│  │  ├─ model-management/
│  │  ├─ borehole-management/
│  │  ├─ workingface-management/
│  │  └─ analysis/
│  ├─ router/
│  ├─ stores/
│  ├─ api/
│  ├─ types/
│  ├─ utils/
│  ├─ three/
│  │  ├─ core/
│  │  ├─ loaders/
│  │  ├─ managers/
│  │  ├─ tools/
│  │  └─ constants/
│  └─ App.vue
├─ public/
└─ package.json
7.2 后端目录建议
backend/
├─ manage.py
├─ config/
│  ├─ settings.py
│  ├─ urls.py
│  └─ wsgi.py / asgi.py
├─ apps/
│  ├─ geology/
│  │  ├─ views.py
│  │  ├─ urls.py
│  │  ├─ serializers.py
│  │  ├─ services/
│  │  │  ├─ model_service.py
│  │  │  ├─ borehole_excel_service.py
│  │  │  ├─ workingface_service.py
│  │  │  └─ analysis_service.py
│  │  └─ schemas/
│  └─ common/
│     ├─ response.py
│     └─ exceptions.py
├─ data/
│  ├─ models/
│  │  ├─ strata/
│  │  ├─ boreholes/
│  │  └─ workingfaces/
│  ├─ boreholes/
│  │  └─ boreholes.xlsx
│  ├─ workingfaces.json
│  └─ analysis.json
├─ static/
│  └─ models/
└─ requirements.txt
```
要求：

.glb 模型文件按类别存放

后端需要为前端返回模型可访问路径，例如 /static/models/...

钻孔原始 Excel 文件放在固定目录

Excel 解析逻辑必须放在 borehole_excel_service.py

不允许将 Excel 解析逻辑直接堆在 view 中

# 8. 前端接口封装要求（axios）

这是本任务的硬性要求。

## 8.1 基本要求

所有接口必须通过 axios 统一封装

不允许在页面组件中直接写裸 axios 请求

不允许页面绕过 API 层直接访问 URL

必须有统一请求实例 request.ts

必须有统一模块 API 文件

Three.js 中加载 .glb 文件所需的 URL，也必须先由后端接口提供或由接口返回资源字段

## 8.2 建议结构
src/api/
├─ request.ts
├─ modules/
│  ├─ model.ts
│  ├─ borehole.ts
│  ├─ workingface.ts
│  └─ analysis.ts
└─ index.ts
## 8.3 request.ts 需要包含

axios 实例创建

baseURL 配置

timeout 配置

request interceptor

response interceptor

错误统一处理

统一响应解包

## 8.4 API 模块职责示例
model.ts

getModelList

getModelDetail

getModelResourceUrl

borehole.ts

getBoreholeList

getBoreholeDetail

searchBoreholes

workingface.ts

getWorkingFaceList

getWorkingFaceDetail

analysis.ts

getThicknessStats

getBoreholeDepthStats

getWorkingFaceStats

getBoreholeCountStats

# 9. 后端 API 设计要求

接口返回风格统一为：

{
  "code": 0,
  "message": "success",
  "data": ...
}

错误时：

{
  "code": 1,
  "message": "error message",
  "data": null
}
# 10. 接口清单
## 10.1 模型接口
GET /api/models

获取模型列表

支持查询参数：

type：模型类型，可选，取值例如：

stratum

borehole

workingface

keyword：关键字，可选

返回字段建议包含：

id

name

type

version

format

description

fileName

fileUrl

bbox

说明：

format 当前统一为 glb

fileUrl 为前端 Three.js GLTFLoader 可直接加载的地址

GET /api/models/{id}

获取模型详情

GET /api/models/{id}/resource

返回某个模型资源的访问地址与元信息

## 10.2 钻孔接口
GET /api/boreholes

获取钻孔列表

数据来源：

后端解析 .xlsx 文件后返回

支持查询参数：

keyword

min_depth

max_depth

返回字段建议：

id

name

totalDepth

layerCount

GET /api/boreholes/{id}

获取钻孔详情

返回字段建议：

id

name

totalDepth

layers

其中 layers 每项包含：

layerName

topDepth

bottomDepth

thickness

GET /api/boreholes/search

按关键字搜索钻孔

## 10.3 工作面接口
GET /api/workingfaces

获取工作面列表

支持查询参数：

keyword

status

GET /api/workingfaces/{id}

获取工作面详情

## 10.4 统计分析接口
GET /api/analysis/thickness-distribution

获取地层厚度分布

说明：

基于 .xlsx 钻孔分层数据统计生成

GET /api/analysis/borehole-depth-distribution

获取钻孔总深度分布

说明：

基于 Excel 中钻孔层段累积后的总深度生成

GET /api/analysis/workingface-status

获取工作面状态统计

GET /api/analysis/borehole-count

获取钻孔数量统计

GET /api/analysis/layer-frequency

获取不同地层出现频次统计（推荐）

## 10.5 Dashboard 聚合接口（推荐）
GET /api/dashboard/summary

返回 dashboard 初始所需概览数据，例如：

模型数量

钻孔数量

工作面数量

默认展示对象

简要统计摘要

说明：

非必须，但推荐实现

可体现接口聚合设计能力

# 11. 后端数据来源要求

本阶段所有业务数据来自本地文件系统，不接数据库。

## 11.1 模型资源来源

模型文件统一使用 .glb 格式，存放于本地目录，例如：

backend/data/models/strata/
backend/data/models/boreholes/
backend/data/models/workingfaces/

要求：

后端维护模型元数据

后端向前端返回 .glb 文件访问路径

前端通过 Three.js 的 GLTFLoader 加载这些 .glb 文件

不允许前端手写固定文件路径绕过后端接口

## 11.2 钻孔数据来源

钻孔原始数据统一来自 .xlsx 文件，例如：

backend/data/boreholes/boreholes.xlsx

Excel 表头固定为：

钻孔名称

地层名称

深度

厚度

要求：

后端负责解析 Excel

后端负责将 Excel 原始字段转换为前端可消费的结构化 JSON

后端负责提供搜索、筛选、详情查询与统计能力

不允许前端直接读取 Excel 文件

## 11.3 工作面与补充配置来源

工作面信息、分析配置、辅助字典等，可以先放在 .json 文件中，例如：

backend/data/workingfaces.json
backend/data/analysis.json
# 12. 数据结构要求
## 12.1 模型元数据结构

模型元数据不要求来自数据库，但后端至少要整理出以下字段：

id

name

type

version

format

description

fileName

fileUrl

bbox

说明：

format 当前固定为 glb

fileUrl 为前端加载地址

bbox 可选，但推荐保留，便于后续相机定位

## 12.2 钻孔数据结构（由 .xlsx 解析后返回）
钻孔列表项建议包含：

id

name

totalDepth

layerCount

钻孔详情建议包含：

id

name

totalDepth

layers

其中 layers 每项包含：

layerName

topDepth

bottomDepth

thickness

说明：

Excel 原始字段名称固定为：钻孔名称 / 地层名称 / 深度 / 厚度

Excel 中多行表示同一钻孔的不同层段，后端需聚合为 borehole + layers[] 结构

第一版默认：

topDepth = 深度

bottomDepth = 深度 + 厚度

前端只消费结构化结果，不关心 Excel 原始格式

## 12.3 工作面数据结构

字段建议：

id

code

name

status

description

modelId

说明：

modelId 用于关联对应 .glb 工作面模型

## 12.4 统计分析数据结构

统计分析数据由后端从 Excel / JSON 整理后返回，至少覆盖：

地层厚度分布

钻孔总深度分布

工作面状态统计

钻孔数量统计

地层出现频次统计（推荐）

# 13. 前端页面开发要求
## 13.1 Dashboard 页面

必须通过 API 获取以下数据：

模型列表与模型资源路径

钻孔数据

工作面数据

钻孔详情

图表联动数据

说明：

.glb 文件通过模型接口返回的 fileUrl 加载

钻孔数据通过钻孔接口获取

不允许页面中写死模型路径

不允许页面直接读取 Excel 或 JSON 本地文件

建议页面结构：

Dashboard
├─ Toolbar
├─ LayerPanel
├─ SearchPanel
├─ SceneCanvas
├─ PropertyPanel
└─ BoreholeChartPanel
## 13.2 管理页要求

所有管理页表格数据都来自 axios 请求。

模型管理页

调用模型列表接口

支持筛选

支持查看详情

钻孔管理页

调用钻孔列表接口

支持搜索

支持查看详情

支持定位到 dashboard

工作面管理页

调用工作面列表接口

支持状态筛选

支持查看详情

支持定位到 dashboard

## 13.3 分析页要求

分析页必须通过后端接口获取图表数据。

至少实现 3~4 张图表，并完成以下任一联动：

图表点击后跳转 dashboard

图表点击后设置目标对象

图表点击后筛选某一类数据

# 14. Three.js 模块拆分要求

Three.js 逻辑必须模块化，不允许堆在单个页面中。

建议拆分：

core

SceneManager

CameraManager

RendererManager

ControlsManager

LightManager

loaders

StratumModelLoader

BoreholeModelLoader

WorkingFaceModelLoader

managers

ModelManager

LayerManager

SelectionManager

HighlightManager

tools

ClipTool

MeasureTool（可占位）

SectionTool（可占位）

AnnotationTool（可占位）

关键要求：

提供场景初始化与销毁逻辑

页面销毁时清理 renderer、controls、监听器

对象拾取独立封装

高亮独立封装

图层显隐独立封装

# 15. 状态管理要求（Pinia）

至少实现以下 store：

projectStore

管理当前项目、资源等

sceneStore

管理：

当前选中对象

当前高亮对象

当前图层状态

当前透明度设置

boreholeStore

管理：

钻孔列表

当前钻孔详情

钻孔搜索条件

analysisStore

管理：

图表筛选条件

当前图表联动项

要求：

页面共享状态尽量进入 store

与三维场景选中对象有关的状态统一进入 sceneStore

# 16. 路由要求

至少包含以下路由：

/dashboard
/model-management
/borehole-management
/workingface-management
/analysis

要求：

使用统一 MainLayout

左侧菜单切换页面

“定位到三维场景”通过 query 参数或 Pinia 实现

# 17. 组件封装要求

至少抽离以下组件：

MainLayout

PageContainer

SceneCanvas

LayerPanel

PropertyPanel

SearchPanel

BoreholeChart

StatsChart

ModelTable

BoreholeTable

WorkingFaceTable

要求：

页面逻辑与通用组件分离

图表组件可复用

表格与面板尽量抽象

# 18. 后端代码要求
## 18.1 视图层要求

view 中只处理请求参数、调用 service、返回统一响应

不在 view 中堆复杂业务逻辑

## 18.2 service 层要求

model_service.py 负责整理 .glb 模型元数据与资源路径

borehole_excel_service.py 负责解析 .xlsx，并提供：

钻孔列表

钻孔详情

搜索

筛选

简单统计

workingface_service.py 负责工作面 JSON 数据

analysis_service.py 负责统计分析结果聚合

## 18.3 Excel 解析要求

推荐使用 pandas.read_excel() 或 openpyxl

需要封装字段映射逻辑

需要封装钻孔分组聚合逻辑

需要根据“深度 + 厚度”生成 topDepth / bottomDepth

需要能够统计每个钻孔总深度（可取最大 bottomDepth 或层段累积后的最大值）

需要考虑后续更换 Excel 模板时的可维护性

## 18.4 模型资源要求

.glb 资源路径不要硬编码在前端页面

必须由后端统一整理并返回

后续要能平滑切换到数据库或对象存储方案

## 18.5 CORS

配置跨域，保证前端本地开发可联调

# 19. 代码规范要求
前端

全项目使用 TypeScript

尽量避免 any

类型集中管理在 types/

API 类型、响应类型尽量明确

不要出现超大单文件

后端

函数职责单一

service 拆分清楚

URL 命名清晰

统一返回结构

适当添加注释

# 20. README 要求

需要分别为前端和后端提供说明，或统一在根目录 README 中说明：

至少包括：

项目简介

技术栈

前端目录结构

后端目录结构

启动方式

接口说明

当前阶段限制说明：

无登录

无数据库

静态文件驱动

真实数据说明：

模型文件为 .glb

钻孔原始数据为 .xlsx

Excel 表头为：钻孔名称 / 地层名称 / 深度 / 厚度

后续扩展方向：

接 Django ORM

接 PostgreSQL

接权限系统

接 Cesium

接真实上传流程

# 21. 交付物要求

需要交付：

## 21.1 前端代码工程

可运行的 Vue 3 + TS 项目

## 21.2 后端代码工程

可运行的 Django 项目

## 21.3 接口联调结果

前端页面数据真实来自后端接口

## 21.4 README

清晰说明启动流程和接口说明

## 21.5 可演示内容

至少包括：

dashboard 三维场景

图层控制

对象点击与属性展示

钻孔柱状图联动

管理页表格展示

分析页图表展示

至少一个跨页面 / 跨模块联动

# 22. 验收标准
必须满足

前后端都可以正常启动

前端所有业务数据来自后端接口

前端所有接口统一使用 axios 封装

dashboard 页面有真实 Three.js 场景

.glb 模型资源能够通过后端接口返回并被前端正常加载

钻孔数据来自后端对 .xlsx 文件的解析结果

Excel 表头按“钻孔名称 / 地层名称 / 深度 / 厚度”正确解析

至少三类对象可展示：

地层

钻孔

工作面

支持对象点击与属性展示

支持基础图层显隐

至少有一个钻孔图表联动

至少有一个统计分析页

后端不依赖数据库存储业务数据

工程结构清晰，不是 demo 式堆代码

加分项

透明度调节体验较好

搜索定位功能完整

dashboard 聚合接口设计较好

service 层封装合理

图表点击联动较自然

README 完整

页面风格统一

# 23. 推荐开发顺序
第一步：搭后端骨架

初始化 Django

配置 CORS

封装统一响应

准备 .glb 资源目录与 .xlsx 文件

完成模型 / 钻孔 / 工作面 / 分析接口

第二步：搭前端骨架

初始化 Vue3 + TS + Vite

接入 Element Plus / Router / Pinia

创建 axios 请求封装

完成 API 模块文件

第三步：联调基础列表页

模型管理页

钻孔管理页

工作面管理页

确保前端能拿到后端数据

第四步：搭 Dashboard

三维场景封装

glb 模型加载

图层控制

属性展示

搜索定位

第五步：补分析联动

钻孔柱状图

统计分析页

图表点击联动

第六步：整理与优化

类型补齐

README

异常处理

页面细节优化

# 24. 输出风格要求

实现时请遵循以下原则：

优先保证结构清晰，而不是一次性追求所有功能做满

优先做“可扩展平台原型”

后端要体现真实接口设计能力

前端要体现工程化与组件化能力

当前实现可以简化业务细节，但结构不能做死

必须为后续接数据库、接登录、接 Cesium 预留扩展空间

# 25. 最终一句话目标

请基于现有 Three.js 地质模型 demo，完成一个前后端分离、无登录、无数据库、通过 axios 统一封装接口、以 .glb 模型和 .xlsx 钻孔数据为核心输入的矿区三维地质可视化分析平台原型，重点展示三维场景管理、业务对象联动、图表分析、Django 接口设计与前后端工程组织能力。