from pydantic import BaseModel, Field
from pathlib import Path
from PySide6.QtCore import QStandardPaths

def _app_dir() -> Path:
    return Path(QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation)) / "AIDocSynth"

def _default_work_dir() -> Path:
    docs = Path(QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation))
    return docs / "AIDocSynth"

class LLMSettings(BaseModel):
    provider: str = "openai"                      # openai | azure | ollama
    # OpenAI
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    # Azure
    azure_endpoint: str | None = None
    azure_deployment: str | None = None
    azure_api_key: str | None = None
    azure_api_version: str = "2024-02-01"
    # Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3"

class AppSettings(BaseModel):
    work_dir: Path = Field(default_factory=_default_work_dir)
    backup_root: Path | None = None
    unsorted_root: Path | None = None
    ocr_max_pages: int = 5  # Maximum number of pages to OCR
    create_backup: bool = True
    sort_action: str = "copy"        # copy | move
    processing_mode: str = "parallel"  # parallel | serial
    llm: LLMSettings = Field(default_factory=LLMSettings)

    model_config = {"extra": "forbid"}            # Fehlertyp statt stilles Ignorieren

    def model_post_init(self, __ctx):             # abhängige Pfade nachziehen
        self.backup_root   = self.backup_root   or self.work_dir / "backup"
        self.unsorted_root = self.unsorted_root or self.work_dir / "unsorted"
