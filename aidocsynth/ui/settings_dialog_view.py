from pathlib import Path
from PySide6.QtWidgets import (
    QApplication,
    QDialog, QVBoxLayout, QLineEdit, QComboBox, 
    QDialogButtonBox, QGroupBox, QWidget, QStackedWidget, QLabel,
    QPushButton, QHBoxLayout, QCheckBox, QFormLayout, QSpinBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt
from aidocsynth.services.settings_service import settings
from aidocsynth.controllers.settings_controller import SettingsController

class SettingsDialogView(QDialog):
    """
    Settings dialog view.
    The UI is created programmatically and linked to the settings manager.
    All settings are on a single page, organized by groups.
    Form layout is used for better alignment and visual hierarchy.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self.controller = SettingsController(self)
        # self.controller.load() # Load is now called from controller's __init__

    def _setup_ui(self):
        self.setWindowTitle("Einstellungen")
        self.resize(480, 620)  # Slightly wider for better readability
        
        # Set up main layout with proper margins
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 15, 15, 15)
        self.layout.setSpacing(12)  # Increased spacing between group boxes

        # --- Allgemein Group ---
        allgemein_group_box = self._create_group_box("Allgemein")
        allgemein_layout = QFormLayout()
        allgemein_layout.setLabelAlignment(Qt.AlignLeft)
        allgemein_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        allgemein_layout.setSpacing(8)  # Spacing between form rows

        # Work Directory
        self.editWorkDir = QLineEdit()
        self.editWorkDir.setObjectName("editWorkDir")
        self.btnWorkDir = QPushButton("...")
        self.btnWorkDir.setFixedWidth(40)
        work_dir_layout = QHBoxLayout()
        work_dir_layout.setSpacing(6)
        work_dir_layout.addWidget(self.editWorkDir)
        work_dir_layout.addWidget(self.btnWorkDir)
        allgemein_layout.addRow("Arbeitsverzeichnis:", work_dir_layout)

        # Backup Directory
        self.editBackupRoot = QLineEdit()
        self.editBackupRoot.setObjectName("editBackupRoot")
        self.btnBackupRoot = QPushButton("...")
        self.btnBackupRoot.setFixedWidth(40)
        backup_dir_layout = QHBoxLayout()
        backup_dir_layout.setSpacing(6)
        backup_dir_layout.addWidget(self.editBackupRoot)
        backup_dir_layout.addWidget(self.btnBackupRoot)
        allgemein_layout.addRow("Backup-Verzeichnis:", backup_dir_layout)

        # Unsorted Directory
        self.editUnsortedRoot = QLineEdit()
        self.editUnsortedRoot.setObjectName("editUnsortedRoot")
        self.btnUnsortedRoot = QPushButton("...")
        self.btnUnsortedRoot.setFixedWidth(40)
        unsort_dir_layout = QHBoxLayout()
        unsort_dir_layout.setSpacing(6)
        unsort_dir_layout.addWidget(self.editUnsortedRoot)
        unsort_dir_layout.addWidget(self.btnUnsortedRoot)
        allgemein_layout.addRow("Unsortiert-Verzeichnis:", unsort_dir_layout)

        # Create Backup Toggle
        self.chkCreateBackup = QCheckBox()
        self.chkCreateBackup.setObjectName("chkCreateBackup")
        allgemein_layout.addRow("Backup erstellen:", self.chkCreateBackup)

        # Sort Action Dropdown
        self.cmbBackupAction = QComboBox()
        self.cmbBackupAction.setObjectName("cmbBackupAction")
        self.cmbBackupAction.addItems(["Kopieren", "Verschieben"])
        allgemein_layout.addRow("Aktion für Originaldatei:", self.cmbBackupAction)

        # Processing Mode Dropdown
        self.cmbProcessingMode = QComboBox()
        self.cmbProcessingMode.setObjectName("cmbProcessingMode")
        self.cmbProcessingMode.addItems(["Parallel", "Seriell"])
        allgemein_layout.addRow("Verarbeitungsmodus:", self.cmbProcessingMode)

        # Max Parallel Processes
        self.spinMaxParallel = QSpinBox()
        self.spinMaxParallel.setObjectName("spinMaxParallel")
        self.spinMaxParallel.setMinimum(1)
        self.spinMaxParallel.setMaximum(32)  # Sensible upper limit
        self.spinMaxParallel.setToolTip("Anzahl der Dokumente, die gleichzeitig verarbeitet werden sollen.")
        allgemein_layout.addRow("Maximale parallele Prozesse:", self.spinMaxParallel)

        # OCR Max Pages
        self.spinOcrMaxPages = QSpinBox()
        self.spinOcrMaxPages.setObjectName("spinOcrMaxPages")
        self.spinOcrMaxPages.setMinimum(1)
        self.spinOcrMaxPages.setMaximum(100) # Or a higher sensible limit
        # Default value will be set by the controller during load
        allgemein_layout.addRow("Maximale OCR-Seiten:", self.spinOcrMaxPages)

        allgemein_group_box.setLayout(allgemein_layout)
        self.layout.addWidget(allgemein_group_box)

        # --- LLM Provider Group ---
        llm_group_box = self._create_group_box("KI-Provider")
        llm_group_layout = QVBoxLayout()
        llm_group_layout.setSpacing(10)
        
        # Provider selection with form layout for better alignment
        provider_form = QFormLayout()
        provider_form.setLabelAlignment(Qt.AlignLeft)
        provider_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        provider_form.setSpacing(8)
        
        self.cmbProvider = QComboBox()
        self.cmbProvider.setObjectName("cmbProvider")
        self.cmbProvider.addItems(["openai", "azure", "ollama", "mistral"])
        self.cmbProvider.currentIndexChanged.connect(self._on_provider_changed)
        provider_form.addRow("Provider:", self.cmbProvider)
        llm_group_layout.addLayout(provider_form)
        
        # Add some spacing between provider selection and provider-specific settings
        llm_group_layout.addSpacing(5)
        
        # Provider-specific forms in a StackedWidget
        self.stwProviderForms = QStackedWidget()
        self.stwProviderForms.setObjectName("stwProviderForms")

        # Page 0: OpenAI
        page_openai = QWidget()
        layout_openai = QFormLayout(page_openai)
        layout_openai.setLabelAlignment(Qt.AlignLeft)
        layout_openai.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        layout_openai.setSpacing(8)
        
        self.editOpenAIKey = QLineEdit()
        self.editOpenAIKey.setEchoMode(QLineEdit.Password)
        layout_openai.addRow("API Key:", self.editOpenAIKey)
        
        self.cmbOpenAIModel = QComboBox()
        self.cmbOpenAIModel.setObjectName("cmbOpenAIModel")
        self.cmbOpenAIModel.setEditable(True)
        layout_openai.addRow("Model:", self.cmbOpenAIModel)

        self.btnTestOpenAI = QPushButton("Verbindung testen")
        layout_openai.addRow(self.btnTestOpenAI)
        self.lblTestResultOpenAI = QLabel()
        layout_openai.addRow(self.lblTestResultOpenAI)
        self.lblTestResultOpenAI.hide()
        
        self.stwProviderForms.addWidget(page_openai)

        # Page 1: Azure
        page_azure = QWidget()
        layout_azure = QFormLayout(page_azure)
        layout_azure.setLabelAlignment(Qt.AlignLeft)
        layout_azure.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        layout_azure.setSpacing(8)
        
        self.editAzureEndpoint = QLineEdit()
        self.editAzureEndpoint.setObjectName("editEndpoint")
        layout_azure.addRow("Endpoint:", self.editAzureEndpoint)
        
        self.editAzureDeploymentName = QLineEdit()
        self.editAzureDeploymentName.setObjectName("editAzureDeploymentName")
        layout_azure.addRow("Deployment Name:", self.editAzureDeploymentName)
        
        self.editAzureKey = QLineEdit()
        self.editAzureKey.setEchoMode(QLineEdit.Password)
        layout_azure.addRow("API Key:", self.editAzureKey)
        
        self.editAzureApiVersion = QLineEdit()
        self.editAzureApiVersion.setObjectName("editAzureApiVersion")
        layout_azure.addRow("API Version:", self.editAzureApiVersion)

        self.btnTestAzure = QPushButton("Verbindung testen")
        layout_azure.addRow(self.btnTestAzure)
        self.lblTestResultAzure = QLabel()
        layout_azure.addRow(self.lblTestResultAzure)
        self.lblTestResultAzure.hide()

        self.stwProviderForms.addWidget(page_azure)

        # Page 2: Ollama
        page_ollama = QWidget()
        layout_ollama = QFormLayout(page_ollama)
        layout_ollama.setLabelAlignment(Qt.AlignLeft)
        layout_ollama.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        layout_ollama.setSpacing(8)
        
        self.editOllamaBaseUrl = QLineEdit()
        layout_ollama.addRow("Base URL:", self.editOllamaBaseUrl)
        
        self.cmbOllamaModel = QComboBox()
        self.cmbOllamaModel.setObjectName("cmbOllamaModel")
        self.cmbOllamaModel.setEditable(True)
        layout_ollama.addRow("Model:", self.cmbOllamaModel)

        self.btnTestOllama = QPushButton("Verbindung testen")
        layout_ollama.addRow(self.btnTestOllama)
        self.lblTestResultOllama = QLabel()
        layout_ollama.addRow(self.lblTestResultOllama)
        self.lblTestResultOllama.hide()

        self.stwProviderForms.addWidget(page_ollama)

        # Page 3: Mistral
        page_mistral = QWidget()
        layout_mistral = QFormLayout(page_mistral)
        layout_mistral.setLabelAlignment(Qt.AlignLeft)
        layout_mistral.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        layout_mistral.setSpacing(8)

        self.editMistralKey = QLineEdit()
        self.editMistralKey.setEchoMode(QLineEdit.Password)
        layout_mistral.addRow("API Key:", self.editMistralKey)

        self.cmbMistralModel = QComboBox()
        self.cmbMistralModel.setObjectName("cmbMistralModel")
        self.cmbMistralModel.setEditable(True)
        layout_mistral.addRow("Model:", self.cmbMistralModel)

        self.btnTestMistral = QPushButton("Verbindung testen")
        layout_mistral.addRow(self.btnTestMistral)
        self.lblTestResultMistral = QLabel()
        layout_mistral.addRow(self.lblTestResultMistral)
        self.lblTestResultMistral.hide()

        self.stwProviderForms.addWidget(page_mistral)

        llm_group_layout.addWidget(self.stwProviderForms)
        llm_group_box.setLayout(llm_group_layout)
        self.layout.addWidget(llm_group_box)

        # Add flexible space between sections and buttons
        self.layout.addStretch(1)

        # --- Dialog Buttons ---
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.button(QDialogButtonBox.Save).setText("Speichern")
        self.button_box.button(QDialogButtonBox.Cancel).setText("Abbrechen")
        button_layout.addStretch(1)
        button_layout.addWidget(self.button_box)
        self.layout.addLayout(button_layout)

        # --- Connect Signals ---
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        
        # Connect directory button signals
        self.btnWorkDir.clicked.connect(lambda: self._select_directory(self.editWorkDir))
        self.btnBackupRoot.clicked.connect(lambda: self._select_directory(self.editBackupRoot))
        self.btnUnsortedRoot.clicked.connect(lambda: self._select_directory(self.editUnsortedRoot))
        # Connect signals to clear test results when inputs change
        self.editOpenAIKey.textChanged.connect(self.lblTestResultOpenAI.hide)
        self.cmbOpenAIModel.editTextChanged.connect(self.lblTestResultOpenAI.hide)
        self.editAzureEndpoint.textChanged.connect(self.lblTestResultAzure.hide)
        self.editAzureKey.textChanged.connect(self.lblTestResultAzure.hide)
        self.editAzureApiVersion.textChanged.connect(self.lblTestResultAzure.hide)
        self.editAzureDeploymentName.textChanged.connect(self.lblTestResultAzure.hide)
        self.editOllamaBaseUrl.textChanged.connect(self.lblTestResultOllama.hide)
        self.cmbOllamaModel.editTextChanged.connect(self.lblTestResultOllama.hide)
        self.editMistralKey.textChanged.connect(self.lblTestResultMistral.hide)
        self.cmbMistralModel.editTextChanged.connect(self.lblTestResultMistral.hide)
        self.cmbProvider.currentIndexChanged.connect(self.clear_all_test_results)

        # Signal connections for test button states are now handled in the controller

        # Set initial provider form
        self._on_provider_changed(self.cmbProvider.currentIndex())

    def show_test_result(self, provider_name: str, success: bool, message: str):
        """Displays the connection test result under the corresponding button."""
        label_map = {
            'openai': self.lblTestResultOpenAI,
            'azure': self.lblTestResultAzure,
            'ollama': self.lblTestResultOllama,
            'mistral': self.lblTestResultMistral,
        }
        label = label_map.get(provider_name)

        if label:
            label.setText(message)
            label.setAlignment(Qt.AlignLeft)
            color = "green" if success else "red"
            label.setStyleSheet(f"color: {color};")
            label.setWordWrap(True)
            label.show()

    def clear_all_test_results(self):
        """Hides all test result labels."""
        self.lblTestResultOpenAI.hide()
        self.lblTestResultAzure.hide()
        self.lblTestResultOllama.hide()
        self.lblTestResultMistral.hide()

    def set_buttons_enabled(self, enabled: bool):
        """Enables or disables all buttons that trigger long-running operations."""
        # Disable/enable test buttons
        self.btnTestOpenAI.setEnabled(enabled)
        self.btnTestAzure.setEnabled(enabled)
        self.btnTestOllama.setEnabled(enabled)
        self.btnTestMistral.setEnabled(enabled)

        # Also disable/enable standard dialog buttons
        self.button_box.button(QDialogButtonBox.Save).setEnabled(enabled)
        self.button_box.button(QDialogButtonBox.Cancel).setEnabled(enabled)

    def _create_group_box(self, title):
        """Helper to create consistently styled group boxes"""
        group_box = QGroupBox(title)
        font = QFont()
        font.setBold(True)
        font.setPointSize(11)
        group_box.setFont(font)
        group_box.setStyleSheet("QGroupBox { margin-top: 15px; padding-top: 15px; }")
        return group_box
        
    def _on_provider_changed(self, index):
        """Switch the provider form when selection changes"""
        self.clear_all_test_results()
        self.stwProviderForms.setCurrentIndex(index)
        
    def _select_directory(self, line_edit):
        """Open directory selection dialog and update the line edit"""
        from PySide6.QtWidgets import QFileDialog
        current_dir = line_edit.text() or str(Path.home())
        directory = QFileDialog.getExistingDirectory(self, "Verzeichnis auswählen", current_dir)
        if directory:
            line_edit.setText(directory)

    def accept(self):
        """Save settings and close the dialog."""
        self.controller.save()
        super().accept()
