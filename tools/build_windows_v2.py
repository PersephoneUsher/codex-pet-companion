"""Build without collecting unrelated DLLs from an inherited desktop PATH."""
from pathlib import Path
import os
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    windows = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    os.environ["PATH"] = os.pathsep.join(map(str, (
        Path(sys.executable).parent, Path(sys.base_prefix),
        windows / "System32", windows,
    )))
    import PyInstaller.__main__
    PyInstaller.__main__.run([
        "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", "CodexPetCompanion", "--icon", "app_icon.ico",
        "--add-data", "icons;icons", "--add-data", "builtin_pets;builtin_pets",
        "--add-data", "README.md;.", "--paths", str(root),
        "codex_pet_companion/main.py",
    ])
    PyInstaller.__main__.run([
        "--noconfirm", "--clean", "--onefile", "--console",
        "--name", "updater", "tools/updater.py",
    ])


if __name__ == "__main__":
    main()
