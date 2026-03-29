"""Centralised icon definitions and rendering helpers for Zen IDE.

All UI icons — buttons, context menus, notifications, file-type indicators —
are defined here.  Components import named constants instead of hardcoding
Unicode code-points, and use ``create_icon_label()`` for consistent sizing.

Zen IDE uses exactly two fonts:
- **ZenIcons** (``ICON_FONT_FAMILY``) — icon glyphs only, generated from
  Nerd Fonts Symbols Only via ``tools/subset_icon_font.py``.
- **Source Code Pro** — all text (editor, terminal, UI).

Every icon label must use ``ICON_FONT_FAMILY`` so glyphs render from the
bundled ZenIcons font regardless of the user's system fonts.
"""

from gi.repository import Gtk, Pango

from constants import NERD_ICON_SIZE_OFFSET

# ── Icon font constants ────────────────────────────────────────────
# The bundled icon font — a Nerd Font subset containing only the
# codepoints used by Zen IDE.  Always available after registration.
ICON_FONT_FAMILY = "ZenIcons"

# CSS class applied to all icon labels for consistent sizing
ICON_SIZE_CSS_CLASS = "zen-icon"


class IconsManager:
    """Named constants for every icon used in the IDE.

    Grouped by semantic category.  All values are single Unicode characters
    (Nerd Font code-points or standard Unicode symbols).
    """

    # ── Actions (buttons & context menus) ──────────────────────────
    PLUS = "\uf067"  # nf-fa-plus
    TRASH = "\uf1f8"  # nf-fa-trash
    CUT = "\uf0c4"  # nf-fa-scissors
    COPY = "\uf0c5"  # nf-fa-copy
    PASTE = "\uf0ea"  # nf-fa-paste
    SELECT_ALL = "\uf245"  # nf-fa-mouse_pointer
    EDIT = "\uf044"  # nf-fa-pencil
    UNDO = "\uf2ea"  # nf-fa-undo_alt
    WRENCH = "\uf0ad"  # nf-fa-wrench
    GLOBE = "\uf0ac"  # nf-fa-globe
    FILE = "\uf15c"  # nf-fa-file_text
    FOLDER_CLOSED = "\uf07b"  # nf-fa-folder
    FOLDER_OPEN = "\uf07c"  # nf-fa-folder_open
    HEART = "\uf004"  # nf-fa-heart
    FILE_BINARY = "\uf471"  # nf-oct-file_binary
    PENCIL = "\uf040"  # nf-fa-pencil (alternative)
    MAXIMIZE = "\U000f0293"  # nf-md-fullscreen
    CLOSE = "\uf00d"  # nf-fa-times
    NEW_TAB = "󰐕"  # nf-md-plus_circle_outline
    MENU = "\ueb94"  # nf-cod-menu
    DELETE = "\U0000ee23"  # nf-md-delete
    EXPORT = "\U000f0207"  # nf-md-export
    IMPORT = "\U000f02fa"  # nf-md-import
    ERASER = "\U000f0b89"  # nf-md-eraser
    COG = "\U000f0493"  # nf-md-cog
    FORMAT_FONT = "\U000f031b"  # nf-md-format_font
    FORMAT_LINE_STYLE = "\U000f05c8"  # nf-md-format_line_style
    ZOOM_IN = "\ueb81"  # nf-cod-zoom_in
    ZOOM_OUT = "\ueb82"
    ZOOM_RESET = "\uf50d"  # nf-md-magnify_remove_outline

    # ── Sketch pad tools ───────────────────────────────────────────
    TOOL_SELECT = "\U000f0485"  # nf-md-cursor_default
    TOOL_PAN = "\U000f0bb4"  # nf-md-pan
    TOOL_RECTANGLE = "\U000f0e5f"  # nf-md-rectangle
    TOOL_ARROW = "\U000f0443"
    TOOL_ARROW_DOTTED = "\U000f01d8"  # nf-md-arrow
    TOOL_ACTOR = "\U000f0004"  # nf-md-account
    TOOL_TOPIC = "\U000f1ab7"
    TOOL_DATABASE = "\ueace"
    TOOL_CLOUD = "\uebaa"  # nf-cod-cloud
    TOOL_SETTINGS = "\U000f066a"

    # ── Dev Pad activity icons ────────────────────────────────────
    SAVE = "\uf0c7"  # nf-fa-floppy_o
    SEARCH = "\uf002"  # nf-fa-search
    TERMINAL = "\uf120"  # nf-fa-terminal
    BUG = "\uf188"  # nf-fa-bug
    EYE = "\uf06e"  # nf-fa-eye
    QUESTION = "\uf128"  # nf-fa-question
    ARROW_UP = "\uf062"  # nf-fa-arrow_up
    ARROW_DOWN = "\uf063"  # nf-fa-arrow_down
    CHEVRON_DOWN = "\U000f0140"  # nf-md-chevron_down
    PIN = "\uf08d"  # nf-fa-thumb_tack
    LIST = "\uf03a"  # nf-fa-list
    HAMMER = "\uf0e3"  # nf-fa-gavel
    FLASK = "\uf0c3"  # nf-fa-flask
    CHECK = "\uf00c"  # nf-fa-check
    ROBOT = "\U000f06a9"  # nf-md-robot
    THOUGHT_BUBBLE = "\uea61"  # nf-cod-lightbulb
    GIT_MERGE = "\ue727"  # nf-dev-git_merge
    CLIPBOARD = "\uf0ea"  # nf-fa-clipboard

    # ── Notifications / status ─────────────────────────────────────
    INFO = "\uea74"  # nf-cod-info
    SUCCESS = "\ueab2"  # nf-cod-check
    WARNING = "\uea6c"  # nf-cod-warning
    ERROR = "\uf057"  # nf-fa-times_circle
    ERROR_X = "\uea76"  # nf-cod-close
    MODIFIED_DOT = "\uea71"  # nf-cod-circle_filled
    STOP = "\uead7"  # nf-cod-debug_stop
    PLAY = "\uead8"  # nf-cod-debug_alt
    CONTINUE = "\ueacf"  # nf-cod-debug_continue
    STEP_OVER = "\uead6"  # nf-cod-debug_step_over
    STEP_INTO = "\U000f01b9"  # nf-md-debug_step_into
    STEP_OUT = "\U000f01b8"  # nf-md-debug_step_out
    RESTART = "\uead2"  # nf-cod-debug_restart
    UNDO_ARROW = "\uf0e2"  # nf-fa-undo

    # ── Git ─────────────────────────────────────────────────────────
    GIT_BRANCH = "\ue725"  # nf-dev-git_branch

    # ── File-type icons (status bar / general use) ─────────────────
    #  These mirror the Nerd Font file-type glyphs used across the IDE.
    FILE_PYTHON = "\ue73c"
    FILE_JS = "\ue74e"
    FILE_JSX = "\ue7ba"
    FILE_TS = "\ue628"
    FILE_TSX = "\ue7ba"
    FILE_HTML = "\ue736"
    FILE_CSS = "\ue749"
    FILE_SCSS = "\ue749"
    FILE_SASS = "\ue74b"
    FILE_LESS = "\ue758"
    FILE_JSON = "\ue60b"
    FILE_YAML = "\ue6a8"
    FILE_XML = "\uf481"
    FILE_MD = "\ue73e"
    FILE_RUST = "\ue7a8"
    FILE_GO = "\ue626"
    FILE_JAVA = "\ue738"
    FILE_RUBY = "\ue739"
    FILE_PHP = "\ue73d"
    FILE_SHELL = "\ue795"
    FILE_C = "\ue61e"
    FILE_CPP = "\ue61d"
    FILE_CSHARP = "\ue7b2"  # dev-csharp
    FILE_SWIFT = "\ue755"
    FILE_KOTLIN = "\ue634"
    FILE_SCALA = "\ue737"
    FILE_R = "\uf25d"
    FILE_JULIA = "\ue624"
    FILE_LUA = "\ue620"
    FILE_VIM = "\ue62b"
    FILE_SQL = "\ue706"
    FILE_GRAPHQL = "\ue662"
    FILE_DOCKER = "\ue7b0"
    FILE_TOML = "\ue6b2"
    FILE_INI = "\ue615"
    FILE_ENV = "\uf462"
    FILE_GITIGNORE = "\ue702"
    FILE_DART = "\ue798"
    FILE_VUE = "\ue6a0"
    FILE_SVELTE = "\ue697"
    FILE_LOCK = "\uf023"
    FILE_TEXT = "\uf15c"
    FILE_LOG = "\uf18d"
    FILE_IMAGE = "\uf1c5"
    FILE_PDF = "\uf1c1"
    FILE_ARCHIVE = "\uf410"
    FILE_SKETCH = "\uf040"
    FILE_WORKSPACE = "\uf1e0"
    FILE_MAKEFILE = "\ue779"
    FILE_LICENSE = "\ue60a"  # seti-license
    FILE_DEFAULT = "\uf15c"

    # ── Autocomplete kind icons ────────────────────────────────────
    KIND_FUNCTION = "ƒ"
    KIND_CLASS = "\U000f0b8a"  # nf-md-diamond
    KIND_PROPERTY = "\uea71"  # nf-cod-circle_filled
    KIND_KEYWORD = "κ"
    KIND_BUILTIN = "β"
    KIND_SNIPPET = "\U000f0633"  # nf-md-apple_keyboard_command
    KIND_VARIABLE = "ν"
    KIND_PARAMETER = "π"


# ── File-type icon lookup ──────────────────────────────────────────

_FILE_ICON_MAP = {
    ".py": IconsManager.FILE_PYTHON,
    ".js": IconsManager.FILE_JS,
    ".jsx": IconsManager.FILE_JSX,
    ".ts": IconsManager.FILE_TS,
    ".tsx": IconsManager.FILE_TSX,
    ".html": IconsManager.FILE_HTML,
    ".htm": IconsManager.FILE_HTML,
    ".css": IconsManager.FILE_CSS,
    ".scss": IconsManager.FILE_SCSS,
    ".sass": IconsManager.FILE_SASS,
    ".less": IconsManager.FILE_LESS,
    ".json": IconsManager.FILE_JSON,
    ".yaml": IconsManager.FILE_YAML,
    ".yml": IconsManager.FILE_YAML,
    ".xml": IconsManager.FILE_XML,
    ".md": IconsManager.FILE_MD,
    ".markdown": IconsManager.FILE_MD,
    ".rs": IconsManager.FILE_RUST,
    ".go": IconsManager.FILE_GO,
    ".java": IconsManager.FILE_JAVA,
    ".rb": IconsManager.FILE_RUBY,
    ".php": IconsManager.FILE_PHP,
    ".sh": IconsManager.FILE_SHELL,
    ".bash": IconsManager.FILE_SHELL,
    ".zsh": IconsManager.FILE_SHELL,
    ".fish": IconsManager.FILE_SHELL,
    ".c": IconsManager.FILE_C,
    ".h": IconsManager.FILE_C,
    ".cpp": IconsManager.FILE_CPP,
    ".hpp": IconsManager.FILE_CPP,
    ".cs": IconsManager.FILE_CSHARP,
    ".swift": IconsManager.FILE_SWIFT,
    ".kt": IconsManager.FILE_KOTLIN,
    ".scala": IconsManager.FILE_SCALA,
    ".r": IconsManager.FILE_R,
    ".jl": IconsManager.FILE_JULIA,
    ".lua": IconsManager.FILE_LUA,
    ".vim": IconsManager.FILE_VIM,
    ".sql": IconsManager.FILE_SQL,
    ".graphql": IconsManager.FILE_GRAPHQL,
    ".docker": IconsManager.FILE_DOCKER,
    ".dockerfile": IconsManager.FILE_DOCKER,
    ".toml": IconsManager.FILE_TOML,
    ".ini": IconsManager.FILE_INI,
    ".cfg": IconsManager.FILE_INI,
    ".conf": IconsManager.FILE_INI,
    ".env": IconsManager.FILE_ENV,
    ".gitignore": IconsManager.FILE_GITIGNORE,
    ".dart": IconsManager.FILE_DART,
    ".vue": IconsManager.FILE_VUE,
    ".svelte": IconsManager.FILE_SVELTE,
    ".lock": IconsManager.FILE_LOCK,
    ".txt": IconsManager.FILE_TEXT,
    ".log": IconsManager.FILE_LOG,
    ".svg": IconsManager.FILE_IMAGE,
    ".png": IconsManager.FILE_IMAGE,
    ".jpg": IconsManager.FILE_IMAGE,
    ".jpeg": IconsManager.FILE_IMAGE,
    ".gif": IconsManager.FILE_IMAGE,
    ".ico": IconsManager.FILE_IMAGE,
    ".pdf": IconsManager.FILE_PDF,
    ".zip": IconsManager.FILE_ARCHIVE,
    ".tar": IconsManager.FILE_ARCHIVE,
    ".gz": IconsManager.FILE_ARCHIVE,
    ".zen_sketch": IconsManager.FILE_SKETCH,
}

_FILE_NAME_MAP = {
    "dockerfile": IconsManager.FILE_DOCKER,
    "makefile": IconsManager.FILE_MAKEFILE,
    "cmakelists.txt": IconsManager.FILE_MAKEFILE,
    "license": IconsManager.FILE_LICENSE,
    ".gitignore": IconsManager.FILE_GITIGNORE,
    ".env": IconsManager.FILE_ENV,
}


def get_file_icon(file_path: str) -> tuple[str, str]:
    """Return ``(icon_char, hex_color)`` for a file path.

    Uses the same color palette as the tree view (``ICON_COLORS``).
    """
    import os

    from treeview.tree_icons import ICON_COLORS

    ext = os.path.splitext(file_path)[1].lower()
    basename = os.path.basename(file_path).lower()

    # Check workspace extensions first
    from constants import WORKSPACE_EXTENSIONS

    for ws_ext in WORKSPACE_EXTENSIONS:
        if basename.endswith(ws_ext):
            return IconsManager.FILE_WORKSPACE, ICON_COLORS.get("default", "#6d8086")

    icon = _FILE_NAME_MAP.get(basename, _FILE_ICON_MAP.get(ext, IconsManager.FILE_DEFAULT))
    color = ICON_COLORS.get(
        os.path.basename(file_path),
        ICON_COLORS.get(ext, ICON_COLORS.get("default", "#6d8086")),
    )
    return icon, color


# ── Consistent icon rendering ──────────────────────────────────────


def create_icon_label(icon: str, size_pt: int | None = None) -> Gtk.Label:
    """Create a ``Gtk.Label`` displaying *icon* at a consistent size.

    The label's font family is set to ``ICON_FONT_FAMILY`` (ZenIcons)
    so the glyph always renders from the bundled icon font.

    Parameters
    ----------
    icon:
        A single Unicode/Nerd-Font character (use an ``IconsManager.*`` constant).
    size_pt:
        Explicit font size in points.  When ``None`` the editor font size
        plus ``NERD_ICON_SIZE_OFFSET`` is used, which guarantees icons are
        always the same relative size as surrounding text.

    The label carries the ``zen-icon`` CSS class so that global CSS can
    fine-tune rendering if needed.
    """
    label = Gtk.Label(label=icon)
    label.add_css_class(ICON_SIZE_CSS_CLASS)

    if size_pt is None:
        from fonts import get_font_settings

        font_settings = get_font_settings("editor")
        size_pt = font_settings.get("size", 14) + NERD_ICON_SIZE_OFFSET

    attr_list = Pango.AttrList()
    attr_list.insert(Pango.attr_family_new(ICON_FONT_FAMILY))
    attr_list.insert(Pango.attr_size_new(size_pt * Pango.SCALE))
    label.set_attributes(attr_list)
    return label


# ── Icon font helpers ──────────────────────────────────────────────


def get_icon_font_name() -> str:
    """Return the icon font family name.

    Always returns ``ICON_FONT_FAMILY`` ("ZenIcons") — the bundled
    Nerd Font subset that is registered at startup.  This replaces
    the old ``get_nerd_font_name()`` which searched for system fonts.
    """
    return ICON_FONT_FAMILY


def apply_icon_font(label: Gtk.Label, size_pt: int | None = None) -> None:
    """Set ``ICON_FONT_FAMILY`` on *label* via Pango attributes.

    Use this when a label already exists and you need to ensure the
    icon glyph renders from ZenIcons rather than the text font.

    Parameters
    ----------
    label:
        An existing ``Gtk.Label`` whose text is an icon character.
    size_pt:
        Optional explicit font size.  When ``None`` only the family
        attribute is set, preserving the label's current size.
    """
    attrs = label.get_attributes() or Pango.AttrList()
    attrs.insert(Pango.attr_family_new(ICON_FONT_FAMILY))
    if size_pt is not None:
        attrs.insert(Pango.attr_size_new(size_pt * Pango.SCALE))
    label.set_attributes(attrs)


def icon_font_css_rule() -> str:
    """Return a CSS snippet that sets the icon font on ``.zen-icon`` labels.

    Embed this in any component-level CSS provider so that icon labels
    always use the bundled ZenIcons font::

        css = f'''
            {icon_font_css_rule()}
            /* …other rules… */
        '''
    """
    return f"""
        .{ICON_SIZE_CSS_CLASS} {{
            font-family: "{ICON_FONT_FAMILY}";
        }}
    """


def icon_font_fallback(base_family: str) -> str:
    """Prepend ``ICON_FONT_FAMILY`` to *base_family* for Pango/CSS fallback.

    Returns a comma-separated font family string such as
    ``"ZenIcons, monospace"`` so Pango renders Nerd Font PUA codepoints
    from ZenIcons while falling back to *base_family* for regular text.
    """
    return f"{ICON_FONT_FAMILY}, {base_family}"
