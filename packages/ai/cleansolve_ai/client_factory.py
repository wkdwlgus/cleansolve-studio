from cleansolve_ai.adapter import AnalysisClient
from cleansolve_ai.errors import OpenAIConfigurationError
from cleansolve_ai.mock_client import MockAnalysisClient
from cleansolve_ai.openai_client import OpenAIAnalysisClient


def build_analysis_client(
    *,
    client_kind: str,
    openai_api_key: str | None = None,
    openai_model_analysis: str = "gpt-5.5",
    openai_analysis_image_detail: str = "auto",
    openai_analysis_timeout_seconds: int = 60,
) -> AnalysisClient:
    if client_kind == "mock":
        return MockAnalysisClient()
    if client_kind == "openai":
        return OpenAIAnalysisClient(
            api_key=openai_api_key or "",
            model=openai_model_analysis,
            image_detail=openai_analysis_image_detail,
            timeout_seconds=openai_analysis_timeout_seconds,
        )
    raise OpenAIConfigurationError(f"Unsupported analysis client: {client_kind}")
