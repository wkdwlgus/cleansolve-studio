from cleansolve_ai.errors import OpenAIConfigurationError


ALLOWED_IMAGE_DETAILS = {"low", "high", "auto", "original"}


class OpenAIAnalysisClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        image_detail: str = "auto",
        timeout_seconds: int = 60,
        client: object | None = None,
    ) -> None:
        if not api_key:
            raise OpenAIConfigurationError(
                "OPENAI_API_KEY is required for openai analysis client"
            )
        if not model:
            raise OpenAIConfigurationError(
                "OPENAI_MODEL_ANALYSIS is required for openai analysis client"
            )
        if image_detail not in ALLOWED_IMAGE_DETAILS:
            raise OpenAIConfigurationError(f"Unsupported OpenAI image detail: {image_detail}")
        if timeout_seconds < 1:
            raise OpenAIConfigurationError(
                "OPENAI_ANALYSIS_TIMEOUT_SECONDS must be at least 1"
            )

        self._api_key = api_key
        self._model = model
        self._image_detail = image_detail
        self._timeout_seconds = timeout_seconds
        self._client = client
