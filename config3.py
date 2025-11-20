import os
from pydantic import Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# 환경 변수로 환경 구분 (local 또는 prod)
env = os.getenv("ENV", "local")

# 환경에 따라 다른 .env 파일 로드
if env == "prod":
    env_file_path = ".env.prod"
else:
    env_file_path = ".env"

load_dotenv(dotenv_path=env_file_path)


class Settings3(BaseSettings):
    """Version 3 (Gemini 3 Pro Preview) 전용 설정"""

    # Google API
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    google_maps_api_key: str = os.getenv("GOOGLE_MAPS_API_KEY", "")

    # Database
    db_host: str = os.getenv("DB_HOST", "")
    db_port: int = int(os.getenv("DB_PORT", "3306"))
    db_name: str = os.getenv("DB_NAME", "")
    db_user: str = os.getenv("DB_USER", "")
    db_password: str = os.getenv("DB_PASSWORD", "")

    # Clustering
    dbscan_eps_km: float = float(os.getenv("DBSCAN_EPS_KM", "7.0"))
    dbscan_min_samples: int = int(os.getenv("DBSCAN_MIN_SAMPLES", "2"))

    # Gemini 3 Pro Preview Configuration
    gemini3_model_name: str = Field(
        default="gemini-3-pro-preview",
        description="Gemini 3 Pro Preview model name"
    )
    gemini3_temperature: float = Field(
        default=0.5,
        description="Temperature for Gemini 3 Pro Preview (lower temp for better reasoning)"
    )
    gemini3_use_reasoning_mode: bool = Field(
        default=True,
        description="Enable Deep Think mode for enhanced reasoning"
    )

    # Gemini API Retry Configuration (PR#14 - compatible with v2)
    gemini_max_retries: int = Field(
        default=5,
        description="Maximum number of retry attempts for Gemini API calls"
    )
    gemini_base_delay: float = Field(
        default=2.0,
        description="Base delay in seconds for exponential backoff"
    )
    gemini_max_delay: float = Field(
        default=60.0,
        description="Maximum delay in seconds between retries"
    )

    class Config:
        env_file = ".env"


settings3 = Settings3()
