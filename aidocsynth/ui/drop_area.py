from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QDragLeaveEvent
from PySide6.QtWidgets import (
    QFrame, QLabel, QVBoxLayout, QWidget, QSizePolicy, QHBoxLayout
)


class InactiveView(QFrame):
    """A simple, non-interactive widget to show the initialization state."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("inactiveView")
        self.setAttribute(Qt.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.text_label = QLabel("OCR Engine wird initialisiert...")
        self.text_label.setObjectName("initializationText")
        font = self.text_label.font()
        font.setPointSize(16)
        self.text_label.setFont(font)
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.text_label)

        self.setStyleSheet("""
            #inactiveView {
                border: 4px dashed #888;
                border-radius: 15px;
                background-color: rgba(100, 100, 100, 100);
            }
            #initializationText {
                color: #888;
                background-color: transparent;
            }
        """)


class ActiveDropArea(QFrame):
    """A widget for drag-and-drop functionality, only handling active and highlighted states."""
    filesDropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setObjectName("activeDropArea")
        self.setAttribute(Qt.WA_StyledBackground, True)

        # Main layout to center the content container
        main_layout = QVBoxLayout(self)
        main_layout.addStretch()

        # Container for the content to isolate it from resizing
        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # --- Widgets for the container ---
        self.text_label = QLabel("Drag & Drop Files Here")
        self.text_label.setObjectName("mainDropText")
        font = self.text_label.font()
        font.setPointSize(20)
        self.text_label.setFont(font)
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self.text_label)

        self.separator_line = QFrame()
        self.separator_line.setObjectName("separatorLine")
        self.separator_line.setFrameShape(QFrame.NoFrame)
        self.separator_line.setFrameShadow(QFrame.Plain)
        self.separator_line.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.separator_line.setLineWidth(1)
        self.separator_line.setFixedHeight(2)
        self.separator_line.setFixedWidth(150)

        # Center the separator line
        separator_layout = QHBoxLayout()
        separator_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        separator_layout.addWidget(self.separator_line)
        content_layout.addLayout(separator_layout)

        self.supported_types_label = QLabel("PDF - Image - Office")
        self.supported_types_label.setObjectName("supportedTypesLabel")
        font = self.supported_types_label.font()
        font.setPointSize(14)
        self.supported_types_label.setFont(font)
        self.supported_types_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self.supported_types_label)

        # Layout to center the container horizontally
        h_layout = QHBoxLayout()
        h_layout.addStretch()
        h_layout.addWidget(content_container)
        h_layout.addStretch()

        main_layout.addLayout(h_layout)
        main_layout.addStretch()

        self._setup_stylesheet()
        # Set initial property for styling
        self.setProperty("highlighted", "false")

    def _setup_stylesheet(self):
        self.setStyleSheet("""
            #activeDropArea {
                border: 4px dashed #777;
                border-radius: 15px;
                background-color: #ffffff;
            }
            #mainDropText, #supportedTypesLabel {
                color: #777;
                background-color: transparent;
                padding-bottom: 2px;
            }
            #supportedTypesLabel {
                padding-top: 2px;
            }
            #separatorLine {
                max-width: 150px;
                border: none;
                border-top: 2px solid #777;
            }

            /* --- Highlighted State --- */
            #activeDropArea[highlighted="true"] {
                background-color: #eaf3fc;
                border-color: #6A89A4;
            }
            #activeDropArea[highlighted="true"] #mainDropText,
            #activeDropArea[highlighted="true"] #supportedTypesLabel {
                color: #6A89A4;
            }
            #activeDropArea[highlighted="true"] #separatorLine {
                border-top-color: #6A89A4;
            }
        """)

    def _refresh_qss(self):
        """Recursively repolish the widget and all its children to apply style changes."""
        st = self.style()
        for w in [self, *self.findChildren(QWidget)]:
            st.unpolish(w)
            st.polish(w)
        self.update()

    def _set_highlighted(self, highlighted: bool):
        """Update property and refresh styles for the entire widget tree."""
        self.setProperty("highlighted", "true" if highlighted else "false")
        self._refresh_qss()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_highlighted(True)
        super().dragEnterEvent(event)

    def dragLeaveEvent(self, event: QDragLeaveEvent):
        self._set_highlighted(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent):
        self._set_highlighted(False)
        urls = [url.toLocalFile() for url in event.mimeData().urls()]
        if urls:
            self.filesDropped.emit(urls)
        super().dropEvent(event)
