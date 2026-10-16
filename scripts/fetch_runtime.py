#!/usr/bin/env python3
"""Fetch pinned public assets; validate every byte before using it."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, target: Path, expected: str) -> None:
    if target.is_file() and sha256(target) == expected:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".partial")
    print(f"Downloading {target.name} ...", flush=True)
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "OpenFunASR-setup"})
        with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as out:
            shutil.copyfileobj(response, out)
        if sha256(partial) != expected:
            raise RuntimeError(f"SHA-256 mismatch: {target.name}")
        os.replace(partial, target)
    finally:
        partial.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-models", type=Path, help="Reuse an existing model directory after checksum validation")
    args = parser.parse_args()
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        parser.error("This desktop runtime package requires an Apple Silicon Mac")
    manifest = json.loads((ROOT / "runtime-manifest.json").read_text())
    assets = ROOT / "runtime-assets"
    for item in manifest["models"]:
        target = assets / "models" / item["name"]
        if args.seed_models and not target.exists():
            source = args.seed_models / item["name"]
            if source.is_file() and sha256(source) == item["sha256"]:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
        download(item["url"], target, item["sha256"])
    runtime = manifest["runtime"]
    archive = ROOT / ".cache" / "funasr-runtime.tar.gz"
    download(runtime["url"], archive, runtime["sha256"])
    # Extract just one regular file, never archive paths, symlinks or executable scripts.
    with tarfile.open(archive, "r:gz") as package:
        matches = [m for m in package.getmembers() if m.isfile() and Path(m.name).name == runtime["member"]]
        if len(matches) != 1:
            raise RuntimeError("Expected exactly one Fun-ASR CLI in the verified archive")
        stream = package.extractfile(matches[0])
        if stream is None:
            raise RuntimeError("Runtime archive is incomplete")
        binary = assets / "bin" / runtime["member"]
        binary.parent.mkdir(parents=True, exist_ok=True)
        temporary = binary.with_suffix(".partial")
        try:
            with stream, temporary.open("wb") as out:
                shutil.copyfileobj(stream, out)
            temporary.chmod(0o755)
            os.replace(temporary, binary)
        finally:
            temporary.unlink(missing_ok=True)
    print("Verified Fun-ASR runtime and all four model files.")


if __name__ == "__main__":
    main()
