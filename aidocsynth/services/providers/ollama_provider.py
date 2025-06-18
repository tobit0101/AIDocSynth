from ollama import AsyncClient, ResponseError
from .base import ProviderBase, register
import logging
from typing import List

logger = logging.getLogger(__name__)

@register
class OllamaProvider(ProviderBase):
    name = "ollama"

    async def get_models(self, **kwargs) -> List[str]:
        logger.debug(f"OllamaProvider get_models called. self type: {type(self)}")
        """
        Fetches the list of available models from the Ollama host configured in this provider instance.
        Raises ollama.ResponseError on failure.
        """
        if not self.host: # Check if the provider instance has a host configured
            # This case should ideally be caught during __init__ or by a config validation
            raise ValueError("Ollama host URL is not configured for this provider instance.")
        
        # self.cli is already an AsyncClient initialized with the host
        models_data = await self.cli.list()
        
        model_names = []
        for model_info in models_data.get('models', []):
            # The API can return 'name' or 'model', prefer 'name'
            name = model_info.get('name')
            if not name:
                name = model_info.get('model')
            if name:
                # Explicitly cast to string to prevent memory issues with C-level pointers
                # that might be returned by the library, causing segfaults in Qt.
                model_names.append(str(name))

        return sorted(model_names)

    async def close(self):
        """Closes the Ollama async client, with resilience for missing aclose method."""
        if hasattr(self, 'cli') and self.cli:
            client_instance = self.cli
            client_type = type(client_instance)
            self.logger.info(f"Attempting to close Ollama client (type: {client_type})...")
            if hasattr(client_instance, 'aclose') and callable(client_instance.aclose):
                try:
                    await client_instance.aclose()
                    self.logger.info("Ollama client closed successfully via aclose().")
                except Exception as e:
                    self.logger.error(f"Error during Ollama client aclose(): {e}", exc_info=True)
            elif hasattr(client_instance, '__aexit__') and callable(client_instance.__aexit__):
                self.logger.warning(f"Ollama client (type: {client_type}) lacks 'aclose' method. Attempting close via async context manager __aexit__.")
                try:
                    await client_instance.__aexit__(None, None, None)
                    self.logger.info("Ollama client context exited successfully via __aexit__.")
                except Exception as e:
                    self.logger.error(f"Error during Ollama client __aexit__: {e}", exc_info=True)
            else:
                self.logger.warning(f"Ollama client (type: {client_type}) does not have a callable 'aclose' or '__aexit__' method. Client may not be closed properly.")
            # To prevent further issues if the client object is in a bad state, nullify it.
            # self.cli = None # Consider if this is appropriate for your resource management strategy
        else:
            self.logger.info("No active Ollama client (self.cli) to close.")

    def __init__(self, cfg):
        logger.debug(f"OllamaProvider __init__ called. self type: {type(self)}, cfg type: {type(cfg)}")
        super().__init__(cfg)
        self.model = cfg.ollama_model
        self.host = cfg.ollama_host
        self.cli   = AsyncClient(host=self.host)

    async def _run(self, messages: list):
        resp = await self.cli.chat(
            model=self.model,
            messages=messages,
            stream=False,
            format="json",
            options={"temperature": 0.2}
        )
        return resp["message"]["content"]

    async def list_models(self) -> list[str]:
        try:
            response_data = await self.cli.list()  # This is ollama.ListResponse
            model_entries = response_data.get('models', [])  # list of ollama.ModelResponse
            
            extracted_names = []
            for entry in model_entries:
                model_name = entry.get('name') or entry.get('model')
                if model_name:
                    extracted_names.append(model_name)
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
