import logging
import threading

from foundry_local_sdk import Configuration, FoundryLocalManager

logger = logging.getLogger(__name__)
_MANAGER_LOCK = threading.Lock()
_MODEL_LOCK = threading.Lock()


class FoundryLocalRuntimeError(RuntimeError):
    """Raised when a configured Foundry Local model cannot be prepared."""


def get_ready_model(model_alias: str) -> object:
    try:
        with _MANAGER_LOCK:
            if FoundryLocalManager.instance is None:
                FoundryLocalManager.initialize(Configuration(app_name="RepoLens"))
            manager = FoundryLocalManager.instance

        with _MODEL_LOCK:
            model = manager.catalog.get_model(model_alias)
            if model is None:
                raise FoundryLocalRuntimeError(
                    f"Foundry Local model '{model_alias}' is unavailable."
                )

            if not model.is_cached:
                logger.info("Downloading Foundry Local model %s", model_alias)
                model.download(
                    progress_callback=lambda progress: _log_download_progress(
                        model_alias,
                        progress,
                    )
                )
            if not model.is_loaded:
                logger.info("Loading Foundry Local model %s", model_alias)
                model.load()
            return model
    except FoundryLocalRuntimeError:
        raise
    except Exception as exc:
        raise FoundryLocalRuntimeError(
            f"Foundry Local model '{model_alias}' could not be prepared."
        ) from exc


def _log_download_progress(model_alias: str, progress: float) -> None:
    logger.info("Model %s download progress: %.0f%%", model_alias, progress)
