"""Download only repository-pinned model artifacts for offline transfer."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import sys
import tarfile

KRONOS = Path(__file__).resolve().parents[1] / "kronos"
sys.path.insert(0, str(KRONOS))
from provision_timesfm import download  # noqa: E402


def extract_source(url: str, archive: Path, destination: Path) -> None:
    download(url, archive)
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as source:
        for item in source:
            relative = Path(*Path(item.name).parts[1:])
            if not relative.parts:
                continue
            target = (destination / relative).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise ValueError("Unsafe source archive")
            if item.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif item.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.extractfile(item) as stream:
                    target.write_bytes(stream.read())


def main() -> None:
    root = Path(os.environ["KRONOS_ROOT"]).resolve()
    root.mkdir(parents=True, exist_ok=True)
    versions = json.loads((KRONOS / "versions.json").read_text())

    def model(entry):
        name, spec = entry
        directory = root / "models" / name
        directory.mkdir(parents=True, exist_ok=True)
        for filename, expected in spec["files"].items():
            download(f"https://huggingface.co/{spec['repo']}/resolve/{spec['revision']}/{filename}",
                     directory / filename, expected)
        manifest = {key: value for key, value in spec.items() if key != "transport"}
        (directory / "revision.json").write_text(json.dumps(manifest, indent=2) + "\n")
        print("Verified", name, flush=True)

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(model, versions["weights"].items()))
    for name, repo, revision, marker in [
        ("Kronos", "shiyu-coder/Kronos", versions["source_revision"], "UPSTREAM_REVISION.txt"),
        ("TimesFM", "google-research/timesfm", versions["timesfm_source_revision"], "TIMESFM_REVISION.txt"),
    ]:
        extract_source(f"https://codeload.github.com/{repo}/tar.gz/{revision}",
                       root / f"{name}-{revision}.tar.gz", root / "vendor" / name)
        (root / marker).write_text(revision + "\n")
        print("Verified source revision", name, revision, flush=True)
    manifest = {}
    for path in (root / "models").rglob("*"):
        if path.is_file():
            result = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                    result.update(block)
            manifest[path.relative_to(root).as_posix()] = result.hexdigest()
    (root / "TRANSFER_SHA256.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
