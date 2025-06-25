from PySide6.QtWidgets import QTableView
from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent

class ClickableTableView(QTableView):
    """A table view that shows a pointing hand cursor over specific columns."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._clickable_columns = set()

    def add_clickable_column(self, column_index):
        self._clickable_columns.add(column_index)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Change cursor to pointing hand when hovering over a clickable column."""
        index = self.indexAt(event.pos())
        if index.isValid() and index.column() in self._clickable_columns:
            self.setCursor(Qt.PointingHandCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        """Reset cursor when mouse leaves the widget."""
        self.setCursor(Qt.ArrowCursor)
        super().leaveEvent(event)
