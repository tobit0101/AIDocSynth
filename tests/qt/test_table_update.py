from PySide6.QtCore import Qt

from aidocsynth.ui.job_table_model import JobTableModel
from aidocsynth.models.job import Job

def test_table_updates():
    m = JobTableModel()
    j = Job(path="a.pdf")
    m.add_job(j)
    assert m.rowCount() == 1
    j.status, j.progress = "done", 100
    m.refresh(j)
    idx_status = m.index(0, 2) # Column 2 for Status
    idx_progress = m.index(0, 3) # Column 3 for Progress
    assert m.data(idx_status, Qt.DisplayRole) == "done"
    assert m.data(idx_progress, Qt.DisplayRole) == "100 %"
