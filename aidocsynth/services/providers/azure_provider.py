from openai import AzureOpenAI
from .base import ProviderBase, register

@register
class AzureProvider(ProviderBase):
    name = "azure"
    def __init__(self, cfg):
        super().__init__(cfg)
        # The openai package uses AzureOpenAI and takes the api_key directly.
        # An api_version is also required for Azure, using a recent default.
        self.cli = AzureOpenAI(
            azure_endpoint=cfg.azure_endpoint,
            api_key=cfg.azure_api_key,
            api_version="2024-02-01" 
        )
        self.deployment = cfg.azure_deployment

    async def _run(self, prompt: str):
        # For the AzureOpenAI client, the deployment name is passed as the 'model' parameter.
        r = await self.cli.chat.completions.create(
            model=self.deployment,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return r.choices[0].message.content
