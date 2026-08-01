"""Wspólne parsowanie konfiguracji ze zmiennych środowiskowych."""
from __future__ import annotations

import os


def env_enabled(name: str, default: bool = True) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
