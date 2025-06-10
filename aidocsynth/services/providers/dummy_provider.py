from .base import ProviderBase, register
import json
@register
class DummyProvider(ProviderBase):
    name = "openai"
    async def _run(self, prompt): return json.dumps({"targetPath":"Test","fileName":"dummy.txt"})
