"""Centralized GI namespace requirements and optional loaders."""

from __future__ import annotations

import os
from typing import Sequence

import gi

_DEFAULT_NAMESPACE_VERSIONS: dict[str, tuple[str, ...]] = {
    "Gtk": ("4.0",),
    "GtkSource": ("5",),
    "Gdk": ("4.0",),
    "Graphene": ("1.0",),
    "GdkPixbuf": ("2.0",),
    "Gsk": ("4.0",),
    "Pango": ("1.0",),
    "Vte": ("3.91",),
}

_WEBKIT_NAMESPACE_CANDIDATES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("WebKit", ("6.0",)),
    ("WebKit2", ("4.1", "4.0")),
)

_TOP_LEVEL_NAMESPACES: tuple[str, ...] = (
    "Gtk",
    "GtkSource",
    "Gdk",
    "Graphene",
    "GdkPixbuf",
    "Gsk",
    "Pango",
    "Vte",
)

_REQUIRED_VERSIONS: dict[str, str] = {}


def _env_versions(namespace: str) -> tuple[str, ...]:
    """Read optional version overrides from environment.

    Example: ZEN_IDE_GI_GTK_VERSIONS=4.0,4
    """
    env_key = f"ZEN_IDE_GI_{namespace.upper()}_VERSIONS"
    raw = os.getenv(env_key, "")
    if not raw:
        return ()
    return tuple(version.strip() for version in raw.split(",") if version.strip())


def _versions_for(namespace: str, fallback: Sequence[str] = ()) -> tuple[str, ...]:
    env_versions = _env_versions(namespace)
    if env_versions:
        return env_versions
    configured = _DEFAULT_NAMESPACE_VERSIONS.get(namespace)
    if configured:
        return configured
    return tuple(fallback)


def require_namespace(namespace: str, versions: Sequence[str] | None = None) -> str:
    """Require a GI namespace version and memoize the selected version."""
    if namespace in _REQUIRED_VERSIONS:
        return _REQUIRED_VERSIONS[namespace]

    candidates = tuple(versions) if versions is not None else _versions_for(namespace)
    if not candidates:
        raise ValueError(f"No version candidates configured for GI namespace: {namespace}")

    last_error: ValueError | None = None
    for version in candidates:
        try:
            gi.require_version(namespace, version)
            _REQUIRED_VERSIONS[namespace] = version
            return version
        except ValueError as exc:
            last_error = exc

    tried = ", ".join(candidates)
    raise ImportError(f"Unable to require GI namespace '{namespace}' with versions: {tried}") from last_error


def ensure_gi_requirements(namespaces: Sequence[str] | None = None) -> dict[str, str]:
    """Require all top-level GI namespaces once."""
    selected: dict[str, str] = {}
    for namespace in tuple(namespaces) if namespaces is not None else _TOP_LEVEL_NAMESPACES:
        selected[namespace] = require_namespace(namespace)
    return selected


def import_namespace(namespace: str):
    """Import and return a module from gi.repository after requiring its version."""
    module = __import__("gi.repository", fromlist=[namespace])
    return getattr(module, namespace)


def load_optional_namespace(namespace: str, versions: Sequence[str] | None = None):
    """Load an optional namespace, returning None when unavailable."""
    candidates = tuple(versions) if versions is not None else _versions_for(namespace)
    if not candidates:
        return None

    for version in candidates:
        try:
            require_namespace(namespace, [version])
            return import_namespace(namespace)
        except (ImportError, ValueError):
            continue
    return None


def load_webkit():
    """Load the best available WebKit namespace (WebKit or WebKit2)."""
    for namespace, defaults in _WEBKIT_NAMESPACE_CANDIDATES:
        module = load_optional_namespace(namespace, _versions_for(namespace, defaults))
        if module is not None:
            return module
    return None


def require_gtk() -> str:
    return require_namespace("Gtk")


def require_gtksource() -> str:
    return require_namespace("GtkSource")


def require_gdk() -> str:
    return require_namespace("Gdk")


def require_graphene() -> str:
    return require_namespace("Graphene")


def require_gdkpixbuf() -> str:
    return require_namespace("GdkPixbuf")


def require_gsk() -> str:
    return require_namespace("Gsk")


def require_pango() -> str:
    return require_namespace("Pango")
