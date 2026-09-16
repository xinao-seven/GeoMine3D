from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
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
    model_public_prefix: str = "/uploads"
    max_upload_size_mb: int = 1024
    source_data_dir: Path = Path("../server/data")
    source_model_dir: Path = Path("../server/static/models")
    source_model_catalog: Path = Path("../server/static/models/web_package/catalog.json")
    # 钻孔数据源(相对 source_data_dir)。分层表换版本时只需改这里。
    borehole_location_file: str = "location/钻孔位置.xlsx"
    borehole_strata_file: str = "boreholes/地层汇总14层.xlsx"
    frontend_dist_dir: Path = Path("../GeoMine3D/dist")
    serve_frontend: bool = True

    @property
    def log_level_name(self) -> str:
        return self.log_level.upper()

    @property
    def upload_path(self) -> Path:
        path = self.upload_dir
        return path if path.is_absolute() else BACKEND_DIR / path

    @property
    def source_data_path(self) -> Path:
        path = self.source_data_dir
        return path if path.is_absolute() else (BACKEND_DIR / path).resolve()

    @property
    def source_model_path(self) -> Path:
        path = self.source_model_dir
        return path if path.is_absolute() else (BACKEND_DIR / path).resolve()

    @property
    def source_model_catalog_path(self) -> Path:
        path = self.source_model_catalog
        return path if path.is_absolute() else (BACKEND_DIR / path).resolve()

    @property
    def frontend_dist_path(self) -> Path:
        path = self.frontend_dist_dir
        return path if path.is_absolute() else (BACKEND_DIR / path).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
