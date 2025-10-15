"""Configuration loading utilities for the Fax QA automation application."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
import json
import hashlib


@dataclass(frozen=True)
class LoadedConfig:
    """Container for loaded configuration payloads and derived metadata."""

    path: Path
    payload: Dict[str, Any]
    sha256: str

    @property
    def hash_prefix(self) -> str:
        """Short hash for log-friendly usage."""
        return self.sha256[:8]


class ConfigService:
    """Loads JSON configuration documents with caching and hashing support."""

    def __init__(self, base_path: Path) -> None:
        self._base_path = base_path
        self._cache: Dict[Path, LoadedConfig] = {}

    def _read_json(self, path: Path) -> LoadedConfig:
        raw = path.read_bytes()
        payload = json.loads(raw)
        digest = hashlib.sha256(raw).hexdigest()
        return LoadedConfig(path=path, payload=payload, sha256=digest)

    def load(self, relative_path: str) -> LoadedConfig:
        """Load a configuration document relative to the base path."""
        resolved = (self._base_path / relative_path).resolve()
        if not resolved.is_file():
            raise FileNotFoundError(f"Configuration file not found: {resolved}")
        cached = self._cache.get(resolved)
        if cached:
            return cached
        loaded = self._read_json(resolved)
        self._cache[resolved] = loaded
        return loaded

    def load_optional(self, relative_path: str) -> Optional[LoadedConfig]:
        resolved = (self._base_path / relative_path).resolve()
        if not resolved.is_file():
            return None
        return self.load(relative_path)

    @property
    def base_path(self) -> Path:
        """Expose the configuration root for callers that need to enumerate files."""

        return self._base_path


def default_config_service() -> ConfigService:
    """Helper that uses the repository's ``config`` directory as the base path."""

    repo_root = Path(__file__).resolve().parents[2]
    return ConfigService(repo_root / "config")
