import importlib
import logging
import sys


def test_logger_handler_init_when_no_handlers(monkeypatch):
    # Remove module to force re-import
    sys.modules.pop("aidocsynth.services.text_pipeline", None)

    # Backup and remove all root handlers
    root_logger = logging.getLogger()
    old_handlers = list(root_logger.handlers)
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)

    try:
        # Import module fresh so top-level logger init runs
        mod = importlib.import_module("aidocsynth.services.text_pipeline")
        # The module-level logger should now have a handler attached since root had none
        assert mod.logger.handlers, "Expected module logger to add a handler when none exist"
        # Also ensure level set at least to INFO as in module init
        assert mod.logger.level <= logging.INFO
    finally:
        # Restore root handlers to avoid impacting other tests
        for h in old_handlers:
            root_logger.addHandler(h)
        # Clean up imported module to avoid side effects for other tests
        sys.modules.pop("aidocsynth.services.text_pipeline", None)
        # Re-import normally to restore typical state for other tests
        importlib.import_module("aidocsynth.services.text_pipeline")
