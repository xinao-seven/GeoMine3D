"""FastAPI 依赖注入集合。

``DbSession`` 是所有路由共用的请求级数据库会话依赖；后续新增鉴权、分页等
横切依赖也集中放在这里。
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session

DbSession = Annotated[AsyncSession, Depends(get_db_session)]
