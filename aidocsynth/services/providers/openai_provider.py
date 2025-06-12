import openai
from openai import AsyncOpenAI
from typing import List
from .base import ProviderBase, register

@register
class OpenAIProvider(ProviderBase):
    name = "openai"

    async def get_models(self, **kwargs) -> List[str]:
        """
        Fetches the list of available models from OpenAI using the client configured in this provider instance.
        Raises openai-specific exceptions on failure.
        """
        # self.cli is already an AsyncOpenAI client initialized with the API key
        if not self.cli:
            # This should ideally be caught by __init__ or a config validation
            raise ValueError("OpenAI client is not initialized. Check OpenAI API key.")

        models_response = await self.cli.models.list()
        return sorted([model.id for model in models_response.data])

    async def close(self):
        """Closes the OpenAI async client."""
        if hasattr(self, 'cli') and self.cli:
            self.logger.info("Closing OpenAI client...")
            await self.cli.close()
            self.logger.info("OpenAI client closed.")

    def __init__(self, cfg):
        super().__init__(cfg)
        self.cli = AsyncOpenAI(api_key=cfg.openai_api_key)
        self.model = cfg.openai_model

    async def _run(self, messages: list):
        r = await self.cli.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2
        )
        return r.choices[0].message.content
