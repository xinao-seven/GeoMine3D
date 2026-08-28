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
    async with AsyncSessionFactory() as session:
        summary = await ServerDataImportService(session).run(project_name)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Import legacy server data into GeoMine3D")
    parser.add_argument("--project-name", default="锦界矿区三维地质项目")
    args = parser.parse_args()
    asyncio.run(import_data(args.project_name))


if __name__ == "__main__":
    main()
