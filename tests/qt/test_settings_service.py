import json
from pathlib import Path

import pytest
from aidocsynth.services.settings_service import settings, SettingsService
from aidocsynth.models.settings import AppSettings


def test_settings_save_load_roundtrip(tmp_path, monkeypatch):
    cfg_file = tmp_path / "settings.json"
    # Snapshot and restore
    snapshot = settings.data.model_copy(deep=True)
    try:
        monkeypatch.setattr("aidocsynth.services.settings_service._CFG", cfg_file, raising=False)
        # Modify settings
        settings.data.work_dir = tmp_path / "work"
        settings.data.create_backup = False
        settings.data.sort_action = "move"
        settings.save()

        # Load new instance from file
        fresh = SettingsService()
        assert fresh.data.work_dir == settings.data.work_dir
        assert fresh.data.create_backup is False
        assert fresh.data.sort_action == "move"
    finally:
        settings.data = snapshot


@pytest.mark.qt
def test_settings_changed_signal_emitted(tmp_path, monkeypatch, qtbot):
    cfg_file = tmp_path / "settings.json"
    monkeypatch.setattr("aidocsynth.services.settings_service._CFG", cfg_file, raising=False)

    triggered = {"ok": False}
    def on_changed(*_):
        triggered["ok"] = True

    try:
        settings.settings_changed.connect(on_changed)
        settings.save()

        qtbot.wait_until(lambda: triggered["ok"], timeout=2000)
    finally:
        try:
            settings.settings_changed.disconnect(on_changed)
        except Exception:
            pass
