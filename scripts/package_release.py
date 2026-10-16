"""Build a flat full package. No network access or publication."""
import argparse
import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path


def build(root, launcher, helper, output, sequence, commit, client_id):
    if sequence <= 0 or not re.fullmatch(r"[a-f0-9]{40}", commit):
        raise ValueError("Invalid sequence/commit")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", client_id):
        raise ValueError("Configure the public GitHub App client ID")
    output.mkdir(parents=True, exist_ok=False)
    stage = output / "package"
    stage.mkdir()
    for source in (launcher, helper):
        for item in source.iterdir():
            if not item.is_file():
                raise ValueError(f"Format 1 requires flat framework-dependent output: {item.name}")
            target = stage / item.name
            if target.exists() and target.read_bytes() != item.read_bytes():
                raise ValueError(f"Conflicting dependency {item.name}")
            shutil.copyfile(item, target)
    for name in ("client_feature_loader.dll", "client_feature.py", "inject.py", "run_client_feature.ps1"):
        shutil.copyfile(root / name, stage / name)
    model = root / "yin_yang_duel_model.json"
    if model.exists():
        shutil.copyfile(model, stage / model.name)
    identity = dict(Schema=1, Sequence=sequence, Commit=commit, Channel="stable", PackageFormat=1)
    def write(path, value):
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    write(stage / "build.json", identity)
    write(stage / "distribution.json", "lirin-private-package-v1")
    write(stage / "updater.json", dict(ClientId=client_id))
    files = [dict(Path=p.name, Size=p.stat().st_size, Sha256=hashlib.sha256(p.read_bytes()).hexdigest())
             for p in sorted(stage.iterdir())]
    write(stage / "package.json", dict(Build=identity, Files=files))
    archive = output / "release.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(stage.iterdir()):
            z.write(p, p.name)
    write(output / "update-manifest.json", dict(Build=identity, Files=files, ArchiveSize=archive.stat().st_size,
                                               ArchiveSha256=hashlib.sha256(archive.read_bytes()).hexdigest()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("root", "launcher", "helper", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--sequence", type=int, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--client-id", required=True)
    build(**vars(parser.parse_args()))
