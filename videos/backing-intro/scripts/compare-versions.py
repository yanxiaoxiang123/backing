"""Verify both deliveries have identical decoded video frames."""
import hashlib
import json
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
results = {}
for name in ("backing-intro", "backing-intro-nobgm"):
    process = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-i", str(root / "out" / f"{name}.mp4"),
         "-map", "0:v:0", "-f", "rawvideo", "-pix_fmt", "yuv420p", "-"],
        stdout=subprocess.PIPE,
    )
    digest = hashlib.sha256()
    while chunk := process.stdout.read(1024 * 1024):
        digest.update(chunk)
    if process.wait() != 0:
        raise RuntimeError(f"Video decode failed: {name}")
    results[name] = digest.hexdigest()
assert len(set(results.values())) == 1, "Visual timelines differ"
(root / "analysis" / "two-version-video-hashes.json").write_text(
    json.dumps({"identical": True, "decoded_yuv420p_sha256": results}, indent=2),
    encoding="utf-8",
)
print(json.dumps(results, indent=2))
