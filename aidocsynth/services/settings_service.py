from pathlib import Path
from dotenv import load_dotenv
from models.settings import AppSettings

_CFG = Path.home() / ".config" / "AIDocSynth" / "settings.json"
load_dotenv()

class SettingsService:
    def __init__(self):
        self.data = (AppSettings.model_validate_json(_CFG.read_text())
                     if _CFG.exists() else AppSettings())
    def save(self):
        _CFG.parent.mkdir(parents=True, exist_ok=True)
        _CFG.write_text(self.data.model_dump_json(indent=2))

settings = SettingsService()
