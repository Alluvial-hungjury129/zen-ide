"""
Theme definitions for Zen IDE.
All built-in color themes, each defined in its own file under definitions/.

Themes are lazy-loaded: only the active theme is imported at startup.
The full set is loaded on-demand when the theme list is requested.

Lightweight metadata (display_name, is_dark) lives in the registry so the
theme picker can populate instantly without importing any theme modules.
"""

import importlib
from typing import List


class _LazyThemeDict(dict):
    """Dict that lazily imports theme definition modules on first access."""

    def __init__(self, registry):
        super().__init__()
        self._registry = registry

    def _load(self, key):
        if key in self._registry and key not in dict.keys(self):
            module_path = self._registry[key][0]
            var_name = self._registry[key][1]
            try:
                mod = importlib.import_module(module_path)
            except ImportError:
                return None
            theme = getattr(mod, var_name, None)
            if theme is None:
                return None
            dict.__setitem__(self, key, theme)
            return theme
        return None

    def _load_all(self):
        for key in self._registry:
            if key not in dict.keys(self):
                self._load(key)

    def __getitem__(self, key):
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            result = self._load(key)
            if result is not None:
                return result
            raise

    def __contains__(self, key):
        return key in self._registry or dict.__contains__(self, key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def values(self):
        self._load_all()
        return dict.values(self)

    def items(self):
        self._load_all()
        return dict.items(self)

    def keys(self):
        return self._registry.keys()

    def __len__(self):
        return len(self._registry)

    def __iter__(self):
        return iter(self._registry)


# Registry: theme_name → (module_path, variable_name, display_name, is_dark)
_THEME_REGISTRY = {
    # Dark themes
    "zen_style": ("themes.definitions.zen_style", "ZEN_STYLE", "Zen Style", True),
    "zen_dark": ("themes.definitions.zen_dark", "ZEN_DARK", "Zen Dark", True),
    "tokyonight": ("themes.definitions.tokyonight", "TOKYONIGHT", "Tokyo Night", True),
    "dracula": ("themes.definitions.dracula", "DRACULA", "Dracula", True),
    "gruvbox_dark": ("themes.definitions.gruvbox_dark", "GRUVBOX_DARK", "Gruvbox Dark", True),
    "zengruv": ("themes.definitions.zengruv", "ZENGRUV", "Zengruv", True),
    "one_dark": ("themes.definitions.one_dark", "ONE_DARK", "One Dark", True),
    "catppuccin_mocha": ("themes.definitions.catppuccin_mocha", "CATPPUCCIN_MOCHA", "Catppuccin Mocha", True),
    "kanagawa": ("themes.definitions.kanagawa", "KANAGAWA", "Kanagawa", True),
    "laserwave": ("themes.definitions.laserwave", "LASERWAVE", "Laserwave", True),
    "everforest_dark": ("themes.definitions.everforest_dark", "EVERFOREST_DARK", "Everforest Dark", True),
    "aura_dark": ("themes.definitions.aura_dark", "AURA_DARK", "Aura Dark", True),
    "aurora_borealis": ("themes.definitions.aurora_borealis", "AURORA_BOREALIS", "Aurora Borealis", True),
    "jellybeans": ("themes.definitions.jellybeans", "JELLYBEANS", "Jellybeans", True),
    "trix": ("themes.definitions.trix", "TRIX", "Trix", True),
    "modus_vivendi": ("themes.definitions.modus_vivendi", "MODUS_VIVENDI", "Modus Vivendi", True),
    "new_aura_dark": ("themes.definitions.new_aura_dark", "NEW_AURA_DARK", "New Aura Dark", True),
    "nyoom": ("themes.definitions.nyoom", "NYOOM", "Nyoom", True),
    "oxocarbon": ("themes.definitions.oxocarbon", "OXOCARBON", "Oxocarbon", True),
    "retrobox": ("themes.definitions.retrobox", "RETROBOX", "Retrobox", True),
    "spacevim": ("themes.definitions.spacevim", "SPACEVIM", "SpaceVim", True),
    "synthwave84": ("themes.definitions.synthwave84", "SYNTHWAVE84", "Synthwave '84", True),
    "c64_dreams": ("themes.definitions.c64_dreams", "C64_DREAMS", "64 Basic Dreams", True),
    "c64_videogame_dreams": ("themes.definitions.c64_videogame_dreams", "C64_VIDEOGAME_DREAMS", "64 Dreams", True),
    "cga_dream": ("themes.definitions.cga_dream", "CGA_DREAM", "CGA Dream", True),
    "cyberdream": ("themes.definitions.cyberdream", "CYBERDREAM", "Cyberdream", True),
    "ega_dreams": ("themes.definitions.ega_dreams", "EGA_DREAMS", "EGA Dreams", True),
    "fluoromachine": ("themes.definitions.fluoromachine", "FLUOROMACHINE", "Fluoromachine", True),
    "terracotta": ("themes.definitions.terracotta", "TERRACOTTA", "Terracotta", True),
    "ansi_blows": ("themes.definitions.ansi_blows", "ANSI_BLOWS", "Ansi Blows", True),
    "zx_dreams": ("themes.definitions.zx_dreams", "ZX_DREAMS", "ZX Dreams", True),
    "melange_dark": ("themes.definitions.melange_dark", "MELANGE_DARK", "Melange Dark", True),
    # Light themes
    "zen_light": ("themes.definitions.zen_light", "ZEN_LIGHT", "Zen Light", False),
    "solarized_light": ("themes.definitions.solarized_light", "SOLARIZED_LIGHT", "Solarized Light", False),
    "catppuccin_latte": ("themes.definitions.catppuccin_latte", "CATPPUCCIN_LATTE", "Catppuccin Latte", False),
    "gruvbox_light": ("themes.definitions.gruvbox_light", "GRUVBOX_LIGHT", "Gruvbox Light", False),
    "everforest_light": ("themes.definitions.everforest_light", "EVERFOREST_LIGHT", "Everforest Light", False),
    "melange_light": ("themes.definitions.melange_light", "MELANGE_LIGHT", "Melange Light", False),
}

THEMES = _LazyThemeDict(_THEME_REGISTRY)


def get_theme_metadata() -> List[tuple]:
    """Return (name, display_name, is_dark) for every registered theme.

    This reads only from the registry — no theme modules are imported.
    """
    return [(name, entry[2], entry[3]) for name, entry in _THEME_REGISTRY.items()]
