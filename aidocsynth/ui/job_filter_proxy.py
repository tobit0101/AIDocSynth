from PySide6.QtCore import QSortFilterProxyModel
from PySide6.QtCore import Qt

class JobFilterProxy(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = "Alle"

    def set_filter_mode(self, mode: str):
        self._mode = mode
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        if self._mode == "Alle":
            return True
        
        index = self.sourceModel().index(source_row, 2, source_parent) # Column 2 is now 'Status'
        status = self.sourceModel().data(index, Qt.DisplayRole)

        is_active = status not in ("done", "error", "cancelled")
        is_completed = status in ("done", "error", "cancelled")

        if self._mode == "Aktiv":
            return is_active
        elif self._mode == "Abgeschlossen":
            return is_completed
        
        return True
