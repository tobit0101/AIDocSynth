from PySide6.QtWidgets import QFrame
from PySide6.QtCore    import Signal

class DropArea(QFrame):
    filesDropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setStyleSheet("border: 2px dashed #888;")

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        self.filesDropped.emit([u.toLocalFile() for u in e.mimeData().urls()])
