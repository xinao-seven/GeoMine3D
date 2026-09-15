import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import register_exception_handlers


settings.upload_path.mkdir(parents=True, exist_ok=True)
(settings.upload_path / "models").mkdir(parents=True, exist_ok=True)


class NoCacheStaticFiles(StaticFiles):
    """不缓存静态模型资产。

    原因:`/static/models` 下的文件会随数据重跑而变(位移场每次重导 sha256 都变),
    而 FastAPI 的 SPA 兜底路由曾用 `FileResponse(index.html)` 以 **HTTP 200**
    应答过同一个 URL。浏览器据此做了启发式缓存(响应里只有 etag/last-modified,
    没有 cache-control → 允许启发式新鲜度),于是后端修好后前端仍拿到旧的 HTML,
    报出 `Unexpected token '<'` 这类难以定位的错误。
    这里统一加 no-cache,彻底消除这类“看不见的缓存”故障。
    """

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    started_at = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Process-Time"] = f"{time.perf_counter() - started_at:.6f}"
    return response


register_exception_handlers(app)
app.include_router(api_router, prefix=settings.api_v1_prefix)
app.mount(settings.model_public_prefix, StaticFiles(directory=settings.upload_path), name="uploads")

# 原始交付包静态目录:server/static/models 下的资产(catalog 模型、井巷、
# 以及沉陷位移场)按 /static/models/... 直接取。
# 不走 DB 版本表是因为沉陷位移场是几 MB 级的固定数据集,且需要与 GLB 的顶点顺序
# 严格配对,用静态路径更稳。前端 vite 已把 /static 代理到本服务。
if settings.source_model_path.is_dir():
    app.mount(
        "/static/models",
        NoCacheStaticFiles(directory=settings.source_model_path),
        name="source-models",
    )


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name, "environment": settings.app_env}


# Host the built frontend (GeoMine3D/dist) so the whole service is reachable
# through this single port on the LAN. Must stay after all API routes so the
# catch-all never shadows /api, /docs, /uploads or /health.
if settings.serve_frontend:
    _frontend_dist = settings.frontend_dist_path
    if _frontend_dist.is_dir():
        if (_frontend_dist / "assets").is_dir():
            app.mount(
                "/assets",
                StaticFiles(directory=_frontend_dist / "assets"),
                name="frontend-assets",
            )

        @app.get("/{full_path:path}", include_in_schema=False, response_model=None)
        async def spa_fallback(full_path: str) -> FileResponse | JSONResponse:
            if full_path.startswith(("api/", "uploads/", "docs", "openapi.json")):
                return JSONResponse({"code": 404, "message": "Not Found", "data": None}, status_code=404)
            candidate = (_frontend_dist / full_path).resolve()
            if full_path and candidate.is_file() and candidate.is_relative_to(_frontend_dist):
                return FileResponse(candidate)
            return FileResponse(_frontend_dist / "index.html")
