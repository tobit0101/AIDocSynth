import sys
import os
from PySide6.QtCore import Qt

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from aidocsynth.ui.job_table_model import JobTableModel
from aidocsynth.models.job import Job

def test_table_updates():
    m = JobTableModel()
    j = Job(path="a.pdf")
    m.add_job(j)
    assert m.rowCount() == 1
    j.status, j.progress = "done", 100
    m.refresh(j)
    idx_status = m.index(0, 1) # Column 1 for Status
    idx_progress = m.index(0, 2) # Column 2 for Progress
    assert m.data(idx_status, Qt.DisplayRole) == "done"
    assert m.data(idx_progress, Qt.DisplayRole) == "100 %"
