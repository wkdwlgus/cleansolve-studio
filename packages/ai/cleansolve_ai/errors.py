class OpenAIAdapterError(RuntimeError):
    """Base error for OpenAI adapter failures."""


class OpenAIConfigurationError(OpenAIAdapterError):
    """Raised when OpenAI adapter settings are invalid."""


class OpenAIResponseError(OpenAIAdapterError):
    """Raised when OpenAI response cannot be parsed or validated."""
