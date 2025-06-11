from PySide6.QtWidgets import QFrame
from PySide6.QtCore import Signal, Qt

class DropArea(QFrame):
    filesDropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Sunken)
        self._original_style = "border: 2px dashed #aaa; background-color: #f0f0f0; border-radius: 5px;"
        self._highlight_style = "border: 2px solid #0078d7; background-color: #eaf3fc; border-radius: 5px;"
        self.setStyleSheet(self._original_style)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet(self._highlight_style)

    def dragLeaveEvent(self, event):
        self.setStyleSheet(self._original_style)

    def dropEvent(self, event):
        self.setStyleSheet(self._original_style)
        urls = [url.toLocalFile() for url in event.mimeData().urls()]
        if urls:
            self.filesDropped.emit(urls)
