"""
Build script — packages the mod into a .ts4script file and optionally installs it.

Usage:
  python build.py           Build and auto-install to Sims 4 Mods folder
  python build.py --build   Build only (don't install)
"""
import os
import sys
import zipfile
import shutil

MOD_NAME = "ClaudeAI"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(SCRIPT_DIR, "src")
OUTPUT_FILE = os.path.join(SCRIPT_DIR, f"{MOD_NAME}.ts4script")
CONFIG_FILE = os.path.join(SCRIPT_DIR, "claude_config.cfg")


def find_mods_folder():
    """Attempt to locate the Sims 4 Mods folder on this machine."""
    docs = os.path.expanduser("~/Documents")
    candidates = [
        # Windows
        os.path.join(docs, "Electronic Arts", "The Sims 4", "Mods"),
        # Mac
        os.path.join(docs, "Electronic Arts", "The Sims 4", "Mods"),
        os.path.expanduser("~/Documents/Electronic Arts/The Sims 4/Mods"),
    ]
    for path in candidates:
        if os.path.isdir(path):
            return path
    return None


def build():
    if not os.path.isdir(SRC_DIR):
        print(f"ERROR: src/ directory not found at {SRC_DIR}")
        sys.exit(1)

    py_files = []
    for root, _dirs, files in os.walk(SRC_DIR):
        for fname in files:
            if fname.endswith(".py"):
                full_path = os.path.join(root, fname)
                arc_path = os.path.relpath(full_path, SRC_DIR)
                py_files.append((full_path, arc_path))

    if not py_files:
        print("ERROR: No .py files found in src/")
        sys.exit(1)

    print(f"Building {MOD_NAME}.ts4script …")
    with zipfile.ZipFile(OUTPUT_FILE, "w", zipfile.ZIP_DEFLATED) as zf:
        for full_path, arc_path in sorted(py_files, key=lambda x: x[1]):
            zf.write(full_path, arc_path)
            print(f"  + {arc_path}")

    size_kb = os.path.getsize(OUTPUT_FILE) / 1024
    print(f"\nBuilt: {OUTPUT_FILE} ({size_kb:.1f} KB, {len(py_files)} files)")
    return OUTPUT_FILE


def install(script_file):
    mods_folder = find_mods_folder()
    if not mods_folder:
        print("\nCould not auto-detect Sims 4 Mods folder.")
        print(f"Manually copy these files to your Mods folder:")
        print(f"  {script_file}")
        if os.path.exists(CONFIG_FILE):
            print(f"  {CONFIG_FILE}")
        return

    print(f"\nInstalling to: {mods_folder}")

    dest_script = os.path.join(mods_folder, os.path.basename(script_file))
    shutil.copy2(script_file, dest_script)
    print(f"  Installed: {os.path.basename(dest_script)}")

    dest_config = os.path.join(mods_folder, "claude_config.cfg")
    if not os.path.exists(dest_config):
        if os.path.exists(CONFIG_FILE):
            shutil.copy2(CONFIG_FILE, dest_config)
            print(f"  Installed: claude_config.cfg")
            print()
            print("=" * 60)
            print("  NEXT STEP: Edit claude_config.cfg in your Mods folder")
            print("  and replace YOUR_API_KEY_HERE with your real API key.")
            print("  Get a key at: https://console.anthropic.com/")
            print("=" * 60)
    else:
        print(f"  Skipped config (already exists — your API key is safe)")

    print()
    print("Installation complete! Launch The Sims 4 and make sure:")
    print("  • Game Options → Other → Enable Custom Content and Mods ✓")
    print("  • Game Options → Other → Enable Script Mods ✓")
    print("  • Restart the game if it was already running")
    print()
    print("Then open the cheat console (Ctrl+Shift+C) and type: claude.status")


if __name__ == "__main__":
    build_only = "--build" in sys.argv
    script = build()
    if not build_only:
        install(script)
