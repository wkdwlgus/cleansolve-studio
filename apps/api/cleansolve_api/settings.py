import os
from pathlib import Path

from pydantic import BaseModel, Field


DEFAULT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def _env_value(name: str, default: str | None = None) -> str | None:
    return os.getenv(name) or _read_env_file().get(name) or default


def _read_env_file() -> dict[str, str]:
    env_path = Path(os.getenv("CLEANSOLVE_API_ENV_FILE", DEFAULT_ENV_FILE))
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


class Settings(BaseModel):
    openai_api_key: str | None = Field(
        default_factory=lambda: _env_value("OPENAI_API_KEY")
    )
    openai_model_analysis: str = Field(
        default_factory=lambda: _env_value("OPENAI_MODEL_ANALYSIS", "gpt-5")
    )
    openai_model_validation: str = Field(
        default_factory=lambda: _env_value("OPENAI_MODEL_VALIDATION", "gpt-5")
    )
    openai_model_image: str = Field(
        default_factory=lambda: _env_value("OPENAI_MODEL_IMAGE", "gpt-image-1")
    )
    storage_root: Path = Field(
        default_factory=lambda: Path(_env_value("CLEANSOLVE_STORAGE_ROOT", "var/jobs"))
    )


settings = Settings()
