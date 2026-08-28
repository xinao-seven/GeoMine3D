# GeoMine3D FastAPI Backend

后端位于 `backend/app`，技术栈为 FastAPI、SQLAlchemy 2.0、Alembic 和 MySQL 8。旧 Django 实现已经移除，历史源数据继续由 `server/data` 和 `server/static/models` 提供。

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

- `app/api`：HTTP 路由与依赖注入
- `app/services`：业务规则和事务边界
- `app/repositories`：SQLAlchemy 查询
- `app/models`：数据库实体
- `app/schemas`：Pydantic 输入输出模型
- `app/core`：配置、数据库和异常处理
- `alembic`：数据库迁移

`import_server_data.py` 会从 `../server/data` 读取钻孔、地层和工作面，从
`../server/static/models` 扫描 GLB；两个目录都能通过 `.env` 覆盖。命令可重复执行，
业务记录按项目和业务键更新，每次执行会新增一条 `import_runs` 审计记录。

模型文件不写入 MySQL。数据库只保存路径、版本、hash、包围盒等元数据；导入的
GLB 继续保存在 `server/static/models`，新上传版本保存在 `uploads/models`，生产环境
可进一步替换为对象存储。

## 验证

```powershell
pytest
```
