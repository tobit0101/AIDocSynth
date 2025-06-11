from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, 
    QDialogButtonBox, QGroupBox, QLabel, QTabWidget, QWidget
)
from aidocsynth.models.settings import settings
from PySide6.QtCore import QCoreApplication

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
        self.resize(450, 200)
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
        
        self.llm_group_box = QGroupBox("LLM Provider")
        self.llm_form_layout = QFormLayout()

        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["openai", "anthropic"]) # Example providers
        self.llm_form_layout.addRow("Provider:", self.provider_combo)

        self.model_input = QLineEdit()
        self.llm_form_layout.addRow("Model:", self.model_input)

        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.llm_form_layout.addRow("API Key:", self.api_key_input)
        
        self.llm_group_box.setLayout(self.llm_form_layout)
        self.ki_layout.addWidget(self.llm_group_box)
        self.ki_layout.addStretch()

        # --- Setup Allgemein Tab ---
        self.allgemein_layout = QVBoxLayout(self.tabAllgemein)
        self.allgemein_layout.addWidget(QLabel("Allgemeine Einstellungen werden hier konfiguriert."))
        self.allgemein_layout.addStretch()

        # --- Dialog Buttons ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.layout.addWidget(self.button_box)

        # --- Connect Signals ---
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def load_settings(self):
        """Load settings from the manager and populate the UI fields."""
        s = settings.data.llm
        self.provider_combo.setCurrentText(s.provider)
        self.model_input.setText(s.model)
        self.api_key_input.setText(s.api_key)

    def accept(self):
        """Save settings and close the dialog."""
        s = settings.data.llm
        s.provider = self.provider_combo.currentText()
        s.model = self.model_input.text()
        s.api_key = self.api_key_input.text()
        settings.save()
        super().accept()
