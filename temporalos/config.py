"""Settings — Pydantic-based configuration with env var overrides."""

from functools import lru_cache

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseModel):
    name: str = "temporalos"
    env: str = "development"
    upload_dir: str = "/tmp/temporalos/uploads"
    frames_dir: str = "/tmp/temporalos/frames"


class DatabaseSettings(BaseModel):
    url: str = "postgresql+asyncpg://temporalos:temporalos@localhost:5432/temporalos"


class OpenAISettings(BaseModel):
    model: str = "gpt-4o"
    vision_model: str = "gpt-4o"
    max_tokens: int = 2048
    temperature: float = 0.0


class AnthropicSettings(BaseModel):
    model: str = "claude-sonnet-4-5"
    vision_model: str = "claude-sonnet-4-5"
    max_tokens: int = 2048


class VideoSettings(BaseModel):
    frame_interval_seconds: int = 2
    max_resolution: int = 1024
    supported_formats: list[str] = ["mp4", "webm", "mkv", "mov"]


class AudioSettings(BaseModel):
    whisper_model: str = "large-v3"
    language: str = "en"
    word_timestamps: bool = True


class ExtractionSettings(BaseModel):
    default_model: str = "gpt4o"
    segment_overlap_ms: int = 500
    min_words_per_segment: int = 3


class TelemetrySettings(BaseModel):
    service_name: str = "temporalos"
    otlp_endpoint: str = ""
    enabled: bool = True
    log_level: str = "INFO"


class Settings(BaseSettings):
    app: AppSettings = AppSettings()
    database: DatabaseSettings = DatabaseSettings()
    openai: OpenAISettings = OpenAISettings()
    anthropic: AnthropicSettings = AnthropicSettings()
    video: VideoSettings = VideoSettings()
    audio: AudioSettings = AudioSettings()
    extraction: ExtractionSettings = ExtractionSettings()
    telemetry: TelemetrySettings = TelemetrySettings()

    # Top-level env var overrides (most commonly set in .env)
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    database_url: str = ""
    temporalos_mode: str = "api"  # api | local

    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        extra="ignore",
    )

    @property
    def effective_database_url(self) -> str:
        return self.database_url or self.database.url


@lru_cache
def get_settings() -> Settings:
    return Settings()
