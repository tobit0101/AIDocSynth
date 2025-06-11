from ollama import AsyncClient, ResponseError
from .base import ProviderBase, register
import logging

logger = logging.getLogger(__name__)

@register
class OllamaProvider(ProviderBase):
    name = "ollama"

    async def close(self):
        """Closes the Ollama async client."""
        if hasattr(self, 'cli') and self.cli:
            self.logger.info("Closing Ollama client...")
            await self.cli.aclose()
            self.logger.info("Ollama client closed.")
    def __init__(self, cfg):
        super().__init__(cfg)
        self.model = cfg.ollama_model
        self.cli   = AsyncClient(host=cfg.ollama_host)

    async def _run(self, messages: list):
        resp = await self.cli.chat(
            model=self.model,
            messages=messages,
            stream=False,
            options={"temperature": 0.2}
        )
        return resp["message"]["content"]

    async def list_models(self) -> list[str]:
        try:
            response_data = await self.cli.list()  # This is ollama.ListResponse
            model_entries = response_data.get('models', [])  # list of ollama.ModelResponse
            
            extracted_names = []
            for entry in model_entries:
                name = entry.get('name')  # Safely get 'name'
                if name:
                    extracted_names.append(name)
                else:
                    # If 'name' is missing, try 'model' as a fallback
                    model_tag = entry.get('model')
                    if model_tag:
                        extracted_names.append(model_tag)
                        logger.warning(
                            f"Ollama model entry missing 'name' field, used 'model' field ('{model_tag}') instead. Entry: {entry}"
                        )
                    else:
                        logger.warning(f"Ollama model entry missing both 'name' and 'model' fields. Entry: {entry}")
            
            if not extracted_names and model_entries:
                logger.info("No model names extracted from Ollama despite model entries being present. Raw entries: %s", model_entries)
            
            return extracted_names
        except ResponseError as e:
            # Log the host/base_url for easier debugging of connection issues
            host_url = self.cli._host if hasattr(self.cli, '_host') else 'N/A'
            logger.error(f"Ollama API error while listing models from {host_url}: {e}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"Unexpected error while listing Ollama models: {e}", exc_info=True)
            return []
