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
    frontend_dist_dir: Path = Path("../GeoMine3D/dist")
    serve_frontend: bool = True

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
    def frontend_dist_path(self) -> Path:
        path = self.frontend_dist_dir
        return path if path.is_absolute() else (BACKEND_DIR / path).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
