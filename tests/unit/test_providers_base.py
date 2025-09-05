import pytest

from aidocsynth.models.settings import LLMSettings
from aidocsynth.services.providers.base import get_provider


def test_get_provider_unknown_raises():
    cfg = LLMSettings(provider="does-not-exist")
    with pytest.raises(ValueError):
        get_provider(cfg)
