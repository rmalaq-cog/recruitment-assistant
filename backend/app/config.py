from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    aamad_target_runtime: str = Field(default="crewai", alias="AAMAD_TARGET_RUNTIME")
    model_name: str = Field(default="gpt-5.5", alias="MODEL")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_api_base: str | None = Field(default=None, alias="OPENAI_API_BASE")
    database_url: str = Field(default="sqlite:///./storage/recruitment_assistant.db", alias="DATABASE_URL")
    storage_dir: Path = Field(default=Path("./storage"), alias="STORAGE_DIR")
    crewai_storage_dir: Path = Field(default=Path("./storage/crewai"), alias="CREWAI_STORAGE_DIR")
    max_candidates_per_run: int = Field(default=10, alias="MAX_CANDIDATES_PER_RUN")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    crewai_max_iter: int = Field(default=8, alias="CREWAI_MAX_ITER")
    crewai_max_rpm: int = Field(default=30, alias="CREWAI_MAX_RPM")
    crewai_max_execution_time: int = Field(default=120, alias="CREWAI_MAX_EXECUTION_TIME")
    crewai_temperature: float = Field(default=0.2, alias="CREWAI_TEMPERATURE")
    crewai_max_tokens: int = Field(default=4000, alias="CREWAI_MAX_TOKENS")

    @property
    def sqlite_path(self) -> Path:
        if not self.database_url.startswith("sqlite:///"):
            msg = "Only sqlite:/// DATABASE_URL values are supported by the MVP backend."
            raise ValueError(msg)
        return Path(self.database_url.removeprefix("sqlite:///"))


@lru_cache
def get_settings() -> Settings:
    return Settings()