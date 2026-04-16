from abc import ABC, abstractmethod
from typing import List, Callable, Tuple
from jinja2 import Environment, PackageLoader, FileSystemLoader, select_autoescape
import sys
import os
import json
import re
import logging
from pathlib import Path
from aidocsynth.models.settings import LLMSettings
import datetime
from aidocsynth.services.settings_service import settings

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, type["ProviderBase"]] = {}


def register(cls): 
    _REGISTRY[cls.name] = cls
    return cls

def get_provider(cfg: LLMSettings) -> "ProviderBase":
    provider_name = cfg.provider
    logger.debug(f"get_provider called for: {provider_name}")
    if provider_name not in _REGISTRY:
        logger.error(f"Provider '{provider_name}' not found in _REGISTRY. Available: {list(_REGISTRY.keys())}")
        raise ValueError(f"Unknown provider: {provider_name}")
    
    provider_class = _REGISTRY[provider_name]
    logger.debug(f"Found provider class for '{provider_name}': {provider_class}")
    
    # Always return a new instance.
    instance = provider_class(cfg)
    logger.debug(f"Created instance for '{provider_name}': {type(instance)}")
    return instance



class ProviderBase(ABC):
    name: str

    async def close(self):
        """Close any open connections or resources. To be overridden by subclasses."""
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()

    @abstractmethod
    async def get_models(self, **kwargs) -> List[str]:
        """
        Fetches the list of available models from the provider.
        Raises an exception if the connection or authentication fails.
        """
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

    async def classify_document(self, system_prompt: str, user_prompt: str, is_cancelled_callback: Callable[[], bool] = None):
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        response_text = await self._run(messages, is_cancelled_callback=is_cancelled_callback)

        # --- KI-Logging ---
        if settings.data.llm.log_prompts:
            try:
                # Eigener Unterordner für die Markdown-Dumps
                log_dir = Path.home() / ".config" / "AIDocSynth" / "logs" / "llm_prompts"
                log_dir.mkdir(parents=True, exist_ok=True)
                
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                provider_name = self.name
                log_file = log_dir / f"{timestamp}_{provider_name}.md"
                
                with open(log_file, "w", encoding="utf-8") as f:
                    f.write(f"# LLM Debug Log ({timestamp})\n\n")
                    f.write(f"**Provider:** {provider_name}\n")
                    f.write(f"**Model:** {getattr(self, 'model', 'Unbekannt')}\n\n")
                    
                    f.write("## System Prompt\n```text\n")
                    f.write(system_prompt)
                    f.write("\n```\n\n")
                    
                    f.write("## User Prompt (OCR Text)\n```text\n")
                    f.write(user_prompt)
                    f.write("\n```\n\n")
                    
                    f.write("## Raw Response\n```json\n")
                    f.write(response_text)
                    f.write("\n```\n")
                
                self.logger.info(f"KI-Debug-Log gespeichert: {log_file}")
            except Exception as e:
                self.logger.error(f"Fehler beim Speichern des KI-Logs: {e}")

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
    async def _run(self, messages: list, is_cancelled_callback: Callable[[], bool] = None):
        pass
