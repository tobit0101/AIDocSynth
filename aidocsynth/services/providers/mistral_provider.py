import asyncio
from typing import List, Callable, Optional, Any

from mistralai import Mistral

from .base import ProviderBase, register

@register
class MistralProvider(ProviderBase):
    name = "mistral"

    def __init__(self, cfg):
        super().__init__(cfg)
        self.model = cfg.mistral_model
        try:
            self.cli = Mistral(api_key=cfg.mistral_api_key)
        except Exception as e:
            self.logger.error(f"Failed to initialize Mistral client: {e}", exc_info=True)
            self.cli = None

    async def close(self):
        """Clean up references."""
        self.cli = None

    async def get_models(self, **kwargs) -> List[str]:
        if not self.cli:
            raise ValueError("Mistral client is not initialized. Check Mistral API key.")

        res = await asyncio.to_thread(self.cli.models.list)
        ids = []
        if hasattr(res, 'data'):
            for m in res.data:
                if hasattr(m, 'id'):
                    ids.append(str(m.id))
        return sorted(ids)

    async def _wait_with_cancellation(self, awaitable, is_cancelled_callback: Optional[Callable[[], bool]] = None, poll: float = 0.1) -> Any:
        if not is_cancelled_callback:
            return await awaitable
        task = asyncio.create_task(awaitable)
        try:
            while not task.done():
                if is_cancelled_callback():
                    self.logger.info("Cancellation requested, aborting Mistral API call")
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        raise asyncio.CancelledError("LLM call cancelled by user request.")
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=poll)
                except asyncio.TimeoutError:
                    continue
            return task.result()
        except Exception:
            if not task.done():
                task.cancel()
            raise

    async def _run(self, messages: list, is_cancelled_callback: Callable[[], bool] = None):
        if not self.cli:
            raise ValueError("Mistral client is not initialized")

        def _do_chat():
            return self.cli.chat.complete(
                model=self.model,
                messages=messages,
                temperature=0.2,
            )
        try:
            r = await self._wait_with_cancellation(asyncio.to_thread(_do_chat), is_cancelled_callback)
            if not hasattr(r, 'choices') or not r.choices:
                raise ValueError("Mistral response missing 'choices'")
            return r.choices[0].message.content
        except asyncio.CancelledError:
            self.logger.info("Mistral API call cancelled by user.")
            raise
        except Exception as e:
            self.logger.error(f"Error during Mistral chat completion: {e}", exc_info=True)
            raise