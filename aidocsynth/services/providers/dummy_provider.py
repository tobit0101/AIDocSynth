from .base import ProviderBase, register
import json
import asyncio
import logging

logger = logging.getLogger(__name__)

@register
class DummyProvider(ProviderBase):
    name = "openai"

    async def _run(self, messages: list) -> str:
        """Simulates a non-blocking network call."""
        logger.info(f"DummyProvider: Simulating network latency with messages: {messages}")
        await asyncio.sleep(2)  # Non-blocking sleep
        logger.info("DummyProvider: Simulation finished. Returning mock data.")
        return json.dumps({
            "targetPath": "T",
            "fileName": "x.txt"
        })
