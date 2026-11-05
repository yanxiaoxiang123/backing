"""Freeze the installed runtime dependency closure, excluding research extras."""

from importlib.metadata import distribution
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


def freeze(root: Path) -> None:
    pending = [
        Requirement(line).name for line in (root / "requirements.txt").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    pinned = {}
    while pending:
        name = canonicalize_name(pending.pop())
        if name in pinned:
            continue
        package = distribution(name)
        pinned[name] = package.version
        for value in package.requires or []:
            requirement = Requirement(value)
            if requirement.marker is None or requirement.marker.evaluate({"extra": ""}):
                pending.append(requirement.name)
    (root / "requirements.lock").write_text(
        "# Installed Linux/CUDA runtime dependency closure; Python 3.10.\n"
        + "".join(f"{name}=={version}\n" for name, version in sorted(pinned.items())),
    )


if __name__ == "__main__":
    freeze(Path(__file__).resolve().parent)
