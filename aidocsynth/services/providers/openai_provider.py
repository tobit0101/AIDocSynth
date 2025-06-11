from openai import AsyncOpenAI
from .base import ProviderBase, register

@register
class OpenAIProvider(ProviderBase):
    name = "openai"
    def __init__(self, cfg):
        super().__init__(cfg)
        self.cli = AsyncOpenAI(api_key=cfg.openai_api_key)

    async def _run(self, prompt: str):
        r = await self.cli.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return r.choices[0].message.content
