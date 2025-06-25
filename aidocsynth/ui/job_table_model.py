from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QApplication, QStyle
from aidocsynth.models.job import Job

HEADERS = ["✓", "Datei", "Status", "Fortschritt", "Ergebnis"]

class JobTableModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self._rows: list[Job] = []
        # Cache standard icons for performance
        self._icons = {
            "done": QApplication.style().standardIcon(QStyle.SP_DialogApplyButton),
            "error": QApplication.style().standardIcon(QStyle.SP_DialogCancelButton),
            "active": QApplication.style().standardIcon(QStyle.SP_BrowserReload),
        }

    # Basis-API
    def rowCount(self, *_):    return len(self._rows)
    def columnCount(self, *_): return len(HEADERS)

    # Datenanzeige
    def data(self, idx: QModelIndex, role: int):
        if not idx.isValid(): return None
        job = self._rows[idx.row()]
        col = idx.column()

        # Column 0: Status Icon
        if role == Qt.DecorationRole and col == 0:
            if job.status == "done":
                return self._icons.get("done")
            if job.status in ["error", "cancelled"]:
                return self._icons.get("error")
            # For any other status, show the 'active' icon
            return self._icons.get("active")

        # Column 1-4: Text Data
        if role == Qt.DisplayRole:
            if col == 1: return job.path
            if col == 2: return job.status
            if col == 3: return f"{job.progress} %"
            if col == 4: return job.result

        # Styling for clickable file paths (now columns 1 and 4)
        if role == Qt.ForegroundRole and (col == 1 or (col == 4 and job.result)):
            return QColor(Qt.blue)

        if role == Qt.FontRole and (col == 1 or (col == 4 and job.result)):
            font = QFont()
            font.setUnderline(True)
            return font

        # Text Alignment
        if role == Qt.TextAlignmentRole:
            if col == 0 or col == 3: # Center Icon and Progress
                return Qt.AlignCenter

    def headerData(self, s, orient, role):
        return HEADERS[s] if orient == Qt.Horizontal and role == Qt.DisplayRole else None

    # Helper
    def add_job(self, job: Job):
        self.beginInsertRows(QModelIndex(), 0, 0)
        self._rows.insert(0, job)          # neueste oben
        self.endInsertRows()

    def refresh(self, job: Job):
        for r, j in enumerate(self._rows):
            if j.id == job.id:
                self._rows[r] = job
                top = self.index(r, 0); bot = self.index(r, self.columnCount()-1)
                self.dataChanged.emit(top, bot); break
