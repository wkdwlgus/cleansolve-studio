import pytest

from cleansolve_ai import (
    MockAnalysisClient,
    OpenAIAnalysisClient,
    OpenAIConfigurationError,
    build_analysis_client,
)


def test_build_analysis_client_returns_mock_by_default_contract():
    client = build_analysis_client(client_kind="mock")

    assert isinstance(client, MockAnalysisClient)


def test_build_analysis_client_returns_openai_when_key_is_present(monkeypatch):
    monkeypatch.setattr(
        OpenAIAnalysisClient,
        "_build_client",
        staticmethod(lambda api_key, timeout_seconds: object()),
    )

    client = build_analysis_client(
        client_kind="openai",
        openai_api_key="sk-test",
        openai_model_analysis="gpt-5.5",
    )

    assert isinstance(client, OpenAIAnalysisClient)


def test_build_analysis_client_rejects_openai_without_key():
    with pytest.raises(OpenAIConfigurationError, match="OPENAI_API_KEY is required"):
        build_analysis_client(
            client_kind="openai",
            openai_api_key=None,
            openai_model_analysis="gpt-5.5",
        )


def test_build_analysis_client_rejects_unknown_kind():
    with pytest.raises(OpenAIConfigurationError, match="Unsupported analysis client"):
        build_analysis_client(client_kind="invalid")
