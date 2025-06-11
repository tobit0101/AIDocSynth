from PySide6.QtCore import QStandardPaths
from pydantic import BaseModel, Field
from pathlib import Path
import yaml

# This call is safe as it doesn't require a QApplication instance
CFG_DIR = Path(QStandardPaths.writableLocation(QStandardPaths.AppConfigLocation)) / "AIDocSynth"
CFG_FILE = CFG_DIR / "config.yaml"

def get_default_work_dir() -> Path:
    """Gets the default working directory, delaying the QStandardPaths call."""
    docs = Path(QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation))
    return docs / "AIDocSynth"

class LLMSettings(BaseModel):
    provider: str = "openai"             # openai | azure | ollama
    # OpenAI
    openai_api_key: str | None = None
    # Azure OpenAI
    azure_endpoint:  str | None = None
    azure_deployment: str | None = None
    azure_api_key:  str | None = None
    # Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3"

class AppSettings(BaseModel):
    work_dir: Path = Field(default_factory=get_default_work_dir)
    backup_root: Path | None = None
    unsorted_root: Path | None = None
    llm: LLMSettings = Field(default_factory=LLMSettings)

    def model_post_init(self, __context) -> None:
        """Set dependent paths after the model is initialized."""
        if self.backup_root is None:
            self.backup_root = self.work_dir / "backup"
        if self.unsorted_root is None:
            self.unsorted_root = self.work_dir / "unsorted"

class SettingsManager:
    """Manages loading and saving of application settings."""
    def __init__(self):
        self.data = AppSettings()
        self.load()

    def load(self):
        CFG_DIR.mkdir(parents=True, exist_ok=True)
        if CFG_FILE.exists():
            try:
                with open(CFG_FILE, "r") as f:
                    # model_validate will call model_post_init
                    self.data = AppSettings.model_validate(yaml.safe_load(f) or {})
            except Exception as e:
                print(f"Could not load settings: {e}. Using defaults.")
                self.data = AppSettings()

    def save(self):
        with open(CFG_FILE, "w") as f:
            yaml.dump(self.data.model_dump(mode="json"), f, indent=2)

# Global settings instance
settings = SettingsManager()
