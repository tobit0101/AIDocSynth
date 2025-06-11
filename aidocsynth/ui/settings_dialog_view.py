from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QComboBox, 
    QDialogButtonBox, QGroupBox, QWidget, QStackedWidget, QLabel,
    QPushButton, QHBoxLayout
)
from aidocsynth.services.settings_service import settings

class SettingsDialogView(QDialog):
    """
    Settings dialog view.
    The UI is created programmatically and linked to the settings manager.
    All settings are on a single page, organized by groups.
    Labels are above input fields, and fields use full width.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self.load_settings()

    def _setup_ui(self):
        self.setWindowTitle("Einstellungen")
        self.resize(450, 600) # Adjusted size for more fields and new layout
        self.layout = QVBoxLayout(self)

        # --- Allgemein Group ---
        allgemein_group_box = QGroupBox("Allgemein")
        allgemein_group_box.setStyleSheet("QGroupBox { font-weight: bold; font-size: 11pt; }")
        allgemein_layout = QVBoxLayout(allgemein_group_box)
        allgemein_layout.setContentsMargins(10, 20, 10, 10) # Add space below title
        allgemein_layout.setSpacing(4) # Reduce space between label and input

        # Work Directory
        allgemein_layout.addWidget(QLabel("Arbeitsverzeichnis:"))
        work_dir_layout = QHBoxLayout()
        self.editWorkDir = QLineEdit()
        self.editWorkDir.setObjectName("editWorkDir")
        self.btnWorkDir = QPushButton("...")
        self.btnWorkDir.setFixedWidth(40)
        work_dir_layout.addWidget(self.editWorkDir)
        work_dir_layout.addWidget(self.btnWorkDir)
        allgemein_layout.addLayout(work_dir_layout)

        # Backup Directory
        allgemein_layout.addWidget(QLabel("Backup-Verzeichnis:"))
        backup_dir_layout = QHBoxLayout()
        self.editBackupRoot = QLineEdit()
        self.editBackupRoot.setObjectName("editBackupRoot")
        self.btnBackupRoot = QPushButton("...")
        self.btnBackupRoot.setFixedWidth(40)
        backup_dir_layout.addWidget(self.editBackupRoot)
        backup_dir_layout.addWidget(self.btnBackupRoot)
        allgemein_layout.addLayout(backup_dir_layout)

        # Unsorted Directory
        allgemein_layout.addWidget(QLabel("Unsortiert-Verzeichnis:"))
        unsort_dir_layout = QHBoxLayout()
        self.editUnsortedRoot = QLineEdit()
        self.editUnsortedRoot.setObjectName("editUnsortedRoot")
        self.btnUnsortedRoot = QPushButton("...")
        self.btnUnsortedRoot.setFixedWidth(40)
        unsort_dir_layout.addWidget(self.editUnsortedRoot)
        unsort_dir_layout.addWidget(self.btnUnsortedRoot)
        allgemein_layout.addLayout(unsort_dir_layout)
        self.layout.addWidget(allgemein_group_box)

        # --- LLM Provider Group ---
        llm_group_box = QGroupBox("KI-Provider")
        llm_group_box.setStyleSheet("QGroupBox { font-weight: bold; font-size: 11pt; }")
        llm_group_layout = QVBoxLayout(llm_group_box)
        llm_group_layout.setContentsMargins(10, 20, 10, 10) # Add space below title
        llm_group_layout.setSpacing(4) # Reduce space between label and input

        # Provider selection
        llm_group_layout.addWidget(QLabel("Provider:"))
        self.cmbProvider = QComboBox()
        self.cmbProvider.setObjectName("cmbProvider")
        self.cmbProvider.addItems(["openai", "azure", "ollama"])
        llm_group_layout.addWidget(self.cmbProvider)

        # Provider-specific forms in a StackedWidget
        self.stwProviderForms = QStackedWidget()
        self.stwProviderForms.setObjectName("stwProviderForms")

        # Page 0: OpenAI
        page_openai = QWidget()
        layout_openai = QVBoxLayout(page_openai) # Changed to QVBoxLayout
        layout_openai.setContentsMargins(0, 0, 0, 0)
        layout_openai.addWidget(QLabel("API Key:"))
        self.editOpenAIKey = QLineEdit()
        self.editOpenAIKey.setObjectName("editOpenAIKey")
        self.editOpenAIKey.setEchoMode(QLineEdit.Password)
        layout_openai.addWidget(self.editOpenAIKey)
        self.stwProviderForms.addWidget(page_openai)

        # Page 1: Azure
        page_azure = QWidget()
        layout_azure = QVBoxLayout(page_azure) # Changed to QVBoxLayout
        layout_azure.setContentsMargins(0, 0, 0, 0)
        layout_azure.addWidget(QLabel("Endpoint:"))
        self.editAzureEndpoint = QLineEdit()
        self.editAzureEndpoint.setObjectName("editEndpoint")
        layout_azure.addWidget(self.editAzureEndpoint)
        layout_azure.addWidget(QLabel("Deployment:"))
        self.editAzureDeployment = QLineEdit()
        self.editAzureDeployment.setObjectName("editDeployment")
        layout_azure.addWidget(self.editAzureDeployment)
        layout_azure.addWidget(QLabel("API Key:"))
        self.editAzureKey = QLineEdit()
        self.editAzureKey.setObjectName("editAzureKey")
        self.editAzureKey.setEchoMode(QLineEdit.Password)
        layout_azure.addWidget(self.editAzureKey)
        self.stwProviderForms.addWidget(page_azure)

        # Page 2: Ollama
        page_ollama = QWidget()
        layout_ollama = QVBoxLayout(page_ollama) # Changed to QVBoxLayout
        layout_ollama.setContentsMargins(0, 0, 0, 0)
        layout_ollama.addWidget(QLabel("Host:"))
        self.editOHost = QLineEdit()
        self.editOHost.setObjectName("editOHost")
        layout_ollama.addWidget(self.editOHost)
        layout_ollama.addWidget(QLabel("Model:"))
        self.cmbOllamaModel = QComboBox()
        self.cmbOllamaModel.setObjectName("cmbOllamaModel")
        self.cmbOllamaModel.setEditable(True)
        layout_ollama.addWidget(self.cmbOllamaModel)
        self.stwProviderForms.addWidget(page_ollama)

        llm_group_layout.addWidget(self.stwProviderForms)
        self.layout.addWidget(llm_group_box)

        self.layout.addStretch()

        # --- Dialog Buttons ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply)
        self.layout.addWidget(self.button_box)

        # --- Connect Signals ---
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.button_box.button(QDialogButtonBox.Apply).clicked.connect(self.save_settings)

    def load_settings(self):
        """Load settings from the manager and populate the UI fields."""
        # Load general settings
        app_s = settings.data
        self.editWorkDir.setText(str(app_s.work_dir))
        self.editBackupRoot.setText(str(app_s.backup_root))
        self.editUnsortedRoot.setText(str(app_s.unsorted_root))

        # Load LLM settings
        llm_s = settings.data.llm
        self.cmbProvider.setCurrentText(llm_s.provider)
        self.editOpenAIKey.setText(llm_s.openai_api_key)
        self.editAzureEndpoint.setText(llm_s.azure_endpoint)
        self.editAzureDeployment.setText(llm_s.azure_deployment)
        self.editAzureKey.setText(llm_s.azure_api_key)
        self.editOHost.setText(llm_s.ollama_host)
        
        # The controller will populate the model list, just set the current one
        if llm_s.ollama_model and not self.cmbOllamaModel.findText(llm_s.ollama_model) > -1:
             self.cmbOllamaModel.addItem(llm_s.ollama_model)
        self.cmbOllamaModel.setCurrentText(llm_s.ollama_model)

    def save_settings(self):
        """Save settings from the UI fields to the manager."""
        # Save general settings
        app_s = settings.data
        app_s.work_dir = Path(self.editWorkDir.text())
        app_s.backup_root = Path(self.editBackupRoot.text())
        app_s.unsorted_root = Path(self.editUnsortedRoot.text())

        # Save LLM settings
        llm_s = settings.data.llm
        llm_s.provider = self.cmbProvider.currentText()
        llm_s.openai_api_key = self.editOpenAIKey.text()
        llm_s.azure_endpoint = self.editAzureEndpoint.text()
        llm_s.azure_deployment = self.editAzureDeployment.text()
        llm_s.azure_api_key = self.editAzureKey.text()
        llm_s.ollama_host = self.editOHost.text()
        llm_s.ollama_model = self.cmbOllamaModel.currentText()
        settings.save()

    def accept(self):
        """Save settings and close the dialog."""
        self.save_settings()
        super().accept()
