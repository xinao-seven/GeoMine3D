# GeoMine3D 后端接口文档

## 1. 基本信息

- 基础前缀：`/api`
- 协议：HTTP
- 数据格式：`application/json`
- 当前接口方法：全部为 `GET`
- CSRF：接口已通过 `csrf_exempt` 放行

## 2. 统一响应结构

### 2.1 成功响应

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

### 2.2 失败响应

```json
{
  "code": 1,
  "message": "error",
  "data": null
}
```

说明：
- 业务成功固定 `code = 0`
- 业务失败 `code != 0`，部分接口会返回 `404/500` HTTP 状态码

## 3. 模型接口

### 3.1 获取模型列表

- 路径：`GET /api/models`
- Query 参数：
  - `type`（可选）：`stratum | workingface | borehole`
  - `keyword`（可选）：按名称/描述模糊搜索

返回 `data` 示例：

```json
[
  {
    "id": "auto-1000",
    "name": "地层模型-xxx",
    "type": "stratum",
    "version": "1.0",
    "format": "glb",
    "description": "自动识别: xxx.glb",
    "fileName": "xxx.glb",
    "fileUrl": "/static/models/strata/xxx.glb",
    "bbox": null
  }
]
```

### 3.2 获取模型详情

- 路径：`GET /api/models/{model_id}`
- Path 参数：
  - `model_id`：模型 ID

失败场景：
- 模型不存在：HTTP `404`，`code = 404`

### 3.3 获取模型资源信息

- 路径：`GET /api/models/{model_id}/resource`
- Path 参数：
  - `model_id`：模型 ID

返回 `data` 示例：

```json
{
  "id": "auto-1000",
  "name": "地层模型-xxx",
  "fileUrl": "/static/models/strata/xxx.glb",
  "format": "glb",
  "bbox": null
}
```

失败场景：
- 模型不存在：HTTP `404`，`code = 404`

## 4. 钻孔接口

### 4.1 获取钻孔列表

- 路径：`GET /api/boreholes`
- Query 参数：
  - `keyword`（可选）：钻孔名称模糊匹配
  - `min_depth`（可选）：最小总深度
  - `max_depth`（可选）：最大总深度

返回 `data` 示例：

```json
[
  {
    "id": "1",
    "name": "ZK001",
    "totalDepth": 365.2,
    "layerCount": 8,
    "location": {
      "x": 4232511.123,
      "y": 384512.456,
      "z": 1250.0
    }
  }
]
```

说明：
- `location` 可能为 `null`

### 4.2 获取钻孔详情

- 路径：`GET /api/boreholes/{borehole_id}`
- Path 参数：
  - `borehole_id`：钻孔 ID

返回 `data` 示例：

```json
{
  "id": "1",
  "name": "ZK001",
  "totalDepth": 365.2,
  "layerCount": 8,
  "layers": [
    {
      "layerName": "砂岩",
      "topDepth": 10.0,
      "thickness": 20.0,
      "bottomDepth": 30.0
    }
  ],
  "location": {
    "x": 4232511.123,
    "y": 384512.456,
    "z": 1250.0
  }
}
```

失败场景：
- 钻孔不存在：HTTP `404`，`code = 404`

### 4.3 搜索钻孔

- 路径：`GET /api/boreholes/search`
- Query 参数：
  - `keyword`（可选，默认空字符串）

返回结构与 `GET /api/boreholes` 一致。

### 4.4 获取钻孔 WGS84 点位

- 路径：`GET /api/boreholes/wgs84`
- Query 参数：无

返回 `data` 示例：

```json
{
  "items": [
    {
      "id": "1",
      "name": "ZK001",
      "longitude": 109.12345678,
      "latitude": 38.12345678,
      "altitude": 1250.0,
      "source": {
        "x": 4232511.123,
        "y": 384512.456,
        "z": 1250.0
      }
    }
  ]
}
```

## 5. 工作面接口

### 5.1 获取工作面列表

- 路径：`GET /api/workingfaces`
- Query 参数：
  - `keyword`（可选）：按 `name/code` 模糊搜索
  - `status`（可选）：状态精确匹配

返回 `data`：`workingfaces.json` 中对象数组（原样返回）。

### 5.2 获取工作面详情

- 路径：`GET /api/workingfaces/{wf_id}`
- Path 参数：
  - `wf_id`：工作面 ID

失败场景：
- 工作面不存在：HTTP `404`，`code = 404`

## 6. 空间边界与投影接口

### 6.1 获取矿区边界（GeoJSON）

- 路径：`GET /api/boundaries/mine-area`

返回 `data`：GeoJSON FeatureCollection，结构示例：

```json
{
  "type": "FeatureCollection",
  "sourceCrs": "EPSG:xxxx",
  "targetCrs": "EPSG:4326",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "source": "mine-area"
      },
      "geometry": {
        "type": "Polygon",
        "coordinates": []
      }
    }
  ]
}
```

失败场景：
- SHP 文件不存在：HTTP `404`
- 解析失败：HTTP `500`

### 6.2 获取工作面边界（GeoJSON）

- 路径：`GET /api/boundaries/working-faces`

返回结构与矿区边界一致，`properties.source = "working-face"`。

失败场景：
- SHP 文件不存在：HTTP `404`
- 解析失败：HTTP `500`

### 6.3 获取投影元信息

- 路径：`GET /api/system/projection`

返回 `data` 示例：

```json
{
  "sourceCrs": "EPSG:xxxx",
  "mineAreaSourceCrs": "EPSG:xxxx",
  "workingFaceSourceCrs": "EPSG:xxxx",
  "targetCrs": "EPSG:4326",
  "sourceShpDir": ".../backend/data/shp"
}
```

## 7. 统计分析接口

### 7.1 地层厚度分布

- 路径：`GET /api/analysis/thickness-distribution`

返回 `data`：

```json
{
  "labels": ["砂岩", "泥岩"],
  "values": [12.5, 8.2],
  "counts": [10, 8]
}
```

### 7.2 钻孔深度分布

- 路径：`GET /api/analysis/borehole-depth-distribution`

返回 `data`：

```json
{
  "items": [{ "name": "ZK001", "totalDepth": 365.2 }],
  "labels": ["ZK001"],
  "values": [365.2]
}
```

### 7.3 工作面状态分布

- 路径：`GET /api/analysis/workingface-status`

返回 `data`：

```json
{
  "items": [{ "status": "开采中", "count": 6 }],
  "labels": ["开采中"],
  "values": [6]
}
```

### 7.4 钻孔数量统计

- 路径：`GET /api/analysis/borehole-count`

返回 `data`：

```json
{
  "total": 120,
  "items": []
}
```

### 7.5 地层出现频率

- 路径：`GET /api/analysis/layer-frequency`

返回 `data`：

```json
{
  "labels": ["砂岩", "泥岩"],
  "values": [40, 35]
}
```

### 7.6 钻孔原始 XY 点位

- 路径：`GET /api/analysis/borehole-xy-raw`

返回 `data`：

```json
{
  "items": [
    { "id": "1", "name": "ZK001", "x": 4232511.123, "y": 384512.456, "z": 1250.0 }
  ],
  "labels": ["ZK001"],
  "xValues": [4232511.123],
  "yValues": [384512.456]
}
```

## 8. Dashboard 聚合接口

### 8.1 首页汇总

- 路径：`GET /api/dashboard/summary`

返回 `data`：

```json
{
  "modelCount": 12,
  "boreholeCount": 120,
  "workingFaceCount": 18,
  "stratumModelCount": 5,
  "activeWorkingFaceCount": 6
}
```

## 9. 快速调试示例

```bash
curl "http://127.0.0.1:8000/api/models?type=stratum"
curl "http://127.0.0.1:8000/api/boreholes/wgs84"
curl "http://127.0.0.1:8000/api/boundaries/mine-area"
curl "http://127.0.0.1:8000/api/dashboard/summary"
```

## 10. 备注

- 路由定义位置：`backend/apps/geology/urls.py`
- 视图定义位置：`backend/apps/geology/views.py`
- 统一响应封装：`backend/apps/common/response.py`
- 当前文档基于代码实现生成，后续新增接口请同步更新本文档。
