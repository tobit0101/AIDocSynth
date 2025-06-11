from abc import ABC, abstractmethod
from jinja2 import Environment, PackageLoader, FileSystemLoader, select_autoescape
import sys
import os
import json
import re
import logging
from pathlib import Path
from aidocsynth.models.settings import LLMSettings

_REGISTRY: dict[str, type["ProviderBase"]] = {}


def register(cls): 
    _REGISTRY[cls.name] = cls
    return cls

def get_provider(cfg: LLMSettings) -> "ProviderBase":
    provider_name = cfg.provider
    if provider_name not in _REGISTRY:
        raise ValueError(f"Unknown provider: {provider_name}")
    # Always return a new instance.
    return _REGISTRY[provider_name](cfg)



class ProviderBase(ABC):
    name: str

    async def close(self):
        """Close any open connections or resources. To be overridden by subclasses."""
        pass

    def __init__(self, cfg: LLMSettings):
        self.cfg = cfg
        self.logger = logging.getLogger(self.__class__.__name__)
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # Running in a PyInstaller bundle
            bundle_dir = Path(sys._MEIPASS)
        else:
            # Running in a normal Python environment
            bundle_dir = Path(__file__).parent.parent.parent

        self._PROMPT_ENV = Environment(
            loader=FileSystemLoader(bundle_dir / "prompts"),
            autoescape=select_autoescape()
        )

    async def close(self):
        """Close any open connections or resources."""
        pass

    def _prompt(self, name: str, **kw):
        template = self._PROMPT_ENV.get_template(name)
        return template.render(**kw)

    async def classify_document(self, system_prompt: str, user_prompt: str):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        self.logger.info(f"Sending payload to LLM: {messages}")
        response_text = await self._run(messages)
        # Clean the response: remove markdown code fences and strip whitespace
        match = re.search(r"```(json)?(.*)```", response_text, re.DOTALL)
        if match:
            clean_json = match.group(2).strip()
        else:
            clean_json = response_text.strip()
        
        # Attempt to parse the cleaned JSON
        try:
            return json.loads(clean_json)
        except json.JSONDecodeError as e:
            # Log the error and the problematic string
            # Consider using self.logger if available, or print for now
            print(f"Error decoding JSON: {e}\nRaw string: '{clean_json}'") # TODO: Replace with proper logging
            raise # Re-raise the exception to be handled by the caller

    @abstractmethod
    async def _run(self, messages: list): ...
