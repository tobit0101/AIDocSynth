from abc import ABC, abstractmethod
from importlib import resources
import json
from aidocsynth.models.settings import LLMSettings

_REGISTRY: dict[str, type["ProviderBase"]] = {}

def register(cls): _REGISTRY[cls.name] = cls; return cls
def get_provider(cfg): return _REGISTRY[cfg.provider](cfg)

class ProviderBase(ABC):
    name: str
    def __init__(self, cfg: LLMSettings): self.cfg = cfg
    
    @staticmethod
    def _prompt(name: str, **kw): return resources.files("aidocsynth.prompts").joinpath(name).read_text().format(**kw)

    async def classify_document(self, ctx: dict):
        return json.loads(await self._run(self._prompt("analysis.j2", **ctx)))

    @abstractmethod
    async def _run(self, prompt: str): ...
