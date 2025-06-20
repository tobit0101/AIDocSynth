import asyncio
from typing import List, Callable

import openai
from openai import AsyncOpenAI

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

    async def _wait_with_cancellation(self, awaitable, is_cancelled_callback: Callable[[], bool]):
        """
        Awaits an async task with periodic checks for cancellation.
        """
        task = asyncio.create_task(awaitable)
        while not task.done():
            if is_cancelled_callback and is_cancelled_callback():
                task.cancel()
                self.logger.info("Cancellation requested, aborting OpenAI API call")
                try:
                    await task
                except asyncio.CancelledError:
                    raise  # Re-raise the cancellation
                except Exception as e:
                    self.logger.error(f"Exception after task cancellation: {e}")
                    raise asyncio.CancelledError("LLM call cancelled by user request.")
            try:
                # Wait for task completion or timeout
                await asyncio.wait_for(asyncio.shield(task), timeout=0.1)
            except asyncio.TimeoutError:
                continue  # Timeout is expected, continue checking for cancellation
        return task.result()

    async def _run(self, messages: list, is_cancelled_callback: Callable[[], bool] = None):
        chat_call = self.cli.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2
        )

        try:
            r = await self._wait_with_cancellation(chat_call, is_cancelled_callback)
            return r.choices[0].message.content
        except asyncio.CancelledError:
            self.logger.info("OpenAI API call cancelled by user.")
            raise
