"""Provision pinned official TimesFM 2.5 files without changing other environments."""

import hashlib
import json
import os
from pathlib import Path
import tarfile
import time
import urllib.request

ROOT = Path(os.environ.get("KRONOS_ROOT", "/home/yanxx/kronos-service"))
SOURCE = "2011cfb9a483296b893571df050b5d25a26ef9cc"
REVISION = "1d952420fba87f3c6dee4f240de0f1a0fbc790e3"
WEIGHT_SHA256 = "2f776efe6245e42b24bc4153ffdf61810140210e4bd3b01fb21f7aa779ab6ce8"


def checksum(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def download(url: str, target: Path, expected: str | None = None) -> None:
    if target.exists() and expected is None:
        return
    if target.exists() and expected and checksum(target) == expected:
        return
    if target.exists() and expected:
        target.unlink()
    partial = target.with_suffix(target.suffix + ".part")
    for attempt in range(4):
        offset = partial.stat().st_size if partial.exists() else 0
        request = urllib.request.Request(url, headers={"Range": f"bytes={offset}-"} if offset else {})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                append = bool(offset and response.status == 206)
                with partial.open("ab" if append else "wb") as stream:
                    chunks = 0
                    while data := response.read(8 * 1024 * 1024):
                        stream.write(data)
                        chunks += 1
                        if chunks % 8 == 0:
                            print(target.name, round(stream.tell() / 1024 ** 2), "MiB", flush=True)
            if expected and checksum(partial) != expected:
                partial.unlink()
                raise ValueError("Official file checksum mismatch")
            partial.replace(target)
            return
        except (OSError, ValueError):
            if attempt == 3:
                raise
            time.sleep(2)


def main() -> None:
    root = ROOT.resolve()
    if root != ROOT or root.is_symlink():
        raise ValueError("Unexpected service root")
    directory = root / "models/TimesFM-2.5-200M"
    directory.mkdir(parents=True, exist_ok=True)
    for filename in ("config.json", "README.md", "model.safetensors"):
        download(
            f"https://huggingface.co/google/timesfm-2.5-200m-pytorch/resolve/{REVISION}/{filename}",
            directory / filename, WEIGHT_SHA256 if filename == "model.safetensors" else None,
        )
    vendor = root / "vendor/TimesFM"
    marker = root / "TIMESFM_REVISION.txt"
    if not (marker.exists() and marker.read_text().strip() == SOURCE
            and (vendor / "LICENSE").exists() and (vendor / "src/timesfm/__init__.py").exists()):
        archive = root / f"timesfm-{SOURCE}.tar.gz"
        download(f"https://codeload.github.com/google-research/timesfm/tar.gz/{SOURCE}", archive)
        vendor.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive) as source:
            for item in source:
                relative = Path(*Path(item.name).parts[1:])
                if not relative.parts:
                    continue
                output = (vendor / relative).resolve()
                if not output.is_relative_to(vendor.resolve()):
                    raise ValueError("Unsafe upstream archive entry")
                if item.isdir():
                    output.mkdir(parents=True, exist_ok=True)
                elif item.isfile():
                    output.parent.mkdir(parents=True, exist_ok=True)
                    with source.extractfile(item) as stream:
                        output.write_bytes(stream.read())
        marker.write_text(SOURCE + "\n")
    manifest = {
        "repo": "google/timesfm-2.5-200m-pytorch", "revision": REVISION,
        "source_revision": SOURCE, "license": "Apache-2.0",
        "files": {filename: checksum(directory / filename) for filename in
                  ("config.json", "README.md", "model.safetensors")},
    }
    (directory / "revision.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("Verified official TimesFM 2.5 source and weights", flush=True)


if __name__ == "__main__":
    main()
