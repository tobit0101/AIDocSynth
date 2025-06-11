from abc import ABC, abstractmethod
from jinja2 import Environment, PackageLoader, FileSystemLoader, select_autoescape
import sys
import os
import json
import re
from aidocsynth.models.settings import LLMSettings

_REGISTRY: dict[str, type["ProviderBase"]] = {}

def register(cls): _REGISTRY[cls.name] = cls; return cls
def get_provider(cfg): return _REGISTRY[cfg.provider](cfg)

class ProviderBase(ABC):
    name: str

    
    def __init__(self, cfg: LLMSettings):
        self.cfg = cfg
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # Running in a PyInstaller bundle
            base_path = sys._MEIPASS
            template_folder = os.path.join(base_path, 'aidocsynth', 'prompts')
            loader = FileSystemLoader(template_folder)
        else:
            # Running in a normal Python environment
            loader = PackageLoader("aidocsynth", "prompts")
        
        self._PROMPT_ENV = Environment(
            loader=loader,
            autoescape=select_autoescape()
        )

    def _prompt(self, name: str, **kw):
        template = self._PROMPT_ENV.get_template(name)
        return template.render(**kw)

    async def classify_document(self, ctx: dict):
        response_text = await self._run(self._prompt("analysis.j2", **ctx))
        # Clean the response: remove markdown code fences and strip whitespace
        match = re.search(r"```(json)?(.*)```", response_text, re.DOTALL)
        if match:
            clean_json = match.group(2).strip()
        else:
            clean_json = response_text.strip()
        
        return json.loads(clean_json)

    @abstractmethod
    async def _run(self, prompt: str): ...
