from PySide6.QtCore import QObject
from aidocsynth.services.settings_service import settings
from aidocsynth.services.providers.ollama_provider import OllamaProvider
import asyncio

class SettingsController(QObject):
    def __init__(self, dlg):
        super().__init__()
        self.dlg = dlg
        self.dlg.cmbProvider.currentTextChanged.connect(self._switch)
        self._switch(self.dlg.cmbProvider.currentText())

    # Umschalten der Stacked-Pages
    def _switch(self, prov: str):
        self.dlg.stwProviderForms.setCurrentIndex({"openai":0,"azure":1,"ollama":2}[prov])
        if prov == "ollama": asyncio.create_task(self._load_ollama_models())

    # Modelle per SDK abrufen
    async def _load_ollama_models(self):
        prov = OllamaProvider(settings.data.llm)
        try:
            models = await prov.list_models()
        except Exception as e:
            print(f"Could not load Ollama models: {e}")
            models = []
        self.dlg.cmbOllamaModel.clear()
        self.dlg.cmbOllamaModel.addItems(models or ["llama3"])
