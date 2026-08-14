# mootdx (vendored, patched)

This directory is a **vendored copy of [`mootdx==0.11.7`](https://pypi.org/project/mootdx/)**
(MIT License, copyright bopo / mootdx contributors — see `LICENSE`), the latest
release on PyPI.

## Why it is vendored

`mootdx==0.11.7` declares `httpx>=0.25,<0.26` in its package metadata, but the
backend stack needs `httpx>=0.27` (fastapi/starlette `full` extra) and runs on
`httpx 0.28.1`. No `httpx` version satisfies both, so pip cannot resolve
`requirements.txt` containing both packages (`ResolutionImpossible`), and
`pip check` reports a conflict.

The runtime code is verified compatible with `httpx 0.28` (`import mootdx` and
`mootdx.quotes.Quotes` work normally), so the fix here is **metadata-only**:

- Version bumped to `0.11.7.post1` (local patched build).
- The only changed line in `pyproject.toml`:
  `httpx>=0.25,<0.26` → `httpx>=0.25,<0.29`.

## How to refresh

To update from upstream:

```bash
pip download mootdx==0.11.7 --no-deps --no-binary :all: -d /tmp/mootdx-src
# copy the extracted mootdx/ package over ./mootdx/, keep the patched
# pyproject.toml, bump the version, and re-verify:
pip check
pytest backend/tests
```

## Installation

Referenced from `backend/requirements.txt` as `./vendor/mootdx`:

```bash
cd backend
pip install -r requirements.txt   # resolves the vendored package from this dir
```
