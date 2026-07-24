# PyInstaller spec for the single-file executable.
#
# Build locally with:
#   pip install -r requirements-dev.txt
#   pyinstaller packaging/autoticker.spec --clean --noconfirm
#
# The result lands in dist/. CI builds this same spec on Windows, macOS, and
# Linux runners — see .github/workflows/release.yml.

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

# SPECPATH is injected by PyInstaller; the project root is its parent.
ROOT = Path(SPECPATH).parent

# The IANA timezone database is a directory of data files, so it has to be
# copied in explicitly — PyInstaller's code analysis can't see it. Without this
# the binary raises ZoneInfoNotFoundError on any host with no system tz
# database, which notably includes every Windows machine.
tzdata_files = collect_data_files("tzdata")

a = Analysis(
    [str(ROOT / "bot.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=tzdata_files,
    # discord.py and aiohttp pull these in dynamically, so PyInstaller's static
    # analysis can miss them.
    hiddenimports=[
        "aiohttp",
        "aiodns",
        "discord",
        "dotenv",
        "zoneinfo",
        "tzdata",
    ],
    hookspath=[],
    runtime_hooks=[],
    # Trim GUI/stdlib bulk the bot never touches, for a smaller binary.
    excludes=[
        "tkinter",
        "unittest",
        "pydoc",
        "doctest",
        "test",
        "pytest",
        "setuptools",
        "pip",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="autoticker-bot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # UPX often trips antivirus heuristics on Windows; not worth the size win.
    upx=False,
    # Keep the console: the setup wizard and logs need somewhere to print.
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
