from PySide6.QtCore import QStandardPaths
from pydantic import BaseModel, Field
from pathlib import Path

docs = Path(QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation))

class LLMSettings(BaseModel):
    provider: str = "openai"
    openai_api_key: str | None = None

class AppSettings(BaseModel):
    work_dir:      Path = docs / "AIDocSynth"
    backup_root:   Path = work_dir / "backup"
    unsorted_root: Path = work_dir / "unsorted"
    llm: LLMSettings = Field(default_factory=LLMSettings)
