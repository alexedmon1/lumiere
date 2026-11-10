"""The old name of Lumière (``lumiere``), kept so tools not yet moved over keep working.

Everything here is Lumière's: ``import neurobox`` is ``import lumiere``, and ``neurobox.spec``,
``neurobox.gallery`` and the rest are the same modules as ``lumiere.spec``, ``lumiere.gallery``.
New code imports ``lumiere``; this forwarder goes once every tool has moved (renamed 2026-11-10).
"""
from __future__ import annotations

import importlib
import sys

from lumiere import *  # noqa: F401,F403
from lumiere import __all__  # noqa: F401

_SUBMODULES = ("_schema", "check", "spec", "write", "gallery", "gallery.digest", "gallery.links")
for _name in _SUBMODULES:
    _module = importlib.import_module(f"lumiere.{_name}")
    sys.modules[f"{__name__}.{_name}"] = _module
    if "." not in _name:
        globals()[_name] = _module
