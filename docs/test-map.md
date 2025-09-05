# AIDocSynth Test Map

A readable map of what each test covers and how it maps to application code. This helps maintain coverage while keeping the suite lean and understandable.

## Suite Structure

- `tests/qt/`: Qt-/Controller-/UI-nahe Tests (Signale, View-Interaktion, Worker)
- `tests/feature/`: Integrations-/Pipeline-Tests mit echten Dateien (schwere Teile stubbed)
- `tests/unit/`: Unit-Tests für Services und Hilfsfunktionen
- `tests/e2e/`: Reale End-to-End-Tests (z. B. Ollama), laufen im Standardlauf

## Shared Fixtures (tests/conftest.py)

- `workspace_dirs`: isolierte Arbeitsumgebung, setzt `settings.data`-Pfade; `create_backup=True`
- `mock_llm`: stubbt LLM-Provider (liefert `T/x.txt`)
- `assets_dir`: Pfad zu realen Test-Assets

---

## Module → Tests (welche Tests decken welches Modul/Funktion ab)

### `aidocsynth/controllers/main_controller.py`

- Initialisierung und Settings
  - `tests/qt/test_controller_edge_cases.py`
    - `test_settings_connect_guard_when_no_signal` → toleriert fehlendes `settings_changed`
    - `test_handle_settings_changed_noop_when_same_dir` → `_handle_settings_changed()` ohne Label-Update bei unverändertem Verzeichnis
    - `test_emit_processing_status_messages` → `_emit_processing_status()`
  - `tests/unit/test_controller_utils.py`
    - `test_handle_settings_changed_updates_label_and_pool` → Threadpool-Anpassung (`_update_thread_pool_size()`), Label-Update

- Arbeitsverzeichnis öffnen
  - `tests/qt/test_controller_edge_cases.py`
    - `test_open_working_directory_missing_dir_no_view` → Fehlerpfad ohne View/Label
    - `test_open_working_directory_open_fails_without_label` → `QDesktopServices.openUrl` schlägt fehl
    - `test_open_working_directory_success` → Erfolgsfall ohne Fehlermeldung

- Drop-/Job-Handling und UI-Status
  - `tests/qt/test_controller_edge_cases.py`
    - `test_handle_drop_empty_noop` → frühe Rückkehr bei leerer Liste
    - `test_handle_drop_enables_stop_action_when_view_present` → `actionStopProcessing` wird aktiviert
    - `test_handle_drop_cancellation_skips_remaining_and_resets_ui` → Abbruch überspringt Rest, Status-Reset
    - `test_handle_drop_index_value_error_path` → robuste Behandlung bei Index-Fehlern
    - `test_handle_drop_cancellation_without_action_stop` → Branch ohne View/Action
    - `test_decrement_active_jobs_resets_and_emits` / `test_decrement_active_jobs_updates_status_when_remaining`
    - `test_handle_drop_emits_job_updated` → Worker-Erfolg → `update_job_on_success()` → `jobUpdated`, inkl. Cleanup

- Pipeline (Backup → OCR/Text → Klassifikation → Sortierung → Metadaten)
  - `tests/qt/test_controller_edge_cases.py`
    - `test_backup_file_handles_exception` → `_backup_file()` fängt Fehler ab
    - `test_classify_document_cancelled_raises` → `_classify_document()` vor Start abgebrochen
    - `test_pipeline_skips_metadata_when_no_new_path` → wenn `_process_file()` `None` → keine Metadaten schreiben
    - `test_pipeline_cancelled_sets_status_when_not_pre_set` → Cancel pflegt Status
    - `test_pipeline_cancelled_without_extra_update_when_status_already_cancelled` → keine Doppel-Emission in Cancel-Exception-Pfad
  - `tests/unit/test_controller_cancel.py`
    - `test_pipeline_cancellation_before_start` → `_pipeline()` bricht vor Start ab, Status „cancelled“
    - `test_update_job_progress_cancellation_raises` → `_update_job_progress()` setzt/prüft Cancel und wirft
    - `test_pipeline_error_sets_job_status_error` → Fehler in Klassifikation → Status „error“
  - `tests/feature/test_pipeline_smoke.py`
    - `test_pipeline_and_table_update` → End-to-End mit Stubs für `full_text`, `FileManager`, `MetadataService`; prüft `jobAdded`/`jobUpdated`, `JobTableModel`
  - `tests/feature/test_pipeline_ocr.py`
    - `test_pipeline_with_assets` → echte Dateien, `full_text` stubbed; prüft Backup-Kopie, Sortierung ins Ziel (Copy-Flow)
  - `tests/qt/test_cancel_during_processing.py`
    - Erzwingt Cancel während der Klassifikationsphase (pollt `is_cancelled_callback`), triggert `request_cancellation()` sobald Status `classifying` emittiert wurde. Prüft: kein Crash, Status `cancelled`, nie `done`, UI-Reset (Stop disabled, "Bereit"). Stabil via Signal-Synchronisation.

- Slots/Signale/Fehlerpfade
  - `tests/qt/test_controller_edge_cases.py`
    - `test_update_job_on_success_none_no_emit` → kein Emit bei `None`
    - `test_update_job_on_error_cancelled_and_error_emits_status` → Pfade „cancelled“/„error“
    - `test_update_job_on_error_cancelled_no_emit` → bereits „cancelled“ → kein erneutes Emit
    - `test_close_calls_shutdown` → `close()` ruft `process_pool.shutdown(wait=False, cancel_futures=True)`

- Dialoge
  - `tests/qt/test_controller_edge_cases.py`
    - `test_show_about_dialog_exec_called` / `test_show_about_dialog_with_parent` → `show_about_dialog()` mit/ohne Parent

---

### `aidocsynth/services/text_pipeline.py`

- `tests/unit/test_text_pipeline.py`
  - `test_extract_direct_truncation` → `extract_direct()` Seiten-/Wortlimit (`ocr_max_pages`)
  - `test_full_text_deduplicates_lines_and_combines` → Zusammenführung `extract_direct` + `ocr_text`
  - `test_full_text_truncates_to_max` → globales Wortlimit (`MAX_FULL_TEXT_WORDS`)
  - `test_logger_handler_init_when_no_handlers` → Logger-Initialisierung
- `tests/unit/test_text_pipeline_logger.py` → kompakte Variante Logger-Init

### `aidocsynth/services/file_manager.py`

- `tests/unit/test_file_manager.py`
  - Copy-/Move-Versionierung: `process_document()` (copy/move; Versionierung; Suffix-Erhaltung)
  - Boundary-/Validierungsfälle: unsorted bei ungültiger Klassifizierung/außerhalb Workspace
  - Verzeichnisstruktur: `get_directory_structure()`, `get_formatted_directory_structure()`
  - Absolute Zielpfade: Normalisierung nach innen
  - Move mit fehlender Quelle → `None`
  - Backup-Logik: `backup_original()` deaktiviert/kein root
- `tests/unit/test_file_manager_outside_abs_normalize.py`
  - abgesicherte Normalisierung bei absoluten Pfaden außerhalb des Workspace

### `aidocsynth/services/metadata_service.py`

- `tests/unit/test_metadata_service.py`
  - `generate_and_merge_metadata()`
  - Round-trip lesen/schreiben: PDF/DOCX/XLSX/PPTX
  - PNG/JPEG Branches inkl. EXIF/Kommentare
  - Fehlerpfade (spezifisch/generic), `_safe_decode`
- `tests/unit/test_metadata_handlers.py`
  - PNG/PDF Basisrunden (kleinere Abdeckung)

### `aidocsynth/services/ocr_service.py`

- `tests/feature/test_ocr_service_feature.py`
  - `test_ocr_text_with_assets_uses_conversion_pipeline` → OCR-Konvertierungspipeline (PyMuPDF/PIL Pfade), Fake-Model → deterministisches Ergebnis

### `aidocsynth/services/classification_service.py`

- `tests/unit/test_classification_service.py`
  - Erfolgspfade inkl. JSON/Nicht-JSON
  - Retries bis valide Klassifizierung
  - Fehlerszenarien (fehlende Keys, invalid JSON, Exceptions) → Fallback-Resultat
  - Cancel vor Aufruf → `asyncio.CancelledError` (Provider wird nicht gerufen)

### `aidocsynth/services/providers/base.py`

- `tests/unit/test_providers_base.py`
  - `get_provider()` wirft bei unbekanntem Provider

### `aidocsynth/utils/connection_utils.py`

- `tests/unit/test_connection_utils.py`
  - `test_provider_connection()` Erfolg/Fehler mit Fake-Providern

### `aidocsynth/utils/worker.py`

- `tests/qt/test_worker.py`
  - `Worker.run()` Sync/Async-Funktionen, Signalpfade (`result`, `progress`, `error`, `finished`)
  - Fehlerfälle: `CancelledError` behandelt, `RuntimeError` beim Emit unterdrückt
  - Kein `QCoreApplication` → keine Thread-Verschiebung, läuft dennoch

- `tests/qt/test_parallel_processing.py`
  - Real-nahe Parallelität: `MainController` unter `processing_mode=parallel` mit 2 Threads
  - Zwei Jobs gleichzeitig droppen, klassifikations-Stufe instrumentiert (simulierte Latenz)
  - Prüft zeitliche Überlappung (Konkurrenz) sowie vollständigen Abschluss und Outputs

### `aidocsynth/utils/async_worker.py`

- Direkte Tests entfernt (thin wrapper: `fetch_models_async`)
- Verhalten indirekt abgedeckt durch `Worker`- und Controller-/Provider-Pfade

### `aidocsynth/services/settings_service.py`

- `tests/qt/test_settings_service.py`
  - Roundtrip `save()`/`load()` (Datei)
  - Signal `settings_changed` wird emittiert

### `aidocsynth/ui/job_table_model.py`

- `tests/qt/test_table_update.py`
  - `add_job()`, `refresh()` → Anzeige von Status/Fortschritt
- Indirekt in `tests/feature/test_pipeline_smoke.py` über `jobAdded`/`jobUpdated`

### `aidocsynth/ui/about_dialog_view.py`

- Indirekt über Controller-Tests `show_about_dialog*`

### Echte E2E

- `tests/e2e/test_ollama.py`
  - Realer Ollama-Provider (falls erreichbar), Pipeline Ende-zu-Ende mit echter Klassifikation
- `tests/e2e/test_ocr_service_e2e.py`
  - Realer OCR-Lauf (doctr) auf generiertem Bild; initialisiert `initialize_ocr()` und ruft `ocr_text()` ohne Mocks

---

## Tests → Module (umgekehrte Sicht)

- `tests/qt/test_controller_edge_cases.py`
  - Deckt den Großteil von `MainController`: `open_working_directory()`, `handle_drop()`, `_pipeline()`, `_backup_file()`, `_extract_text_ocr()`, `_classify_document()`, `_process_file()`, `_generate_and_write_metadata()`, `_update_job_progress()`, `update_job_on_success()`, `update_job_on_error()`, `_decrement_active_jobs()`, `_emit_processing_status()`, `request_cancellation()`, `close()`, `show_about_dialog()`

- `tests/unit/test_controller_cancel.py`
  - Cancel-/Fehler-Pfade in `_pipeline()`/`_update_job_progress()`

- `tests/feature/test_pipeline_smoke.py`
  - Controller-Pipeline mit Stubs; Interaktion mit `JobTableModel`

- `tests/feature/test_pipeline_ocr.py`
  - Controller-Pipeline mit echten Assets; prüft Backup/Sortierung (Copy-Flow)

- `tests/feature/test_ocr_service_feature.py`
  - `ocr_service.ocr_text()` Konvertierungspipeline bis zum (Fake-)Model

- `tests/e2e/test_ocr_service_e2e.py`
  - `ocr_service.initialize_ocr()`, `ocr_service.ocr_text()` mit echtem Modell (skip, falls Modell nicht initialisierbar)

- `tests/unit/test_text_pipeline*.py`
  - `text_pipeline.extract_direct()`, `text_pipeline.full_text()`, Logger-Init

- `tests/unit/test_file_manager*.py`
  - `file_manager.process_document()`, `backup_original()`, Verzeichnis-/Pfad-Logik

- `tests/unit/test_metadata*.py`
  - `metadata_service` Lesen/Schreiben/Handler/Fehlerzweige

- `tests/unit/test_classification_service.py`
  - `classification_service.ClassificationService.classify_document()`

- `tests/unit/test_connection_utils.py`
  - `utils.connection_utils.test_provider_connection()`

- `tests/unit/test_providers_base.py`
  - `services.providers.base.get_provider()`

- `tests/qt/test_settings_service.py`
  - `SettingsService.save()`/`SettingsService.settings_changed`

- `tests/qt/test_worker.py`
  - `utils.worker.Worker.run()` Signal-Pfade, Sync/Async, Fehlerfälle

- `tests/qt/test_parallel_processing.py`
  - `controllers.main_controller._update_thread_pool_size()` (indirekt: parallel vs. serial)
  - `controllers.main_controller.handle_drop()` Queueing mehrerer Jobs, Worker-Start, Cleanup
  - `services.classification_service.ClassificationService.classify_document()` (instrumentiert für Latenz/Overlap)
  - `services.file_manager.process_document()` realer Copy-Flow (kein Netzwerk)

- `tests/qt/test_cancel_during_processing.py`
  - Forcierter Cancel zur Laufzeit in der Klassifikationsphase; verifiziert robustes Fehler-/Cancel-Handling ohne Absturz, sauberes Cleanup und UI-Reset.

---

## Marker & Ausführung

- `@pytest.mark.qt`: Qt/Signaltests
- `@pytest.mark.feature`: Feature-/Pipeline-/OCR-Tests (schnell; schwere Teile stubbed)
- `@pytest.mark.e2e`: End-to-End unter realen Bedingungen

Im Standardlauf werden sowohl Feature- als auch E2E-Tests ausgeführt. Feature-Tests verwenden Stubs für schnelle, stabile Pipelines; E2E-Tests laufen gegen echte Abhängigkeiten und können bei fehlender Umgebung per `skip` übersprungen werden.

Beispiele:

```bash
# Standardlauf (alle Tests inkl. e2e)
pytest -q

# Schneller Lauf ohne e2e
pytest -q -m "not e2e"

# Nur Feature-Tests
pytest -q -m feature

# Nur End-to-End unter realen Bedingungen
pytest -q -m e2e
```

---

## Konsolidierungen (zuletzt)

- Entfernt: `tests/qt/test_controller_branches.py`, `tests/qt/test_bootstrap.py`, `tests/qt/test_async_worker.py`, `tests/unit/test_controller_paths.py`
- Gründe: Redundanz; Abdeckung in `tests/qt/test_controller_edge_cases.py` und bestehenden Worker-/Pipeline-Tests vorhanden.

---

## Erweiterungshinweise

- Neue Controller-Funktion? Ergänze zuerst in `tests/qt/test_controller_edge_cases.py` einen Edge-/Erfolgspfad-Test (Signalfluss, UI-Auswirkung).
- Schwere Abhängigkeiten? In `tests/feature/` als Integrations-Test mit Stubs (schnell). Reale End-to-End-Flows als `e2e` (impliziert `real`) unter `tests/e2e/` ablegen.
- Service-/Hilfsfunktionen: Unit-Test in `tests/unit/` nahe an der betroffenen API.
