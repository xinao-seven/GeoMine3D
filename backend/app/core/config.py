"""全局配置（pydantic-settings）。

所有配置项都可用环境变量 / backend/.env 覆盖（大小写不敏感），默认值面向
"本机 docker compose 起 MySQL+Redis" 的开发场景。相对路径一律相对 backend/
目录解析（见各 *path 属性），使 uvicorn 从任意工作目录启动行为一致。
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """应用配置。字段分组与默认值见模块 docstring 与各组行内注释。"""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "GeoMine3D API"
    app_env: str = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    # 日志
    log_level: str = "INFO"
    access_log: bool = True
    # 是否打印 SQLAlchemy 生成的 SQL 语句(独立于 DEBUG,避免调试时刷屏)
    db_echo: bool = False
    database_url: str = (
        "mysql+asyncmy://geomine:geomine@127.0.0.1:3306/geomine3d?charset=utf8mb4"
    )
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    upload_dir: Path = Path("uploads")
    # 模型文件唯一根目录(对外挂载 /static/models):锦界交付包、上传建模交付包、
    # 手动上传版本与固定数据集都在这里,见 app/services/model_paths.py。
    source_model_dir: Path = Path("../server/static/models")
    source_model_catalog: Path = Path("../server/static/models/web_package/catalog.json")
    max_upload_size_mb: int = 1024
    source_data_dir: Path = Path("../server/data")
    # 钻孔数据源(相对 source_data_dir)。分层表换版本时只需改这里。
    borehole_location_file: str = "location/钻孔位置.xlsx"
    borehole_strata_file: str = "boreholes/地层汇总14层.xlsx"
    # 矿区边界/工作面范围 Shapefile(相对 source_data_dir,CAD 折线导出,pyshp 读取)
    mine_boundary_shp: str = "shp/锦界矿边界.shp"
    workingface_boundary_shp: str = "shp/开采工作面.shp"
    frontend_dist_dir: Path = Path("../GeoMine3D/dist")
    serve_frontend: bool = True
    # 远程调试中继(WebSocket /api/v1/remote/ws + /remote/invoke):供 backend/mcp_server.py
    # 把命令转发到浏览器工作台的 __geomine 桥;整体关闭时不影响常规 API。
    remote_debug_enabled: bool = True
    # 钻孔建模引擎(modeling_engine):上传 14层汇总表后异步生成模型交付包。
    modeling_max_concurrent: int = 1
    modeling_timeout_seconds: int = 1800
    # Redis:建模任务队列 / 进度推送 / 分析结果缓存共用。由 backend/docker-compose.yml
    # 的单容器 redis 服务提供(``docker compose up -d``)。
    # ``redis_enabled=false`` 时后端自动降级回进程内后台任务(与引入 Redis 之前一致),
    # 保证没起 Redis 也能开发调试;所有调用方都必须容忍 ``get_redis()`` 返回 None。
    redis_enabled: bool = True
    redis_url: str = "redis://127.0.0.1:6379/0"
    redis_key_prefix: str = "geomine"
    # 建模任务队列(Redis Stream):重试与存活语义
    modeling_max_attempts: int = 3
    modeling_retry_backoff_seconds: float = 5.0
    # worker 心跳刷新间隔小于 TTL 1/3;TTL 过期即视为“没人真在跑这个任务”
    modeling_heartbeat_ttl_seconds: int = 15
    # 消息被某个 worker 读走但迟迟不 ACK(进程崩了),超过这个空闲时长后允许重认领
    modeling_reclaim_idle_ms: int = 60000

    @property
    def log_level_name(self) -> str:
        """日志级别名（统一大写，供 dictConfig 使用）。"""
        return self.log_level.upper()

    @property
    def upload_path(self) -> Path:
        """运行期上传根目录（建模任务输入/日志），绝对化到 backend/。"""
        path = self.upload_dir
        return path if path.is_absolute() else BACKEND_DIR / path

    @property
    def source_data_path(self) -> Path:
        """业务源数据目录（server/data），绝对化到仓库根。"""
        path = self.source_data_dir
        return path if path.is_absolute() else (BACKEND_DIR / path).resolve()

    @property
    def source_model_path(self) -> Path:
        """模型文件唯一根目录（server/static/models），绝对化到仓库根。"""
        path = self.source_model_dir
        return path if path.is_absolute() else (BACKEND_DIR / path).resolve()

    @property
    def source_model_catalog_path(self) -> Path:
        """锦界交付包 catalog.json 路径。"""
        path = self.source_model_catalog
        return path if path.is_absolute() else (BACKEND_DIR / path).resolve()

    @property
    def frontend_dist_path(self) -> Path:
        """前端构建产物目录（serve_frontend=true 时由后端托管）。"""
        path = self.frontend_dist_dir
        return path if path.is_absolute() else (BACKEND_DIR / path).resolve()


@lru_cache
def get_settings() -> Settings:
    """进程级单例配置（lru_cache 保证只读一次 .env/环境变量）。"""
    return Settings()


settings = get_settings()
