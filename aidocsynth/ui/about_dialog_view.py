from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QApplication
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
import os

class AboutDialogView(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        app_name = QApplication.applicationDisplayName() or "AI Doc Synth"
        app_version = QApplication.applicationVersion() or "0.1.0"
        # Try to get copyright from organization name if set, otherwise default
        org_name = QApplication.organizationName() or "tobit0101"
        copyright_text = f"Copyright © 2025 {org_name}. All rights reserved."

        self.setWindowTitle(f"Über {app_name}")

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Icon and App Name Layout
        header_layout = QHBoxLayout()
        header_layout.setSpacing(15)

        # App Icon
        icon_label = QLabel()
        icon_path = os.path.join(os.path.dirname(__file__), "resources", "app.png") # Assuming app.png is the source
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            icon_label.setPixmap(pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        header_layout.addWidget(icon_label)

        # App Info Text Layout
        app_info_layout = QVBoxLayout()
        app_info_layout.setSpacing(5)

        title_label = QLabel(f"<b>{app_name}</b>")
        title_label.setFont(self.font())
        font = title_label.font()
        font.setPointSize(font.pointSize() + 4)
        title_label.setFont(font)
        app_info_layout.addWidget(title_label)

        version_label = QLabel(f"Version {app_version}")
        app_info_layout.addWidget(version_label)
        
        header_layout.addLayout(app_info_layout)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(separator)

        # Copyright Information
        copyright_label = QLabel(copyright_text)
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(copyright_label)

        # Description/Link (Optional)
        # description_label = QLabel("Ein intelligentes Werkzeug zur Dokumentenverarbeitung.")
        # description_label.setWordWrap(True)
        # main_layout.addWidget(description_label)
        # 
        # github_link = QLabel('<a href="https://github.com/tobit0101/AIDocSynth">AIDocSynth auf GitHub</a>')
        # github_link.setOpenExternalLinks(True)
        # github_link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # main_layout.addWidget(github_link)

        # OK Button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        ok_button = QPushButton("OK")
        ok_button.setDefault(True)
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)
        button_layout.addStretch()
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)
        self.setFixedSize(self.sizeHint()) # Prevent resizing

if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)
    # Set some app info for testing
    QApplication.setApplicationName("AIDocSynth Test")
    QApplication.setApplicationVersion("0.9.9")
    QApplication.setOrganizationName("TestOrg")

    dialog = AboutDialogView()
    dialog.exec()
    sys.exit(app.exec())
