import pytest

from aidocsynth.models.settings import LLMSettings
from aidocsynth.utils.connection_utils import test_provider_connection as check_provider_connection


class FakeProvider:
    def __init__(self, cfg):
        self.cfg = cfg
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc, tb):
        return False
    async def get_models(self):
        return ["m1", "m2"]


class FailingProvider(FakeProvider):
    async def get_models(self):
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_connection_utils_success(monkeypatch):
    def fake_get_provider(cfg):
        return FakeProvider(cfg)
    monkeypatch.setattr(
        "aidocsynth.utils.connection_utils.providers.get_provider",
        fake_get_provider,
    )
    cfg = LLMSettings(provider="openai")
    ok, msg = await check_provider_connection(cfg)
    assert ok is True
    assert isinstance(msg, str) and msg


@pytest.mark.asyncio
async def test_connection_utils_failure(monkeypatch):
    def fake_get_provider(cfg):
        return FailingProvider(cfg)
    monkeypatch.setattr(
        "aidocsynth.utils.connection_utils.providers.get_provider",
        fake_get_provider,
    )
    cfg = LLMSettings(provider="openai")
    ok, msg = await check_provider_connection(cfg)
    assert ok is False
    assert msg.startswith("Fehler:")
