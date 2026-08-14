import os
from pathlib import Path

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    app_name: str = "인삼 농장 AI 영농일지 API"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    openweather_api_key: str = ""
    demo_mode: bool = True
    database_url: str = f"sqlite:///{BASE_DIR / 'ginseng_farm.db'}"
    upload_dir: str = str(BASE_DIR / "uploads")

    jwt_secret: str = "dev-only-change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 30  # 30일

    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"


settings = Settings()

os.makedirs(settings.upload_dir, exist_ok=True)
