import os
import re
import tempfile
from pathlib import Path
from typing import Protocol

_KEY_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class LLMCache(Protocol):
    """Stores raw model responses by a content hash. Values are JSON strings."""

    def get(self, key: str) -> str | None: ...

    def put(self, key: str, value: str) -> None: ...


class MemoryCache:
    """Process-local cache. Used when no cache directory is configured, and in tests."""

    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self._values.get(key)

    def put(self, key: str, value: str) -> None:
        self._values[key] = value


class FileCache:
    """One JSON file per response.
    Writes are atomic, so a crash never leaves a half-written entry.
    """

    def __init__(self, directory: Path) -> None:
        self._directory = directory
        self._directory.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        if not _KEY_PATTERN.fullmatch(key):
            raise ValueError("cache keys must be SHA-256 hex digests")
        return self._directory / f"{key}.json"

    def get(self, key: str) -> str | None:
        path = self._path(key)
        if not path.is_file():
            return None
        return path.read_text(encoding="utf-8")

    def put(self, key: str, value: str) -> None:
        target = self._path(key)
        handle, tmp_name = tempfile.mkstemp(dir=self._directory, suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as tmp:
                tmp.write(value)
            os.replace(tmp_name, target)
        except OSError:
            Path(tmp_name).unlink(missing_ok=True)
            raise
