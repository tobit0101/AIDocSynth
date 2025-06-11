from openai import AsyncOpenAI
from .base import ProviderBase, register

@register
class OpenAIProvider(ProviderBase):
    name = "openai"

    async def close(self):
        """Closes the OpenAI async client."""
        if hasattr(self, 'cli') and self.cli:
            self.logger.info("Closing OpenAI client...")
            await self.cli.close()
            self.logger.info("OpenAI client closed.")
    def __init__(self, cfg):
        super().__init__(cfg)
        self.cli = AsyncOpenAI(api_key=cfg.openai_api_key)

    async def _run(self, messages: list):
        r = await self.cli.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            response_format={"type": "json_object"}
        )
        return r.choices[0].message.content
