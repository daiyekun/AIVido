from __future__ import annotations

from functools import lru_cache

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        case_sensitive=False,
    )

    env: str = Field(default="dev", validation_alias="ENV")
    app_version: str = Field(default="1.0.0", validation_alias="APP_VERSION")
    app_name: str = Field(default="ainew", validation_alias="APP_NAME")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    database_url: str = Field(
        default="postgresql+asyncpg://ainew:ainew@localhost:5432/ainew",
        validation_alias="DATABASE_URL",
    )
    database_pool_size: int = Field(default=10, validation_alias="DATABASE_POOL_SIZE")
    database_max_overflow: int = Field(default=10, validation_alias="DATABASE_MAX_OVERFLOW")
    database_pool_timeout: int = Field(default=30, validation_alias="DATABASE_POOL_TIMEOUT")
    database_pool_recycle: int = Field(default=1800, validation_alias="DATABASE_POOL_RECYCLE")

    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")

    mq_url: str = Field(
        default="amqp://ainew:ainew@localhost:5672/ainew",
        validation_alias="MQ_URL",
    )
    mq_api: str = Field(default="http://localhost:15672/api", validation_alias="MQ_API")
    mq_user: str = Field(default="ainew", validation_alias="MQ_USER")
    mq_pass: str = Field(default="ainew", validation_alias="MQ_PASS")
    mq_vhost: str = Field(default="ainew", validation_alias="MQ_VHOST")
    mq_api_timeout: int = Field(default=10, validation_alias="MQ_API_TIMEOUT")

    minio_endpoint: str = Field(default="localhost:9000", validation_alias="MINIO_ENDPOINT")
    minio_public_endpoint: str = Field(default="http://localhost:9000", validation_alias="MINIO_PUBLIC_ENDPOINT")
    minio_access_key: str = Field(default="ainew-app", validation_alias="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field(default="ainew-secret", validation_alias="MINIO_SECRET_KEY")
    minio_secure: bool = Field(default=False, validation_alias="MINIO_SECURE")
    minio_bucket_input: str = Field(default="ai-input", validation_alias="MINIO_BUCKET_INPUT")
    minio_bucket_output: str = Field(default="ai-output", validation_alias="MINIO_BUCKET_OUTPUT")
    minio_bucket_thumb: str = Field(default="ai-thumb", validation_alias="MINIO_BUCKET_THUMB")
    minio_bucket_backup: str = Field(default="ai-backup", validation_alias="MINIO_BUCKET_BACKUP")
    signed_url_expire_minutes: int = Field(default=60, validation_alias="SIGNED_URL_EXPIRE_MINUTES")

    jwt_secret: str = Field(default="dev-only-jwt-secret-change-me-32bytes", validation_alias="JWT_SECRET")
    jwt_expire_days: int = Field(default=7, validation_alias="JWT_EXPIRE_DAYS")

    sms_provider_key: str = Field(default="", validation_alias="SMS_PROVIDER_KEY")
    sms_provider_url: str = Field(default="", validation_alias="SMS_PROVIDER_URL")
    sms_dev_fixed_code: str = Field(default="123456", validation_alias="SMS_DEV_FIXED_CODE")
    sms_code_ttl_seconds: int = Field(default=300, validation_alias="SMS_CODE_TTL_SECONDS")
    sms_rate_seconds: int = Field(default=60, validation_alias="SMS_RATE_SECONDS")
    sms_daily_limit: int = Field(default=10, validation_alias="SMS_DAILY_LIMIT")
    dev_sms_endpoint: bool = Field(default=False, validation_alias="DEV_SMS_ENDPOINT")

    upload_image_max_mb: int = Field(default=10, validation_alias="UPLOAD_IMAGE_MAX_MB")
    upload_video_max_mb: int = Field(default=200, validation_alias="UPLOAD_VIDEO_MAX_MB")
    client_max_body_size_mb: int = Field(default=210, validation_alias="CLIENT_MAX_BODY_SIZE")

    model_call_connect_timeout: float = Field(default=10.0, validation_alias="MODEL_CALL_CONNECT_TIMEOUT")
    model_call_timeout_image: int = Field(default=120, validation_alias="MODEL_CALL_TIMEOUT_IMAGE")
    model_call_timeout_video: int = Field(default=600, validation_alias="MODEL_CALL_TIMEOUT_VIDEO")
    model_call_timeout_chat: int = Field(default=60, validation_alias="MODEL_CALL_TIMEOUT_CHAT")
    model_transport_retries: int = Field(default=2, validation_alias="MODEL_TRANSPORT_RETRIES")
    model_breaker_threshold: int = Field(default=10, validation_alias="MODEL_BREAKER_THRESHOLD")
    model_breaker_reset_seconds: int = Field(default=60, validation_alias="MODEL_BREAKER_RESET_SECONDS")
    model_rate_limit_per_minute: int = Field(default=120, validation_alias="MODEL_RATE_LIMIT_PER_MINUTE")

    task_retry_delays: str = Field(default="30,120,600", validation_alias="TASK_RETRY_DELAYS")
    task_visibility_timeout: int = Field(default=3600, validation_alias="TASK_VISIBILITY_TIMEOUT")

    otel_service_name: str = Field(default="ainew-api", validation_alias="OTEL_SERVICE_NAME")
    otel_exporter: str = Field(default="log", validation_alias="OTEL_EXPORTER")
    otel_sample_ratio: float = Field(default=1.0, validation_alias="OTEL_SAMPLE_RATIO")
    otel_otlp_endpoint: str = Field(
        default="http://localhost:4317", validation_alias="OTEL_EXPORTER_OTLP_ENDPOINT"
    )

    sensitive_words_path: str = Field(default="", validation_alias="SENSITIVE_WORDS_PATH")

    @field_validator("jwt_secret")
    @classmethod
    def _check_jwt_secret(cls, value: str) -> str:
        if len(value.encode("utf-8")) < 32:
            raise ValueError("JWT_SECRET must be at least 32 bytes")
        return value

    @property
    def is_prod(self) -> bool:
        return self.env.lower() in {"prod", "production"}

    @property
    def database_url_sync(self) -> str:
        return (
            self.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
            .replace("postgres+asyncpg://", "postgresql+psycopg2://")
            .replace("postgresql://", "postgresql+psycopg2://")
            .replace("postgres://", "postgresql+psycopg2://")
        )

    @property
    def retry_delays(self) -> tuple[int, ...]:
        return tuple(int(part.strip()) for part in self.task_retry_delays.split(",") if part.strip())

    @property
    def service_name(self) -> str:
        return self.otel_service_name


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
