from __future__ import annotations

import json
import shutil
import zipfile
import tempfile
import re

from .pets import load_pet_from_folder
from pathlib import Path

def import_pet_pack(zip_path: Path, data_root: Path) -> str:
    pets_root = data_root / "pets"
    pets_root.mkdir(parents=True, exist_ok=True)
    # Validate in staging before replacing an existing installed pet.
    with zipfile.ZipFile(zip_path, "r") as archive, tempfile.TemporaryDirectory(dir=pets_root) as temp:
        names = [name for name in archive.namelist() if not name.endswith("/")]
        candidates = [n for n in names if Path(n).name == "pet.json"]
        if len(candidates) != 1:
            raise ValueError("Archive must contain exactly one pet.json.")
        manifest_name = candidates[0]
        manifest = json.loads(archive.read(manifest_name).decode("utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError("pet.json must be an object.")
        pet_id = str(manifest.get("id") or Path(manifest_name).parent.name).strip()
        if (not pet_id or pet_id in {".", ".."} or re.search(r'[<>:"/\\|?*\x00-\x1f]', pet_id)
                or pet_id.endswith((".", " "))):
            raise ValueError("pet.json contains an invalid id.")
        staging = Path(temp) / "pet"
        staging.mkdir()
        prefix = manifest_name.replace("\\", "/").rsplit("/", 1)[0] + "/" if "/" in manifest_name.replace("\\", "/") else ""
        for name in names:
            normalized = name.replace("\\", "/")
            if prefix and not normalized.startswith(prefix):
                continue
            rel = normalized[len(prefix):]
            out = staging / rel
            if not rel or not out.resolve().is_relative_to(staging.resolve()) or ":" in rel:
                raise ValueError("Archive contains an unsafe path.")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(archive.read(name))
        if load_pet_from_folder(staging, "import") is None:
            raise ValueError("Invalid pet pack: use a PNG/WebP atlas of 1536x1872 (v1) or 1536x2288 (v2), matching spriteVersionNumber when supplied.")
        target = pets_root / pet_id
        if not target.resolve().is_relative_to(pets_root.resolve()) or target.is_symlink():
            raise ValueError("Invalid pet destination.")
        backup = Path(temp) / "previous"
        if target.exists():
            target.rename(backup)
        try:
            shutil.move(str(staging), str(target))
        except OSError:
            if backup.exists():
                backup.rename(target)
            raise
    return pet_id


def export_pet_pack(folder: Path, pet_id: str, output: Path) -> None:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file in folder.rglob("*"):
            if file.is_file():
                archive.write(file, arcname=str(Path(pet_id) / file.relative_to(folder)))
