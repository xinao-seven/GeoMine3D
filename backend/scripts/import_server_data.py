"""把 server/data 源数据与锦界交付包一次性导入 MySQL（项目初始化脚本）。

用法::

    python scripts/import_server_data.py [--project-name 锦界矿区三维地质项目]

可重复执行（幂等 upsert）；含建模内容的项目不会被同名劫持，
详见 ``app/services/server_import_service.py``。
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import AsyncSessionFactory
from app.services.server_import_service import ServerDataImportService


async def import_data(project_name: str) -> None:
    """执行导入并打印统计摘要。"""
    async with AsyncSessionFactory() as session:
        summary = await ServerDataImportService(session).run(project_name)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> None:
    """CLI 入口。"""
    parser = argparse.ArgumentParser(description="Import legacy server data into GeoMine3D")
    parser.add_argument("--project-name", default="锦界矿区三维地质项目")
    args = parser.parse_args()
    asyncio.run(import_data(args.project_name))


if __name__ == "__main__":
    main()
