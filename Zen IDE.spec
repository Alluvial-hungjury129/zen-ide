# -*- mode: python ; coding: utf-8 -*-

import glob
import os
import subprocess

# Detect Homebrew prefix
BREW = subprocess.check_output(['brew', '--prefix']).decode().strip()
TYPELIB_DIR = os.path.join(BREW, 'lib', 'girepository-1.0')


def _brew_lib(name):
    """Resolve a Homebrew library by unversioned symlink — no hardcoded versions."""
    path = os.path.join(BREW, 'lib', name)
    if os.path.exists(path):
        return os.path.realpath(path)
    raise FileNotFoundError(
        f"Homebrew library not found: {path}\n"
        f"Install it with:  brew install <package>"
    )


# Explicitly bundle Vte and GdkMacos (no built-in PyInstaller hooks)
extra_binaries = [
    (_brew_lib('libvte-2.91-gtk4.0.dylib'), '.'),
    (_brew_lib('libgnutls.dylib'), '.'),
    (_brew_lib('libsimdutf.dylib'), '.'),
]

extra_typelibs = [
    (os.path.join(TYPELIB_DIR, 'Vte-3.91.typelib'), 'gi_typelibs'),
    (os.path.join(TYPELIB_DIR, 'GdkMacos-4.0.typelib'), 'gi_typelibs'),
]

a = Analysis(
    ['src/zen_ide.py'],
    pathex=['src'],
    binaries=extra_binaries,
    datas=[
        ('src/fonts/resources', 'fonts/resources'),
        ('zen_icon.png', '.'),
        ('pyproject.toml', '.'),
    ] + extra_typelibs,
    hiddenimports=[
        'gi',
        'gi._error',
        'gi._option',
        'gi._enum',
        'gi.overrides',
        'gi.overrides.Gtk',
        'gi.overrides.Gdk',
        'gi.overrides.GLib',
        'gi.overrides.GObject',
        'gi.overrides.Gio',
        'gi.overrides.Pango',
        'gi.overrides.GdkPixbuf',
        'gi.repository.Gtk',
        'gi.repository.Gdk',
        'gi.repository.GdkPixbuf',
        'gi.repository.GdkMacos',
        'gi.repository.Gio',
        'gi.repository.GLib',
        'gi.repository.GObject',
        'gi.repository.Pango',
        'gi.repository.GtkSource',
        'gi.repository.Adw',
        'gi.repository.Graphene',
        'gi.repository.Gsk',
        'gi.repository.HarfBuzz',
        'gi.repository.Vte',
        'gi.repository.cairo',
        'gi.repository.freetype2',
        'asyncio',
        'cairo',
        'cmarkgfm',
        'cmarkgfm.cmark',
        'yaml',
        'yaml._yaml',
        'yaml.composer',
        'yaml.constructor',
        'yaml.cyaml',
        'yaml.dumper',
        'yaml.emitter',
        'yaml.error',
        'yaml.events',
        'yaml.loader',
        'yaml.nodes',
        'yaml.parser',
        'yaml.reader',
        'yaml.representer',
        'yaml.resolver',
        'yaml.scanner',
        'yaml.serializer',
        'yaml.tokens',
        'psutil',
        'tree_sitter',
        'watchfiles',
        'watchfiles._rust_notify',
        'objc',
        'Cocoa',
        'Foundation',
        'AppKit',
        'ai.spinner',
        'ai.tab_title_inferrer',
        'ai.ai_chat_tabs',
        'ai.ai_chat_terminal',
        'ai.ai_process_tracker',
        'ai.ansi_buffer',
        'ai.anthropic_http_provider',
        'ai.block_cursor_text_view',
        'ai.chat_canvas',
        'ai.copilot_http_provider',
        'ai.dock_badge',
        'ai.markdown_formatter',
        'ai.openai_http_provider',
        'ai.terminal_markdown_renderer',
        'ai.tool_definitions',
        'ai.tool_executor',
        'themes.definitions',
        'themes.definitions.ansi_blows',
        'themes.definitions.aura_dark',
        'themes.definitions.aurora_borealis',
        'themes.definitions.c64_dreams',
        'themes.definitions.c64_videogame_dreams',
        'themes.definitions.catppuccin_latte',
        'themes.definitions.catppuccin_mocha',
        'themes.definitions.cga_dream',
        'themes.definitions.cyberdream',
        'themes.definitions.dracula',
        'themes.definitions.ega_dreams',
        'themes.definitions.everforest_dark',
        'themes.definitions.everforest_light',
        'themes.definitions.fluoromachine',
        'themes.definitions.gruvbox_dark',
        'themes.definitions.gruvbox_light',
        'themes.definitions.jellybeans',
        'themes.definitions.kanagawa',
        'themes.definitions.laserwave',
        'themes.definitions.matrix',
        'themes.definitions.melange_dark',
        'themes.definitions.melange_light',
        'themes.definitions.modus_vivendi',
        'themes.definitions.new_aura_dark',
        'themes.definitions.nyoom',
        'themes.definitions.one_dark',
        'themes.definitions.oxocarbon',
        'themes.definitions.retrobox',
        'themes.definitions.solarized_light',
        'themes.definitions.spacevim',
        'themes.definitions.synthwave84',
        'themes.definitions.terracotta',
        'themes.definitions.tokyonight',
        'themes.definitions.zen_dark',
        'themes.definitions.zen_light',
        'themes.definitions.zen_style',
        'themes.definitions.zengruv',
        'themes.definitions.zx_dreams',
    ],
    hookspath=['tools/pyinstaller_hooks'],
    hooksconfig={
        'gi': {
            'module-versions': {
                'Gtk': '4.0',
                'Gdk': '4.0',
                'Gsk': '4.0',
                'GdkMacos': '4.0',
                'GtkSource': '5',
                'Adw': '1',
                'Graphene': '1.0',
                'Vte': '3.91',
                'HarfBuzz': '0.0',
                'GdkPixbuf': '2.0',
                'Pango': '1.0',
            },
            'icons': ['Adwaita', 'hicolor'],
            'themes': ['Default'],
        },
    },
    runtime_hooks=['tools/pyinstaller_hooks/rthook_gi.py'],
    excludes=[
        'tkinter', 'unittest', 'pydoc', 'pydoc_data', 'PIL', 'Pillow',
        'multiprocessing', 'xmlrpc', 'lib2to3', 'ensurepip',
        'idlelib', 'turtledemo', 'turtle', 'doctest', 'test',
    ],
    noarchive=True,
    optimize=2,
)

# Prune locale data (21MB → <1MB) — keep only English, saves startup I/O
a.datas = [
    (dest, src, typ) for dest, src, typ in a.datas
    if not dest.startswith('share/locale/')
    or dest.startswith(('share/locale/en/', 'share/locale/en_US/'))
]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='zen-ide-core',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file='entitlements.plist',
    icon=['zen_icon.icns'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=True,
    upx=False,
    upx_exclude=[],
    name='Zen IDE',
)

app = BUNDLE(
    coll,
    name='Zen IDE.app',
    icon='zen_icon.icns',
    bundle_identifier='com.zen-ide.app',
    info_plist={
        'CFBundleDisplayName': 'Zen IDE',
        'CFBundleShortVersionString': '0.1.0',
        'CFBundleExecutable': 'zen-launcher',
        'NSHighResolutionCapable': True,
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'Text Document',
                'CFBundleTypeRole': 'Editor',
                'LSHandlerRank': 'Alternate',
                'LSItemContentTypes': [
                    'public.text',
                    'public.plain-text',
                    'public.source-code',
                    'public.script',
                    'public.shell-script',
                    'public.python-script',
                    'public.ruby-script',
                    'public.perl-script',
                    'public.c-source',
                    'public.c-plus-plus-source',
                    'public.c-header',
                    'public.objective-c-source',
                    'public.swift-source',
                    'net.daringfireball.markdown',
                    'public.json',
                    'public.xml',
                    'public.yaml',
                    'com.netscape.javascript-source',
                    'public.css',
                    'public.html',
                ],
            },
            {
                'CFBundleTypeName': 'Folder',
                'CFBundleTypeRole': 'Viewer',
                'LSHandlerRank': 'Alternate',
                'LSItemContentTypes': ['public.folder'],
            },
        ],
    },
)

# Copy native launcher into the .app bundle AFTER BUNDLE creates it
# (files manually added to COLLECT output are NOT picked up by BUNDLE)
import shutil
launcher_src = os.path.join('tools', 'launcher', 'zen-launcher')
launcher_dst = os.path.join('dist', 'Zen IDE.app', 'Contents', 'MacOS', 'zen-launcher')
if os.path.exists(launcher_src):
    shutil.copy2(launcher_src, launcher_dst)
