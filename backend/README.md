# GeoMine3D FastAPI Backend

新的后端位于 `backend/app`，目标技术栈为 FastAPI、SQLAlchemy 2.0、Alembic 和 MySQL 8。旧 Django 目录在迁移完成前仅作为数据规则参照，不再是新功能入口。

## 本地启动

```powershell
Copy-Item .env.example .env
docker compose up -d mysql
alembic upgrade head
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

模型文件不写入 MySQL。数据库只保存路径、版本、hash、包围盒等元数据，实际 GLB 文件保存在 `uploads/models`，生产环境可替换为对象存储。

## 验证

```powershell
pytest
```
