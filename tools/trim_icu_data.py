#!/usr/bin/env python3
"""Trim ICU data in a PyInstaller-built macOS app bundle.

Extracts the ICU data from libicudata.XX.dylib, removes unused locale/converter
data, and rebuilds a minimal dylib. Typically saves ~25 MB for an English-only
code editor.

Usage:
    python3 tools/trim_icu_data.py dist/Zen\\ IDE.app

Requires: ICU tools (icupkg, genccode) from Homebrew's icu4c package.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Items to KEEP in the trimmed ICU data.
# Everything not listed here is removed.
KEEP_PREFIXES = [
    "brkitr/",  # break iterators — essential for text segmentation
    "translit/",  # transliteration — used by GTK/Pango
]

KEEP_COLL = {
    "coll/en.res",
    "coll/en_US.res",
    "coll/en_US_POSIX.res",
    "coll/res_index.res",
    "coll/root.res",
    "coll/ucadata.icu",
}

KEEP_LOCALES = {
    "en.res",
    "en_US.res",
    "en_US_POSIX.res",
    "en_GB.res",
    "en_001.res",
    "en_150.res",
    "en_AU.res",
    "en_CA.res",
}

KEEP_CORE = {
    "cnvalias.icu",
    "confusables.cfu",
    "currencyNumericCodes.res",
    "dayPeriods.res",
    "genderList.res",
    "grammaticalFeatures.res",
    "icustd.res",
    "icuver.res",
    "keyTypeData.res",
    "langInfo.res",
    "metaZones.res",
    "metadata.res",
    "numberingSystems.res",
    "pluralRanges.res",
    "plurals.res",
    "pool.res",
    "res_index.res",
    "root.res",
    "supplementalData.res",
    "timezoneTypes.res",
    "uemoji.icu",
    "ulayout.icu",
    "unames.icu",
    "units.res",
    "uts46.nrm",
    "windowsZones.res",
    "zoneinfo64.res",
}

KEEP_EXTENSIONS = {".nrm"}  # all normalization files


def find_icu_tools():
    """Locate ICU command-line tools from Homebrew."""
    brew_prefix = subprocess.check_output(["brew", "--prefix", "icu4c"], text=True).strip()
    if not brew_prefix:
        brew_prefix = subprocess.check_output(["brew", "--prefix", "icu4c@78"], text=True).strip()
    icupkg = os.path.join(brew_prefix, "sbin", "icupkg")
    genccode = os.path.join(brew_prefix, "sbin", "genccode")
    if not os.path.exists(icupkg) or not os.path.exists(genccode):
        sys.exit(f"ICU tools not found at {brew_prefix}/sbin/")
    return icupkg, genccode


def find_icu_dylib(app_path: Path):
    """Find the libicudata dylib inside the Frameworks directory."""
    fw_dir = app_path / "Contents" / "Frameworks"
    for f in fw_dir.iterdir():
        if f.name.startswith("libicudata.") and f.name.endswith(".dylib"):
            return f
    sys.exit("libicudata dylib not found in Frameworks/")


def extract_dat(dylib_path: Path, dat_path: Path):
    """Extract the raw ICU .dat blob from the dylib's __const section."""
    import subprocess as sp

    otool_out = sp.check_output(["otool", "-l", str(dylib_path)], text=True)

    offset = size = None
    lines = otool_out.split("\n")
    # Find __const section inside __TEXT segment
    in_text_segment = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if "segname __TEXT" in stripped:
            in_text_segment = True
            continue
        if "segname " in stripped and "segname __TEXT" not in stripped:
            in_text_segment = False
            continue
        if in_text_segment and "sectname __const" in stripped:
            # Parse the section fields that follow
            for j in range(i + 1, min(i + 12, len(lines))):
                fld = lines[j].strip()
                parts = fld.split()
                if len(parts) == 2:
                    if parts[0] == "size":
                        size = int(parts[1], 16)
                    elif parts[0] == "offset":
                        offset = int(parts[1])
            break

    if offset is None or size is None:
        sys.exit("Could not find __TEXT.__const section in dylib")

    with open(dylib_path, "rb") as f:
        f.seek(offset)
        data = f.read(size)

    with open(dat_path, "wb") as f:
        f.write(data)


def should_keep(item: str) -> bool:
    """Decide whether an ICU data item should be kept."""
    for prefix in KEEP_PREFIXES:
        if item.startswith(prefix):
            return True
    if item in KEEP_COLL:
        return True
    if item in KEEP_CORE:
        return True
    if item in KEEP_LOCALES:
        return True
    _, ext = os.path.splitext(item)
    if ext in KEEP_EXTENSIONS:
        return True
    return False


def trim_dat(icupkg: str, dat_path: Path):
    """Remove unwanted items from the .dat file in-place."""
    result = subprocess.run(
        [icupkg, "-l", str(dat_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    all_items = result.stdout.strip().split("\n")
    remove = [item for item in all_items if not should_keep(item)]

    if not remove:
        print("  Nothing to remove — data is already minimal")
        return

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("\n".join(remove) + "\n")
        remove_list = f.name

    try:
        subprocess.run(
            [icupkg, "-r", remove_list, str(dat_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        print(f"  Removed {len(remove)} / {len(all_items)} items (kept {len(all_items) - len(remove)})")
    finally:
        os.unlink(remove_list)


def rebuild_dylib(genccode: str, dat_path: Path, dylib_path: Path):
    """Compile the trimmed .dat back into a dylib matching the original."""
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(
            [genccode, "-a", "gcc-darwin", "-d", tmpdir, str(dat_path)],
            check=True,
            capture_output=True,
            text=True,
        )

        asm_name = dat_path.stem + "_dat.S"
        obj_name = dat_path.stem + "_dat.o"
        asm_path = os.path.join(tmpdir, asm_name)
        obj_path = os.path.join(tmpdir, obj_name)

        # genccode generates symbol "_icudt78l_dat" (with 'l' for little-endian)
        # but libicuuc expects "_icudt78_dat" (no endian suffix). Patch the asm.
        with open(asm_path, "r") as f:
            asm_content = f.read()
        asm_content = asm_content.replace("_icudt78l_dat", "_icudt78_dat")
        with open(asm_path, "w") as f:
            f.write(asm_content)

        subprocess.run(
            ["cc", "-arch", "arm64", "-c", asm_path, "-o", obj_path],
            check=True,
            capture_output=True,
            text=True,
        )

        install_name = f"@rpath/{dylib_path.name}"
        out_dylib = os.path.join(tmpdir, dylib_path.name)
        subprocess.run(
            [
                "cc",
                "-arch",
                "arm64",
                "-dynamiclib",
                "-install_name",
                install_name,
                "-compatibility_version",
                "78.0.0",
                "-current_version",
                "78.2.0",
                "-o",
                out_dylib,
                obj_path,
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        shutil.copy2(out_dylib, dylib_path)


def main():
    if len(sys.argv) < 2:
        sys.exit(f"Usage: {sys.argv[0]} <path/to/App.app>")

    app_path = Path(sys.argv[1])
    if not app_path.exists():
        sys.exit(f"App not found: {app_path}")

    icupkg, genccode = find_icu_tools()
    dylib = find_icu_dylib(app_path)

    before_size = dylib.stat().st_size
    print(f"Trimming ICU data in {dylib.name} ({before_size / 1024 / 1024:.1f} MB)")

    with tempfile.TemporaryDirectory() as tmpdir:
        dat_path = Path(tmpdir) / "icudt78l.dat"

        print("  Extracting ICU data from dylib...")
        extract_dat(dylib, dat_path)

        print("  Removing unused ICU data...")
        trim_dat(icupkg, dat_path)

        print("  Rebuilding dylib...")
        rebuild_dylib(genccode, dat_path, dylib)

    after_size = dylib.stat().st_size
    saved = (before_size - after_size) / 1024 / 1024
    print(f"  {before_size / 1024 / 1024:.1f} MB → {after_size / 1024 / 1024:.1f} MB (saved {saved:.1f} MB)")


if __name__ == "__main__":
    main()
