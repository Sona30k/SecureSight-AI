from importlib import import_module
from typing import Any


def optional_import(name: str) -> Any | None:
    try:
        return import_module(name)
    except ImportError:
        return None
