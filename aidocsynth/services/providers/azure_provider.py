from openai import AsyncAzureOpenAI
from typing import List
from .base import ProviderBase, register

@register
class AzureProvider(ProviderBase):
    name = "azure"

    async def get_models(self, **kwargs) -> List[str]:
        """
        Fetches the list of available models from Azure OpenAI using the client configured in this provider instance.
        Raises openai-specific exceptions on failure.
        """
        # self.cli is already an AsyncAzureOpenAI client initialized with credentials
        if not self.cli:
            # This should ideally be caught by __init__ or a config validation
            raise ValueError("Azure client is not initialized. Check Azure settings.")

        models_response = await self.cli.models.list()
        return sorted([model.id for model in models_response.data])

    async def close(self):
        """Closes the Azure OpenAI async client."""
        if hasattr(self, 'cli') and self.cli:
            self.logger.info("Closing Azure OpenAI client...")
            await self.cli.close()
            self.logger.info("Azure OpenAI client closed.")

    def __init__(self, cfg):
        super().__init__(cfg)
        # The openai package uses AsyncAzureOpenAI and takes the api_key directly.
        # An api_version is also required for Azure, using a recent default.
        self.cli = AsyncAzureOpenAI(
            azure_endpoint=cfg.azure_endpoint,
            api_key=cfg.azure_api_key,
            api_version=cfg.azure_api_version
        )
        self.deployment = cfg.azure_deployment

    async def _run(self, messages: list):
        # For the AzureOpenAI client, the deployment name is passed as the 'model' parameter.
        r = await self.cli.chat.completions.create(
            model=self.deployment,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2
        )
        return r.choices[0].message.content
