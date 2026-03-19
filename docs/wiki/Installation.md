# Installation & First Launch

## System Requirements

| Requirement | Minimum |
|---|---|
| Python | 3.13+ |
| OS | macOS 12+ or Linux (X11/Wayland) |
| GTK4 | 4.x (via Homebrew or apt) |
| GtkSourceView | 5.x |
| VTE | 0.70+ (terminal emulator) |

## Install System Dependencies

```bash
# macOS
make install-system-deps   # runs: brew install gtk4 gtksourceview5 libadwaita vte3 pygobject3

# Linux (Debian/Ubuntu)
make install-system-deps   # runs: apt install libgtk-4-dev libgtksourceview-5-dev libvte-2.91-gtk4-dev
```

## Install Zen IDE

```bash
# Clone and install
git clone <repo-url> zen_ide
cd zen_ide
make install           # Install Python dependencies with uv
make install-dev       # (optional) Install dev tools: pytest, ruff
```

## Running

```bash
make run               # Launch the IDE
```

## Install the `code` CLI Command

Open Zen IDE from any terminal:

```bash
make install-cli       # Installs the `code` command to your PATH
```

Then from any terminal:

```bash
code .                 # Open current directory in Zen IDE
code myfile.py         # Open a specific file
```

## Linux Desktop Entry

```bash
make install-desktop   # Install .desktop file and icon for app launchers
```

## First Launch

On first launch, Zen IDE will:

1. **Create the user directory** at `~/.zen_ide/` with default settings
2. **Detect Nerd Fonts** on your system and cache the result
3. **Show the Welcome Screen** with the ASCII logo and keyboard shortcut reference
4. **Auto-detect AI providers** (GitHub Copilot or Claude Code if installed)

> **Tip:** Press `Cmd+Shift+/` (macOS) or `Ctrl+Shift+/` (Linux) at any time to see all keyboard shortcuts.

## Building a Standalone App (macOS)

```bash
make install-build     # Install PyInstaller/Nuitka
make dist              # Build .app bundle in dist/
```
