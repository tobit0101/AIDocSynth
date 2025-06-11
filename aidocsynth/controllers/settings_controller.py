from PySide6.QtCore import QObject, Signal, QThread
from PySide6.QtWidgets import QFileDialog, QLineEdit
import logging
from functools import partial

from aidocsynth.services.settings_service import settings
from aidocsynth.services.providers.ollama_provider import OllamaProvider
import asyncio

logger = logging.getLogger(__name__)

class OllamaModelsFetcherThread(QThread):
    modelsFetched = Signal(list)

    def __init__(self, llm_settings, parent=None):
        super().__init__(parent)
        self.llm_settings = llm_settings
        self._loop = None # Store the loop to close it later

    async def _fetch_models_async(self):
        prov = OllamaProvider(self.llm_settings)
        try:
            models = await prov.list_models()
            return models
        except Exception as e:
            logger.error(f"Could not load Ollama models: {e}", exc_info=True)
            return []

    def run(self):
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            models = self._loop.run_until_complete(self._fetch_models_async())
            self.modelsFetched.emit(models or ["llama3"])
        except RuntimeError as e:
            logger.warning(f"RuntimeError in OllamaModelsFetcherThread, trying existing loop: {e}")
            try:
                self._loop = asyncio.get_event_loop()
                if not self._loop.is_running(): # Ensure we only run if not already running
                    models = self._loop.run_until_complete(self._fetch_models_async())
                    self.modelsFetched.emit(models or ["llama3"])
                else:
                    logger.warning("Existing loop is already running, cannot fetch models.")
                    self.modelsFetched.emit(["llama3"]) # Fallback
            except Exception as ex_inner:
                logger.error(f"Failed to fetch Ollama models even with existing loop: {ex_inner}", exc_info=True)
                self.modelsFetched.emit(["llama3"]) # Fallback
        except Exception as ex_outer:
            logger.error(f"Failed to fetch Ollama models: {ex_outer}", exc_info=True)
            self.modelsFetched.emit(["llama3"]) # Fallback
        finally:
            if self._loop and not self._loop.is_closed():
                self._loop.close()
                logger.debug("Asyncio loop in OllamaModelsFetcherThread closed.")

class SettingsController(QObject):
    ollamaModelsLoaded = Signal(list)

    def __init__(self, dlg):
        super().__init__()
        self.dlg = dlg
        self.fetcher_thread = None

        self.ollamaModelsLoaded.connect(self._update_ollama_models_combo)
        self.dlg.cmbProvider.currentTextChanged.connect(self._switch)

        # Connect directory selection buttons
        self.dlg.btnWorkDir.clicked.connect(partial(self._select_directory, self.dlg.editWorkDir))
        self.dlg.btnBackupRoot.clicked.connect(partial(self._select_directory, self.dlg.editBackupRoot))
        self.dlg.btnUnsortedRoot.clicked.connect(partial(self._select_directory, self.dlg.editUnsortedRoot))

        self._switch(self.dlg.cmbProvider.currentText()) # Initial call

    def __del__(self):
        logger.debug(f"SettingsController {id(self)} is being deleted. Cleaning up fetcher thread.")
        self.cleanup()

    def cleanup(self):
        if hasattr(self, 'fetcher_thread') and self.fetcher_thread:
            try:
                if self.fetcher_thread.isRunning():
                    logger.info("Stopping Ollama models fetcher thread...")
                    self.fetcher_thread.quit() # Signal the thread to finish its event loop (if any)
                    # Wait for the thread to finish. Timeout after 5 seconds.
                    if not self.fetcher_thread.wait(5000): 
                        logger.warning("Ollama models fetcher thread did not finish gracefully. Terminating.")
                        self.fetcher_thread.terminate() # Forcefully terminate if it doesn't stop
                        self.fetcher_thread.wait() # Wait for termination to complete
                    else:
                        logger.info("Ollama models fetcher thread finished gracefully.")
            except RuntimeError:
                # This can happen if the C++ part of the QThread object is already deleted
                # by Qt's parent-child mechanism before this cleanup method is called.
                logger.warning("Could not clean up fetcher thread, it was likely already deleted.")
            finally:
                self.fetcher_thread = None # Clear the reference to allow GC

    def _switch(self, prov: str):
        self.dlg.stwProviderForms.setCurrentIndex({"openai":0,"azure":1,"ollama":2}[prov])
        if prov == "ollama":
            self._load_ollama_models_threaded()

    def _load_ollama_models_threaded(self):
        if self.fetcher_thread and self.fetcher_thread.isRunning():
            logger.debug("Ollama models fetcher thread already running. Not starting a new one.")
            return 
        self.fetcher_thread = OllamaModelsFetcherThread(settings.data.llm, self) # Parent is self
        self.fetcher_thread.modelsFetched.connect(self.ollamaModelsLoaded)
        self.fetcher_thread.start()

    def _update_ollama_models_combo(self, models):
        current_model = self.dlg.cmbOllamaModel.currentText()
        self.dlg.cmbOllamaModel.clear()
        self.dlg.cmbOllamaModel.addItems(models)
        if current_model in models:
            self.dlg.cmbOllamaModel.setCurrentText(current_model)
        elif models:
            self.dlg.cmbOllamaModel.setCurrentIndex(0)

    def _select_directory(self, line_edit_widget: QLineEdit):
        """Opens a dialog to select a directory and updates the line edit."""
        # Use the current path in the line edit as the starting directory
        start_dir = line_edit_widget.text()
        if not start_dir:
            start_dir = "/"

        directory = QFileDialog.getExistingDirectory(
            self.dlg, # Parent
            "Verzeichnis auswählen",
            start_dir
        )
        if directory:
            line_edit_widget.setText(directory)

