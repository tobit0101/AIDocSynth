from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, 
    QDialogButtonBox, QGroupBox, QLabel, QTabWidget, QWidget, QStackedWidget
)
from aidocsynth.services.settings_service import settings

class SettingsDialogView(QDialog):
    """
    Settings dialog view.
    The UI is created programmatically and linked to the settings manager.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self.load_settings()

    def _setup_ui(self):
        self.setWindowTitle("Einstellungen")
        self.resize(450, 300) # Adjusted size for more fields
        self.layout = QVBoxLayout(self)

        # Create and configure the tab widget
        self.tabWidget = QTabWidget()
        self.tabAllgemein = QWidget()
        self.tabKI = QWidget()
        self.tabWidget.addTab(self.tabAllgemein, "Allgemein")
        self.tabWidget.addTab(self.tabKI, "KI")
        self.layout.addWidget(self.tabWidget)

        # --- Setup KI Tab ---
        self.ki_layout = QVBoxLayout(self.tabKI)
        
        # --- LLM Provider Group ---
        llm_group_box = QGroupBox("LLM Provider")
        llm_group_layout = QVBoxLayout(llm_group_box)

        # Provider selection
        provider_form_layout = QFormLayout()
        self.cmbProvider = QComboBox()
        self.cmbProvider.setObjectName("cmbProvider")
        self.cmbProvider.addItems(["openai", "azure", "ollama"])
        provider_form_layout.addRow("Provider:", self.cmbProvider)
        llm_group_layout.addLayout(provider_form_layout)

        # Provider-specific forms in a StackedWidget
        self.stwProviderForms = QStackedWidget()
        self.stwProviderForms.setObjectName("stwProviderForms")

        # Page 0: OpenAI
        page_openai = QWidget()
        layout_openai = QFormLayout(page_openai)
        self.editOpenAIKey = QLineEdit()
        self.editOpenAIKey.setObjectName("editOpenAIKey")
        self.editOpenAIKey.setEchoMode(QLineEdit.Password)
        layout_openai.addRow("API Key:", self.editOpenAIKey)
        self.stwProviderForms.addWidget(page_openai)

        # Page 1: Azure
        page_azure = QWidget()
        layout_azure = QFormLayout(page_azure)
        self.editAzureEndpoint = QLineEdit()
        self.editAzureEndpoint.setObjectName("editEndpoint") # Match instruction
        self.editAzureDeployment = QLineEdit()
        self.editAzureDeployment.setObjectName("editDeployment")
        self.editAzureKey = QLineEdit()
        self.editAzureKey.setObjectName("editAzureKey")
        self.editAzureKey.setEchoMode(QLineEdit.Password)
        layout_azure.addRow("Endpoint:", self.editAzureEndpoint)
        layout_azure.addRow("Deployment:", self.editAzureDeployment)
        layout_azure.addRow("API Key:", self.editAzureKey)
        self.stwProviderForms.addWidget(page_azure)

        # Page 2: Ollama
        page_ollama = QWidget()
        layout_ollama = QFormLayout(page_ollama)
        self.editOHost = QLineEdit()
        self.editOHost.setObjectName("editOHost")
        self.cmbOllamaModel = QComboBox()
        self.cmbOllamaModel.setObjectName("cmbOllamaModel")
        self.cmbOllamaModel.setEditable(True)
        layout_ollama.addRow("Host:", self.editOHost)
        layout_ollama.addRow("Model:", self.cmbOllamaModel)
        self.stwProviderForms.addWidget(page_ollama)

        llm_group_layout.addWidget(self.stwProviderForms)
        self.ki_layout.addWidget(llm_group_box)
        self.ki_layout.addStretch()

        # --- Setup Allgemein Tab ---
        self.allgemein_layout = QVBoxLayout(self.tabAllgemein)
        self.allgemein_layout.addWidget(QLabel("Allgemeine Einstellungen werden hier konfiguriert."))
        self.allgemein_layout.addStretch()

        # --- Dialog Buttons ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply)
        self.layout.addWidget(self.button_box)

        # --- Connect Signals ---
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.button_box.button(QDialogButtonBox.Apply).clicked.connect(self.save_settings)

    def load_settings(self):
        """Load settings from the manager and populate the UI fields."""
        s = settings.data.llm
        self.cmbProvider.setCurrentText(s.provider)
        self.editOpenAIKey.setText(s.openai_api_key)
        self.editAzureEndpoint.setText(s.azure_endpoint)
        self.editAzureDeployment.setText(s.azure_deployment)
        self.editAzureKey.setText(s.azure_api_key)
        self.editOHost.setText(s.ollama_host)
        # The controller will populate the model list, just set the current one
        if s.ollama_model and not self.cmbOllamaModel.findText(s.ollama_model) > -1:
             self.cmbOllamaModel.addItem(s.ollama_model)
        self.cmbOllamaModel.setCurrentText(s.ollama_model)

    def save_settings(self):
        """Save settings from the UI fields to the manager."""
        s = settings.data.llm
        s.provider = self.cmbProvider.currentText()
        s.openai_api_key = self.editOpenAIKey.text()
        s.azure_endpoint = self.editAzureEndpoint.text()
        s.azure_deployment = self.editAzureDeployment.text()
        s.azure_api_key = self.editAzureKey.text()
        s.ollama_host = self.editOHost.text()
        s.ollama_model = self.cmbOllamaModel.currentText()
        settings.save()

    def accept(self):
        """Save settings and close the dialog."""
        self.save_settings()
        super().accept()
