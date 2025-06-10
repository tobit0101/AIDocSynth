from abc import ABC, abstractmethod
from jinja2 import Environment, PackageLoader, select_autoescape
import json
from aidocsynth.models.settings import LLMSettings

_REGISTRY: dict[str, type["ProviderBase"]] = {}

def register(cls): _REGISTRY[cls.name] = cls; return cls
def get_provider(cfg): return _REGISTRY[cfg.provider](cfg)

class ProviderBase(ABC):
    name: str
    def __init__(self, cfg: LLMSettings): self.cfg = cfg
    
    _PROMPT_ENV = Environment(
        loader=PackageLoader("aidocsynth", "prompts"),
        autoescape=select_autoescape()
    )

    def _prompt(self, name: str, **kw):
        template = self._PROMPT_ENV.get_template(name)
        return template.render(**kw)

    async def classify_document(self, ctx: dict):
        return json.loads(await self._run(self._prompt("analysis.j2", **ctx)))

    @abstractmethod
    async def _run(self, prompt: str): ...
