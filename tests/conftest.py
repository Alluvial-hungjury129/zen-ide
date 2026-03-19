"""Shared pytest fixtures and path setup for all tests."""

import os
import sys

# Add project paths so tests can import src/ modules
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_src = os.path.join(_project_root, "src")
_shared = os.path.join(_src, "shared")
_settings = os.path.join(_shared, "settings")

for p in [_project_root, _src, _shared, _settings]:
    if p not in sys.path:
        sys.path.insert(0, p)

from gi_requirements import ensure_gi_requirements

ensure_gi_requirements()
