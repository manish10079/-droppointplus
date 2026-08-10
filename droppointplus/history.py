"""Per-instance file history.

Qt equivalent of ``src/History.js``, re-enabled as a first-class feature.

Fixes the original implementation's persistence bug: it wrote to a bare
relative path ``instanceHistory.json`` (resolved against the CWD, so it
landed wherever the app happened to be launched from). DropPoint+ always
writes to the stable per-user app-data directory.

History is best-effort: a read/write failure is logged and never crashes the
shelf (per the project's development skills, failures are not silently
ignored — they are reported through logging).
"""

from __future__ import annotations

import copy
import json
import logging
from pathlib import Path

from .app_config import app_data_dir
from .models import FileItem

logger = logging.getLogger(__name__)

_DEFAULT = {"history": []}


def history_path() -> Path:
    return app_data_dir() / "instanceHistory.json"


def get_history() -> dict:
    """Returns the full history object; never raises."""
    path = history_path()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and isinstance(data.get("history"), list):
            return data
    except OSError as exc:
        # Missing file is normal on first run.
        logger.debug("no history file at %s (%s)", path, exc)
    except (ValueError, TypeError) as exc:
        logger.warning("history file %s is corrupt (%s); starting fresh",
                       path, exc)
    return copy.deepcopy(_DEFAULT)


def _set_history(obj: dict) -> None:
    """Persist the history object; failures are logged, never raised."""
    try:
        history_path().parent.mkdir(parents=True, exist_ok=True)
        with open(history_path(), "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2)
    except OSError:
        logger.exception("could not write history to %s", history_path())


def init_instance(instance_id: int) -> None:
    """Add an empty slot for a new instance if it isn't there yet."""
    data = get_history()
    if any(i.get("instanceId") == instance_id for i in data["history"]):
        return
    data["history"].append({"instanceId": instance_id, "files": []})
    _set_history(data)


def add_to_instance(instance_id: int, files: list[FileItem]) -> None:
    """Record the file list of an instance (serialized to the JSON format)."""
    data = get_history()
    serialized = [f.to_dict() for f in files]
    for entry in data["history"]:
        if entry.get("instanceId") == instance_id:
            entry["files"] = serialized
            break
    else:
        data["history"].append({"instanceId": instance_id, "files": serialized})
    _set_history(data)


def last_instances(n: int = 5) -> list[dict]:
    """The most recent ``n`` instances that actually hold files, newest first."""
    data = get_history()
    with_files = [i for i in data["history"] if i.get("files")]
    return with_files[-n:][::-1]
