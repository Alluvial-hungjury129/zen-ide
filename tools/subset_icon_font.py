#!/usr/bin/env python3
"""Generate a minimal icon-only font from a Nerd Font source.

Extracts only the Unicode codepoints actually used by Zen IDE's icon system
(defined in src/icons/icon_manager.py and src/treeview/tree_icons.py) into a
tiny TTF file.

Usage:
    python tools/subset_icon_font.py

Output:
    src/fonts/resources/ZenIcons.ttf  (~30-50 KB vs ~3 MB per full Nerd Font)
"""

import os
import sys

# Ensure src/ is on the path so we can import the icon definitions
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from icons.icon_manager import Icons  # noqa: E402

from treeview.tree_icons import (  # noqa: E402
    CHEVRON_COLLAPSED,
    CHEVRON_EXPANDED,
    NERD_FILE_ICONS,
    NERD_FOLDER_CLOSED,
    NERD_FOLDER_OPEN,
    NERD_NAME_ICONS,
)

# ── Collect all unique codepoints from Icons class ──────────────────
ICON_CODEPOINTS: set[int] = set()
for attr in dir(Icons):
    if attr.startswith("_"):
        continue
    value = getattr(Icons, attr)
    if isinstance(value, str) and len(value) == 1:
        ICON_CODEPOINTS.add(ord(value))

# Collect codepoints from tree view icon maps
for icon_str in NERD_FILE_ICONS.values():
    for ch in icon_str:
        cp = ord(ch)
        if cp > 0x7F:  # skip ASCII (spaces, etc.)
            ICON_CODEPOINTS.add(cp)

for icon_str in NERD_NAME_ICONS.values():
    for ch in icon_str:
        cp = ord(ch)
        if cp > 0x7F:
            ICON_CODEPOINTS.add(cp)

for icon_str in (NERD_FOLDER_CLOSED, NERD_FOLDER_OPEN, CHEVRON_EXPANDED, CHEVRON_COLLAPSED):
    for ch in icon_str:
        cp = ord(ch)
        if cp > 0x7F:
            ICON_CODEPOINTS.add(cp)

# Keep .notdef and space for a valid font
ICON_CODEPOINTS.add(0x0020)  # space


def main():
    from fontTools.subset import Options, Subsetter
    from fontTools.ttLib import TTFont

    src_dir = os.path.join(os.path.dirname(__file__), "..", "src", "fonts", "resources")
    source_font = os.path.join(src_dir, "SymbolsNerdFont-Regular.ttf")
    output_font = os.path.join(src_dir, "ZenIcons.ttf")

    if not os.path.exists(source_font):
        print(f"ERROR: Source font not found: {source_font}")
        sys.exit(1)

    font = TTFont(source_font)

    # Configure subsetting options
    options = Options()
    options.layout_features = ["*"]  # keep all OpenType features
    options.name_IDs = ["*"]  # keep name records
    options.notdef_outline = True
    options.recalc_bounds = True
    options.recalc_timestamp = True
    options.drop_tables = [
        "DSIG",  # digital signature (invalid after subsetting)
    ]

    subsetter = Subsetter(options=options)
    subsetter.populate(unicodes=ICON_CODEPOINTS)
    subsetter.subset(font)

    # Rename the font family so it doesn't clash with the full Nerd Font
    _rename_font(font, "ZenIcons")

    font.save(output_font)

    source_size = os.path.getsize(source_font)
    output_size = os.path.getsize(output_font)
    glyph_count = len(ICON_CODEPOINTS)

    print(f"Source:  {source_font}")
    print(f"         {source_size:,} bytes ({source_size / 1024:.0f} KB)")
    print(f"Output:  {output_font}")
    print(f"         {output_size:,} bytes ({output_size / 1024:.0f} KB)")
    print(f"Glyphs:  {glyph_count} codepoints retained")
    print(f"Saving:  {(1 - output_size / source_size) * 100:.1f}% reduction")


def _rename_font(font, new_name: str) -> None:
    """Update the font's name table so the OS sees it as a new family."""
    name_table = font["name"]
    for record in name_table.names:
        # nameID 1 = Family, 4 = Full Name, 6 = PostScript Name
        if record.nameID in (1, 4, 6):
            record.string = new_name


if __name__ == "__main__":
    main()
