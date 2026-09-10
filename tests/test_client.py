import httpx
import pytest

from app.ai.client import (
    InferenceUnavailableError,
    InvalidModelOutputError,
    LocalLLMClient,
)
from app.config import Settings


def make_client(transport):
    settings = Settings(model_base_url="http://testserver/v1", model_max_retries=0)
    client = LocalLLMClient(settings)
    client._client = httpx.Client(base_url=settings.model_base_url, transport=transport)
    return client


def test_successful_chat_returns_content():
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"cards": []}'}}]})

    client = make_client(httpx.MockTransport(handler))
    result = client.chat("system", "user")
    assert result.content == '{"cards": []}'


def test_connection_error_raises_inference_unavailable():
    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    client = make_client(httpx.MockTransport(handler))
    with pytest.raises(InferenceUnavailableError):
        client.chat("system", "user")


def test_timeout_raises_inference_timeout():
    from app.ai.client import InferenceTimeoutError

    def handler(request):
        raise httpx.TimeoutException("timed out", request=request)

    client = make_client(httpx.MockTransport(handler))
    with pytest.raises(InferenceTimeoutError):
        client.chat("system", "user")


def test_server_error_raises_inference_unavailable():
    def handler(request):
        return httpx.Response(503, text="service unavailable")

    client = make_client(httpx.MockTransport(handler))
    with pytest.raises(InferenceUnavailableError):
        client.chat("system", "user")


def test_client_error_raises_invalid_model_output():
    def handler(request):
        return httpx.Response(400, text="bad request: unknown model")

    client = make_client(httpx.MockTransport(handler))
    with pytest.raises(InvalidModelOutputError):
        client.chat("system", "user")


def test_unexpected_response_shape_raises_invalid_model_output():
    def handler(request):
        return httpx.Response(200, json={"unexpected": "shape"})

    client = make_client(httpx.MockTransport(handler))
    with pytest.raises(InvalidModelOutputError):
        client.chat("system", "user")
