from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget
)
from PySide6.QtCore import QCoreApplication

class SettingsDialogView(QDialog):
    """
    Settings dialog view.
    The UI is created programmatically.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        # This code is migrated from the original settings_dialog.ui file
        if not self.objectName():
            self.setObjectName("SettingsDialog")
        self.resize(400, 300)
        self.verticalLayout = QVBoxLayout(self)
        self.verticalLayout.setObjectName("verticalLayout")
        self.tabWidget = QTabWidget(self)
        self.tabWidget.setObjectName("tabWidget")
        self.tabAllgemein = QWidget()
        self.tabAllgemein.setObjectName("tabAllgemein")
        self.tabWidget.addTab(self.tabAllgemein, "")
        self.tabKI = QWidget()
        self.tabKI.setObjectName("tabKI")
        self.tabWidget.addTab(self.tabKI, "")
        self.verticalLayout.addWidget(self.tabWidget)

        self._retranslate_ui()

    def _retranslate_ui(self):
        self.setWindowTitle(QCoreApplication.translate("SettingsDialog", "Einstellungen", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tabAllgemein), QCoreApplication.translate("SettingsDialog", "Allgemein", None))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tabKI), QCoreApplication.translate("SettingsDialog", "KI", None))
