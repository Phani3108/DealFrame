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


class FineTuningSettings(BaseModel):
    base_model_id: str = "mistralai/Mistral-7B-Instruct-v0.3"
    adapter_path: str = ""  # empty = no fine-tuned adapter available
    dataset_dir: str = "/tmp/temporalos/finetuning/datasets"
    models_dir: str = "/tmp/temporalos/finetuning/models"
    registry_file: str = "/tmp/temporalos/finetuning/registry.json"
    lora_r: int = 8
    lora_alpha: int = 16
    lora_dropout: float = 0.05
    target_modules: list[str] = ["q_proj", "v_proj"]
    epochs: int = 3
    learning_rate: float = 2e-4
    batch_size: int = 4
    max_length: int = 1024


class Settings(BaseSettings):
    app: AppSettings = AppSettings()
    database: DatabaseSettings = DatabaseSettings()
    openai: OpenAISettings = OpenAISettings()
    anthropic: AnthropicSettings = AnthropicSettings()
    video: VideoSettings = VideoSettings()
    audio: AudioSettings = AudioSettings()
    extraction: ExtractionSettings = ExtractionSettings()
    telemetry: TelemetrySettings = TelemetrySettings()
    finetuning: FineTuningSettings = FineTuningSettings()

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
