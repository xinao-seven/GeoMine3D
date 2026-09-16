# GeoMine3D FastAPI Backend

后端位于 `backend/app`，技术栈为 FastAPI、SQLAlchemy 2.0（asyncmy）、Alembic 和 MySQL 8。旧 Django 实现已经移除，历史源数据继续由 `server/data` 和 `server/static/models` 提供。

## 本地启动

```powershell
Copy-Item .env.example .env
docker compose up -d mysql
alembic upgrade head
python scripts/import_server_data.py
uvicorn app.main:app --reload --port 8000
```

API 文档：`http://127.0.0.1:8000/docs`

## 目录职责

| 目录 | 职责 |
|------|------|
| `app/api` | HTTP 路由与依赖注入 |
| `app/services` | 业务规则和事务边界 |
| `app/repositories` | SQLAlchemy 查询 |
| `app/models` | 数据库实体 |
| `app/schemas` | Pydantic 输入输出模型 |
| `app/core` | 配置、数据库、日志、异常处理 |
| `alembic` | 数据库迁移 |
| `scripts` | 数据导入等运维脚本 |
| `tests` | pytest 测试 |

## 配置

配置通过 `.env`（参考 `.env.example`）注入，由 `app/core/config.py` 读取。与日志相关的变量：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DEBUG` | `false` | FastAPI 调试模式；**不再**控制 SQL 输出 |
| `LOG_LEVEL` | `INFO` | 应用日志级别 |
| `ACCESS_LOG` | `true` | 是否输出 HTTP 访问日志 |
| `DB_ECHO` | `false` | 是否打印 SQLAlchemy 生成的 SQL 语句 |

## 日志

日志由 `app/core/logging.py` 用 `dictConfig` 统一配置，输出到 stdout，格式固定：

```
2026-09-16 16:54:23 | INFO    | app.access                 | rid=8fcaa177 | GET /health -> 200 0.3ms
```

- `app.*` 为应用日志命名空间，按模块自动分层（`app.api` / `app.services` / `app.core` ...）；
- 请求中间件分配 `requestId` 并写入 contextvar，日志自动附加 `rid` 前缀，完整值通过响应头 `X-Request-ID` 返回；
- SQL 语句默认关闭，仅在 `DB_ECHO=true` 时由 `sqlalchemy.engine` 输出；
- uvicorn 自带 access 日志已禁用，由 `app.access` 统一输出；API 请求记 `INFO`，静态资源记 `DEBUG`；
- 未处理异常在中间件统一记录堆栈（带 `rid`）并返回统一错误体，避免 uvicorn 重复打印；
- SQLAlchemy、asyncmy、watchfiles、multipart、httpx 等第三方 logger 默认压到 `WARNING`。

新增业务日志时使用：

```python
from app.core.logging import get_logger

logger = get_logger(__name__)
logger.info("...")
```

## 数据导入

`import_server_data.py` 会从 `../server/data` 读取钻孔、地层和工作面，模型按 `../server/static/models/web_package/catalog.json` 逐层注册（分层模型、完整地层模型、巷道、工作面），不扫描静态目录。

- 数据源可通过 `.env` 覆盖：`SOURCE_DATA_DIR`、`SOURCE_MODEL_DIR`、`SOURCE_MODEL_CATALOG`、`BOREHOLE_LOCATION_FILE`、`BOREHOLE_STRATA_FILE`；
- 命令可重复执行：业务记录按项目和业务键更新，不在 catalog 中的旧模型资产会被清除，每次执行新增一条 `import_runs` 审计记录；
- 项目坐标原点取 catalog 的 `origin_restore`，保证钻孔与模型共用同一基准；
- 模型文件不写入 MySQL：数据库只保存路径、版本、hash、包围盒等元数据；导入的 GLB 保存在 `server/static/models`，新上传版本保存在 `uploads/models`，生产环境可替换为对象存储。

## 验证

```powershell
pytest
```
