from aidocsynth.utils.worker import Worker

def fetch_models_async(provider_cls, cfg):
    """Return a :class:`Worker` that asynchronously fetches the model list.

    The inner coroutine now **returns** the collected models instead of emitting
    them directly via *signals*.  The surrounding :class:`Worker` will emit the
    ``result`` signal exactly once with this return value.  This strategy keeps
    all Qt‐signal traffic in the main thread and avoids native semaphore leaks
    that can lead to segmentation faults when the worker thread shuts down.
    """

    async def _run():
        async with provider_cls(cfg) as prov:  # Provider has async context manager
            return await prov.get_models()

    return Worker(_run)
