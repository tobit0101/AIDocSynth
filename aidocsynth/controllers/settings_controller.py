from pathlib import Path
from PySide6.QtCore import QObject, Signal, Qt, QThreadPool, QUrl
from aidocsynth.services.settings_service import settings
from aidocsynth.services import providers
from aidocsynth.utils.worker import Worker
from aidocsynth.utils.connection_utils import test_provider_connection
from aidocsynth.utils.async_worker import fetch_models_async
import logging, asyncio
from PySide6.QtGui import QDesktopServices

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
        self.v.btnTestMistral.clicked.connect(lambda: self._test('mistral'))
        self.modelsReady.connect(self._populate_models)
        self.testDone.connect(self.v.show_test_result)
        self.testDone.connect(self._handle_successful_test)

        # Connect text changed signals to update button states
        self.v.editOpenAIKey.textChanged.connect(self._update_test_button_states)
        self.v.editAzureEndpoint.textChanged.connect(self._update_test_button_states)
        self.v.editAzureKey.textChanged.connect(self._update_test_button_states)
        self.v.editAzureApiVersion.textChanged.connect(self._update_test_button_states)
        self.v.editOllamaBaseUrl.textChanged.connect(self._update_test_button_states)
        self.v.editMistralKey.textChanged.connect(self._update_test_button_states)

        self.v.btnOpenLogDir.clicked.connect(self._open_log_directory)

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
        self.v.cmbProcessingMode.setCurrentText("Parallel" if s.processing_mode=="parallel" else "Seriell")
        self.v.spinMaxParallel.setValue(s.max_parallel_processes)
        self.v.spinOcrMaxPages.setValue(s.ocr_max_pages)

        self.v.chkLogPrompts.setChecked(llm.log_prompts)
        self.v.cmbProvider.setCurrentText(llm.provider)
        self.v.editOpenAIKey.setText(llm.openai_api_key or "")
        self.v.cmbOpenAIModel.setEditText(llm.openai_model)
        self.v.editAzureEndpoint     .setText(llm.azure_endpoint or "")
        self.v.editAzureDeploymentName.setText(llm.azure_deployment or "")
        self.v.editAzureKey          .setText(llm.azure_api_key or "")
        self.v.editAzureApiVersion   .setText(llm.azure_api_version)
        self.v.editOllamaBaseUrl     .setText(llm.ollama_host)
        self.v.cmbOllamaModel.setEditText(llm.ollama_model)
        self.v.chkOllamaThink.setChecked(llm.ollama_think)
        # Mistral
        if hasattr(self.v, 'editMistralKey'):
            self.v.editMistralKey.setText(llm.mistral_api_key or "")
        if hasattr(self.v, 'cmbMistralModel'):
            self.v.cmbMistralModel.setEditText(llm.mistral_model)
        self._switch_provider(llm.provider)

    def save(self):
        """View → Model"""
        s, llm = settings.data, settings.data.llm
        s.work_dir      = Path(self.v.editWorkDir.text())
        s.backup_root   = Path(self.v.editBackupRoot.text())
        s.unsorted_root = Path(self.v.editUnsortedRoot.text())
        s.create_backup = self.v.chkCreateBackup.isChecked()
        s.sort_action   = "copy" if self.v.cmbBackupAction.currentText()=="Kopieren" else "move"
        s.processing_mode = "parallel" if self.v.cmbProcessingMode.currentText()=="Parallel" else "serial"
        s.max_parallel_processes = self.v.spinMaxParallel.value()
        s.ocr_max_pages = self.v.spinOcrMaxPages.value()

        llm.log_prompts = self.v.chkLogPrompts.isChecked()
        llm.provider        = self.v.cmbProvider.currentText()
        llm.openai_api_key  = self.v.editOpenAIKey.text().strip() or None
        llm.openai_model    = self.v.cmbOpenAIModel.currentText().strip()
        llm.azure_endpoint  = self.v.editAzureEndpoint.text().strip() or None
        llm.azure_deployment= self.v.editAzureDeploymentName.text().strip() or None
        llm.azure_api_key   = self.v.editAzureKey.text().strip() or None
        llm.azure_api_version = self.v.editAzureApiVersion.text().strip() or llm.azure_api_version
        llm.ollama_host     = self.v.editOllamaBaseUrl.text().strip()
        llm.ollama_model    = self.v.cmbOllamaModel.currentText().strip()
        llm.ollama_think    = self.v.chkOllamaThink.isChecked()
        # Mistral
        if hasattr(self.v, 'editMistralKey'):
            llm.mistral_api_key = self.v.editMistralKey.text().strip() or None
        if hasattr(self.v, 'cmbMistralModel'):
            llm.mistral_model = self.v.cmbMistralModel.currentText().strip() or llm.mistral_model

        settings.save()

    # ---------------------------------------------------------------- #
    #   Interne Helfer                                                 #
    # ---------------------------------------------------------------- #
    def _switch_provider(self, provider: str):
        idx = {"openai":0, "azure":1, "ollama":2, "mistral":3}.get(provider,0)
        self.v.stwProviderForms.setCurrentIndex(idx)
        self._update_test_button_states()

        # Lazy load models if credentials are provided
        should_load = False
        if provider == "openai":
            should_load = self.v.btnTestOpenAI.isEnabled()
        elif provider == "ollama":  # Skip Azure auto-load to avoid native crash
            should_load = self.v.btnTestOllama.isEnabled()
        elif provider == "mistral":
            should_load = getattr(self.v, 'btnTestMistral', None) is not None and self.v.btnTestMistral.isEnabled()

        # For Azure we currently disable automatic model loading due to
        # stability issues that lead to segmentation faults. Users can enter
        # the deployment name manually.
        if provider == "azure":
            should_load = False

        if should_load:
            log.info(f"Credentials for '{provider}' are present, attempting to load models...")
            self._load_models(provider)

    def _load_models(self, provider: str):
        log.info(f"Lazy loading models for provider: {provider}")
        cfg = self._collect_temp_cfg()
        try:
            # Run the async fetcher directly in the main thread. This is a very
            # fast operation (single HTTP call) and avoids the segmentation
            # fault caused by asyncio/threading issues with QThreadPool.
            prov_cls = providers.get_provider(cfg).__class__
            worker = fetch_models_async(prov_cls, cfg)
            # The worker's fn is an async function, we can run it with asyncio.run
            models = asyncio.run(worker.fn())
            self.modelsReady.emit(provider, models)
        except Exception as e:
            log.error(f"Failed to load models for {provider}: {e}", exc_info=True)
            self.modelsReady.emit(provider, []) # Emit empty list on error

    def _populate_models(self, provider: str, models: list[str]):
        log.info(f"Populating model list for '{provider}' with {len(models)} models.")
        combo = {
            "openai": self.v.cmbOpenAIModel,
            "ollama": self.v.cmbOllamaModel,
            "mistral": getattr(self.v, 'cmbMistralModel', None),
        }.get(provider)

        if not combo:
            log.warning(f"Could not find a combo box for provider '{provider}' to populate.")
            return

        current = combo.currentText()
        log.debug(f"Current text in combobox for '{provider}': '{current}'")
        combo.blockSignals(True)  # Prevent editTextChanged hiding the label
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
        combo.blockSignals(False)

    # ---------------------------------------------------------------- #
    #   Connection-Test                                                #
    # ---------------------------------------------------------------- #
    def _test(self, provider: str):
        """Starts a connection test for the given provider."""
        log.info(f"Starting connection test for provider: {provider}")
        cfg = self._collect_temp_cfg()

        # Connection tests are lightweight single HTTP calls. Run them
        # synchronously in the GUI thread for all providers to avoid thread
        # teardown issues and keep the implementation simple.
        try:
            success, message = asyncio.run(test_provider_connection(cfg))
        except Exception as exc:
            success, message = False, str(exc)

        if success and not message:
            message = "Erfolgreich"

        self.testDone.emit(provider, success, message)

        # On success, immediately refresh model list for providers that support
        # dynamic models. (Azure requires deployment name, so we skip it.)
        if success and provider in ("openai", "ollama", "mistral"):
            self._load_models(provider)

    # ---------------------------------------------------------------- #
    def _handle_successful_test(self, provider: str, success: bool, message: str):
        """If a test is successful, (re)load the models for that provider."""
        if success and provider in ("openai", "ollama", "mistral"):
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
        
        # Mistral
        mistral_ready = bool(getattr(self.v, 'editMistralKey', None) and self.v.editMistralKey.text().strip())
        if getattr(self.v, 'btnTestMistral', None):
            self.v.btnTestMistral.setEnabled(mistral_ready)

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
            ollama_model    = self.v.cmbOllamaModel.currentText().strip() or "llama3",
            ollama_think    = self.v.chkOllamaThink.isChecked(),
            log_prompts     = self.v.chkLogPrompts.isChecked(),
            mistral_api_key = (self.v.editMistralKey.text().strip() if getattr(self.v, 'editMistralKey', None) else None),
            mistral_model   = (self.v.cmbMistralModel.currentText().strip() if getattr(self.v, 'cmbMistralModel', None) else "mistral-small-latest"),
        )

    def _open_log_directory(self):
        """Öffnet den Logging-Ordner im Standard-Dateibrowser des Systems."""
        log_dir = Path.home() / ".config" / "AIDocSynth" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_dir)))