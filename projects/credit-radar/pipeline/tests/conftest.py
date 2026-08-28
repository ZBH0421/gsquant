from __future__ import annotations

import importlib
from types import ModuleType

import pytest


def load_module(name: str) -> ModuleType:
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError:
        pytest.fail(f"required module is not implemented yet: {name}", pytrace=False)
