import json
from pathlib import Path
import runpy
import subprocess

from PIL import Image
import pytest


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


@pytest.mark.parametrize("backup_name", ["backing-intro", "backing-intro-nobgm"])
def test_finalize_preserves_existing_render_backup_before_any_work(
    tmp_path, monkeypatch, backup_name
):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "videos/backing-intro"
    output = root / "out"
    output.mkdir(parents=True)
    analysis = root / "analysis"
    analysis.mkdir()
    (analysis / "beat_data.json").write_text(json.dumps({"beats": [0]}))
    for name in ["backing-intro", "backing-intro-nobgm"]:
        (output / f"{name}.mp4").write_bytes(f"delivery-{name}".encode())
    backup = output / f"{backup_name}-render.mp4"
    backup.write_bytes(b"pristine-render")
    originals = {path: path.read_bytes() for path in output.iterdir()}
    calls = []

    def encode(args, **kwargs):
        calls.append(args)
        Path(args[-1]).write_bytes(b"re-encoded")

    monkeypatch.setattr(subprocess, "run", encode)
    monkeypatch.setattr(
        subprocess,
        "check_output",
        lambda args: json.dumps({"format": {"size": "10"}}).encode(),
    )

    with pytest.raises(FileExistsError):
        runpy.run_path(str(SCRIPTS / "finalize.py"), run_name="__main__")

    assert calls == []
    assert {path: path.read_bytes() for path in output.iterdir()} == originals


def test_extract_qa_creates_output_directory_on_first_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "videos/backing-intro/out"
    output.mkdir(parents=True)
    (output / "backing-intro.mp4").write_bytes(b"test-video")

    def extract(args, **kwargs):
        Image.new("RGB", (64, 36), "white").save(args[-1])

    monkeypatch.setattr(subprocess, "run", extract)
    runpy.run_path(str(SCRIPTS / "extract-qa.py"), run_name="__main__")

    assert len(list((output / "qa").glob("final-f*.png"))) == 20
    with Image.open(output / "qa/contact-final.jpg") as contact:
        assert contact.size == (1920, 1950)
