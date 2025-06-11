from ollama import AsyncClient
from .base import ProviderBase, register

@register
class OllamaProvider(ProviderBase):
    name = "ollama"
    def __init__(self, cfg):
        super().__init__(cfg)
        self.model = cfg.ollama_model
        self.cli   = AsyncClient(host=cfg.ollama_host)

    async def _run(self, prompt: str):
        resp = await self.cli.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            stream=False,
            options={"temperature": 0.2}
        )
        return resp["message"]["content"]

    async def list_models(self) -> list[str]:
        info = await self.cli.list()
        return [m["name"] for m in info.get("models", [])]
