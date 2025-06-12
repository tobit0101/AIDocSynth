from pathlib import Path
from PySide6.QtCore import QObject, Signal, Qt, QThreadPool
from aidocsynth.services.settings_service import settings
from aidocsynth.services import providers
from aidocsynth.utils.worker import Worker
from aidocsynth.utils.connection_utils import test_provider_connection
from aidocsynth.utils.async_worker import fetch_models_async
import logging, asyncio

log = logging.getLogger(__name__)

class SettingsController(QObject):
    modelsReady = Signal(str, list)           # provider, model-liste
    testDone    = Signal(str, bool, str)      # provider, ok, msg

    def __init__(self, view):
        super().__init__(view)
        self.v  = view
        self._pool = QThreadPool.globalInstance()

        # UI-Bindings
        self.v.cmbProvider.currentTextChanged.connect(self._switch_provider)
        self.v.btnTestOpenAI.clicked .connect(lambda: self._test('openai'))
        self.v.btnTestAzure.clicked  .connect(lambda: self._test('azure'))
        self.v.btnTestOllama.clicked .connect(lambda: self._test('ollama'))
        self.modelsReady.connect(self._populate_models)
        self.testDone.connect(self.v.show_test_result)
        self.testDone.connect(self._handle_successful_test)

        # Connect text changed signals to update button states
        self.v.editOpenAIKey.textChanged.connect(self._update_test_button_states)
        self.v.editAzureEndpoint.textChanged.connect(self._update_test_button_states)
        self.v.editAzureKey.textChanged.connect(self._update_test_button_states)
        self.v.editAzureApiVersion.textChanged.connect(self._update_test_button_states)
        self.v.editOllamaBaseUrl.textChanged.connect(self._update_test_button_states)

        self.load()
        self._update_test_button_states() # Set initial state

    # ---------------------------------------------------------------- #
    #   Public API                                                     #
    # ---------------------------------------------------------------- #
    def load(self):
        """Model → View"""
        s, llm = settings.data, settings.data.llm
        self.v.editWorkDir.setText(str(s.work_dir))
        self.v.editBackupRoot.setText(str(s.backup_root))
        self.v.editUnsortedRoot.setText(str(s.unsorted_root))
        self.v.chkCreateBackup.setChecked(s.create_backup)
        self.v.cmbBackupAction.setCurrentText("Kopieren" if s.sort_action=="copy" else "Verschieben")

        self.v.cmbProvider.setCurrentText(llm.provider)
        self.v.editOpenAIKey.setText(llm.openai_api_key or "")
        self.v.cmbOpenAIModel.setEditText(llm.openai_model)
        self.v.editAzureEndpoint     .setText(llm.azure_endpoint or "")
        self.v.editAzureDeploymentName.setText(llm.azure_deployment or "")
        self.v.editAzureKey          .setText(llm.azure_api_key or "")
        self.v.editAzureApiVersion   .setText(llm.azure_api_version)
        self.v.editOllamaBaseUrl     .setText(llm.ollama_host)
        self.v.cmbOllamaModel.setEditText(llm.ollama_model)
        self._switch_provider(llm.provider)

    def save(self):
        """View → Model"""
        s, llm = settings.data, settings.data.llm
        s.work_dir      = Path(self.v.editWorkDir.text())
        s.backup_root   = Path(self.v.editBackupRoot.text())
        s.unsorted_root = Path(self.v.editUnsortedRoot.text())
        s.create_backup = self.v.chkCreateBackup.isChecked()
        s.sort_action   = "copy" if self.v.cmbBackupAction.currentText()=="Kopieren" else "move"

        llm.provider        = self.v.cmbProvider.currentText()
        llm.openai_api_key  = self.v.editOpenAIKey.text().strip() or None
        llm.openai_model    = self.v.cmbOpenAIModel.currentText().strip()
        llm.azure_endpoint  = self.v.editAzureEndpoint.text().strip() or None
        llm.azure_deployment= self.v.editAzureDeploymentName.text().strip() or None
        llm.azure_api_key   = self.v.editAzureKey.text().strip() or None
        llm.azure_api_version = self.v.editAzureApiVersion.text().strip() or llm.azure_api_version
        llm.ollama_host     = self.v.editOllamaBaseUrl.text().strip()
        llm.ollama_model    = self.v.cmbOllamaModel.currentText().strip()

        settings.save()

    # ---------------------------------------------------------------- #
    #   Interne Helfer                                                 #
    # ---------------------------------------------------------------- #
    def _switch_provider(self, provider: str):
        idx = {"openai":0, "azure":1, "ollama":2}.get(provider,0)
        self.v.stwProviderForms.setCurrentIndex(idx)
        self._update_test_button_states()

        # Lazy load models if credentials are provided
        should_load = False
        if provider == "openai":
            should_load = self.v.btnTestOpenAI.isEnabled()
        elif provider == "azure":
            should_load = self.v.btnTestAzure.isEnabled()
        elif provider == "ollama":
            should_load = self.v.btnTestOllama.isEnabled()

        if should_load:
            log.info(f"Credentials for '{provider}' are present, attempting to load models...")
            self._load_models(provider)

    def _load_models(self, provider: str):
        log.info(f"Lazy loading models for provider: {provider}")
        cfg = self._collect_temp_cfg()
        prov_cls = providers.get_provider(cfg).__class__
        log.debug(f"Using provider class '{prov_cls.__name__}' for model loading.")
        worker = fetch_models_async(prov_cls, cfg)
        worker.sig.result.connect(lambda models: self.modelsReady.emit(provider, models))
        self._pool.start(worker)

    def _populate_models(self, provider: str, models: list[str]):
        log.info(f"Populating model list for '{provider}' with {len(models)} models.")
        combo = {
            "openai": self.v.cmbOpenAIModel,
            "ollama": self.v.cmbOllamaModel
        }.get(provider)

        if not combo:
            log.warning(f"Could not find a combo box for provider '{provider}' to populate.")
            return

        current = combo.currentText()
        log.debug(f"Current text in combobox for '{provider}': '{current}'")
        combo.clear()
        if models:
            combo.addItems(models)
            log.debug(f"Added {len(models)} models to combobox for '{provider}'.")
            if current in models:
                combo.setCurrentText(current)
                log.debug(f"Restored current selection to '{current}'.")
            else:
                combo.setCurrentText(models[0])
                log.debug(f"Set selection to first model in list: '{models[0]}'.")
        else:
            log.warning(f"Received an empty model list for provider '{provider}'. Combobox is empty.")

    # ---------------------------------------------------------------- #
    #   Connection-Test                                                #
    # ---------------------------------------------------------------- #
    def _test(self, provider: str):
        log.info(f"Starting connection test for provider: {provider}")
        cfg = self._collect_temp_cfg()

        async def _run(signals):
            success, message = await test_provider_connection(cfg)
            signals.result.emit((success, message))

        worker = Worker(_run)
        worker.sig.result.connect(lambda res: self.testDone.emit(provider, *res))
        self._pool.start(worker)

    # ---------------------------------------------------------------- #
    def _handle_successful_test(self, provider: str, success: bool, message: str):
        """If a test is successful, (re)load the models for that provider."""
        if success:
            log.info(f"Connection test for '{provider}' was successful, refreshing model list.")
            self._load_models(provider)

    def _update_test_button_states(self):
        """Enables or disables the test buttons based on required fields."""
        # OpenAI
        openai_ready = bool(self.v.editOpenAIKey.text().strip())
        self.v.btnTestOpenAI.setEnabled(openai_ready)

        # Azure
        azure_ready = all([
            self.v.editAzureEndpoint.text().strip(),
            self.v.editAzureKey.text().strip(),
            self.v.editAzureApiVersion.text().strip(),
        ])
        self.v.btnTestAzure.setEnabled(azure_ready)

        # Ollama
        ollama_ready = bool(self.v.editOllamaBaseUrl.text().strip())
        self.v.btnTestOllama.setEnabled(ollama_ready)

    def _collect_temp_cfg(self):
        """Liest aktuelle UI-Werte in ein frisches `LLMSettings`-Objekt."""
        from aidocsynth.models.settings import LLMSettings
        return LLMSettings(
            provider        = self.v.cmbProvider.currentText(),
            openai_api_key  = self.v.editOpenAIKey.text().strip() or None,
            openai_model    = self.v.cmbOpenAIModel.currentText().strip() or "gpt-4o-mini",
            azure_endpoint  = self.v.editAzureEndpoint.text().strip() or None,
            azure_deployment= self.v.editAzureDeploymentName.text().strip() or None,
            azure_api_key   = self.v.editAzureKey.text().strip() or None,
            azure_api_version = self.v.editAzureApiVersion.text().strip() or "2024-02-01",
            ollama_host     = self.v.editOllamaBaseUrl.text().strip(),
            ollama_model    = self.v.cmbOllamaModel.currentText().strip() or "llama3"
        )

