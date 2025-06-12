import logging
from typing import Tuple

from aidocsynth.models.settings import LLMSettings
from aidocsynth.services import providers

log = logging.getLogger(__name__)

async def test_provider_connection(cfg: LLMSettings) -> Tuple[bool, str]:
    """
    Tests the connection to the specified LLM provider using the given settings.

    Args:
        cfg: An LLMSettings object containing the provider and credentials.

    Returns:
        A tuple containing a boolean indicating success and a string message.
    """
    provider_name = cfg.provider
    log.debug(f"Testing connection for provider '{provider_name}'...")

    try:
        prov_cls = providers.get_provider(cfg).__class__
        log.debug(f"Using provider class '{prov_cls.__name__}' with config: {cfg}")

        async with prov_cls(cfg) as p:
            # A model list fetch is a sufficient connection test for all providers.
            await p.get_models()
        
        log.info(f"Connection test for '{provider_name}' successful.")
        return True, "Verbindung erfolgreich."

    except Exception as e:
        log.warning(f"Connection test for '{provider_name}' failed: {e}", exc_info=True)
        # Return a user-friendly, concise error message.
        error_message = str(e).split('\n')[0] # Often the first line is the most relevant
        return False, f"Fehler: {error_message}"
