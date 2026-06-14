import os
from pathlib import Path

from pydantic import BaseModel, Field


class Settings(BaseModel):
    openai_api_key: str | None = Field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY")
    )
    openai_model_analysis: str = Field(
        default_factory=lambda: os.getenv("OPENAI_MODEL_ANALYSIS", "gpt-5")
    )
    openai_model_validation: str = Field(
        default_factory=lambda: os.getenv("OPENAI_MODEL_VALIDATION", "gpt-5")
    )
    openai_model_image: str = Field(
        default_factory=lambda: os.getenv("OPENAI_MODEL_IMAGE", "gpt-image-1")
    )
    storage_root: Path = Field(
        default_factory=lambda: Path(os.getenv("CLEANSOLVE_STORAGE_ROOT", "var/jobs"))
    )


settings = Settings()
