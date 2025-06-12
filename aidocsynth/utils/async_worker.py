from aidocsynth.utils.worker import Worker

def fetch_models_async(provider_cls, cfg):
    async def _run(signals):
        async with provider_cls(cfg) as prov:     # Provider hat __aenter__/close
            models = await prov.get_models()
            signals.result.emit(models)
    return Worker(_run)
