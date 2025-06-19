from pathlib import Path
from dotenv import load_dotenv
from PySide6.QtCore import QObject, Signal
from aidocsynth.models.settings import AppSettings

_CFG = Path.home() / ".config" / "AIDocSynth" / "settings.json"
load_dotenv()

class SettingsService(QObject): # Inherit from QObject
    settings_changed = Signal() # Define the signal
    def __init__(self):
        super().__init__() # Call QObject constructor
        self.data = (AppSettings.model_validate_json(_CFG.read_text())
                     if _CFG.exists() else AppSettings())
    def save(self):
        _CFG.parent.mkdir(parents=True, exist_ok=True)
        _CFG.write_text(self.data.model_dump_json(indent=2))
        self.settings_changed.emit() # Emit the signal

settings = SettingsService()
