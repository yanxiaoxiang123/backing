# OCR workspace review — 2026-11-15

Five confirmed High/Medium issues were fixed in the workspace: one High security issue and four Medium correctness issues. No confirmed High/Medium issue remains unresolved within the reviewed scope. Existing unrelated workspace changes were preserved; nothing was committed, pushed, deployed, or restored into a running deployment.

## Scope and coverage

- Review mode: `workspace` — staged, unstaged, and untracked changes relative to HEAD.
- Branch: `feat/agent-workspace-improvements`.
- Base commit: `043e9747341337235d34eddcf5bd0dbdbc2c2667`.
- Rules: OCR checklists were obtained for all 80 selected files before review.
- Review covered the changed lines of tracked files and the source of selected untracked files. Findings below concern changed or added code.

The [per-file coverage ledger](2026-11-15-ocr-workspace-coverage.json) records every original previewed `(path, git_status)` as `reviewed` or `skipped`, with a reason. Its denominator is fixed to the initial preview so that adding regression tests and this report does not change the audit scope.

| Metric | All original preview entries | OCR-selected review scope |
| --- | ---: | ---: |
| `total_files` | 533 | 80 |
| `reviewed_files` | 80 | 80 |
| `skipped_files` | 453 | 0 |
| `coverage_rate` | 15.01% | 100% |

OCR excluded 398 binary entries, 36 entries with unsupported extensions, and 19 entries matching default path exclusions. These exclusions are recorded individually; they are not claimed as source or binary audits. Selected files comprise 21 frontend files, 12 backend/deployment files, 40 video-project files, and seven downloaded Chromium text/configuration files.

The Nginx companion configuration and relevant regression tests were also inspected and verified for the fixes. Their focused use does not turn OCR-excluded files into completed full-file reviews in the original ledger. Two new test files were added after the initial preview: `frontend/src/components/research/ResearchCopilot.test.tsx` and `videos/backing-intro/tests/test_media_scripts.py`. A refreshed preview before report creation contained 535 entries, with the same 80 OCR-selected files.

## Confirmed findings and fixes

### F1 — High — Forged forwarding headers could bypass login rate limits — fixed

Selected source: [deploy/production/serve.py:12](../../deploy/production/serve.py:12). Fix: [deploy/production/nginx.conf:30](../../deploy/production/nginx.conf:30).

The production entry point trusts forwarded client addresses. The public Nginx edge previously appended a client-supplied `X-Forwarded-For` header with `$proxy_add_x_forwarded_for`. With Uvicorn configured to trust all forwarding peers, the supplied first address became the request's client identity. A client could rotate that header to obtain a new login limiter bucket without changing their actual connection address.

The public edge now overwrites `X-Forwarded-For` with `$remote_addr`. This deployment has Nginx as its public entry point; the fix removes incoming forwarding claims at that boundary.

Regression evidence: [test_production_serve.py:53](../../backend/tests/test_production_serve.py:53) executes the actual entry script with server startup intercepted, reads the Nginx directive, and passes three forged header variants through the real Uvicorn proxy middleware and SlowAPI address function. Before the fix, the limiter saw three forged identities. After the fix, all three requests use the real connection address and retain HTTPS scheme.

### F2 — Medium — Live research-cache backups could be inconsistent and still verify — fixed

Source and fix: [deploy/production/operations.py:36](../../deploy/production/operations.py:36), [cache archive handling:53](../../deploy/production/operations.py:53), and [restore verification:108](../../deploy/production/operations.py:108).

The application database already used SQLite's online backup API, but the research evidence cache was copied with the rest of `backend-data`. A live WAL checkpoint between independent copies of `research_cache.db`, its WAL, and its SHM file could leave incompatible file generations in the archive. Restore verification checked the application database and file checksums, but did not check the research cache's SQLite integrity. A damaged cache with correct archive checksums was accepted as verified.

Both databases now use the SQLite backup API. The evidence-cache snapshot uses DELETE journal mode and is archived without live WAL/SHM sidecars. Its table counts are recorded in the manifest. Verification checks cache integrity and foreign keys, and compares table counts when the optional cache manifest field is present. Cache files in older archives are also integrity-checked.

Regression evidence:

- [Live-cache snapshot test:60](../../backend/tests/test_production_backup.py:60) uses a real WAL-mode SQLite cache with 200 records and simulates a checkpoint between ordinary file copies. The archive must contain a standalone valid snapshot with no cache WAL/SHM files.
- [Corrupt-cache test:103](../../backend/tests/test_production_backup.py:103) builds a correctly checksummed archive containing a damaged cache and requires verification to reject it.

Both tests failed before the fix and passed afterward. No production backup or restore application was run.

### F3 — Medium — Copilot handoff during restoration dropped the conversation — fixed

Source and fix: [ResearchCopilot.tsx:32](../../frontend/src/components/research/ResearchCopilot.tsx:32), [workspace handoff:79](../../frontend/src/components/research/ResearchCopilot.tsx:79).

When the URL requested an existing thread but its details were still loading, the input correctly scoped its draft to the URL's `thread_id`. The button for opening the full workspace used only the loaded thread object. Clicking during restoration navigated without the thread identifier, separating the destination from the intended conversation and its draft.

The Copilot now computes one shared thread identity, falling back to the URL while the thread object is unavailable. The draft input and workspace link both use it.

Regression evidence: [ResearchCopilot.test.tsx](../../frontend/src/components/research/ResearchCopilot.test.tsx) uses the real component, chat hook, router, and draft storage while keeping the external thread-detail request pending. Before the fix, the destination was `/workspace?stock=sh.600000`; afterward it is `/workspace?thread_id=bank&stock=sh.600000`. The draft remains stored under the requested thread, and sending stays disabled during restoration.

### F4 — Medium — Repeating media finalization overwrote pristine render backups — fixed

Source and fix: [finalize.py:4](../../videos/backing-intro/scripts/finalize.py:4).

The finalization script moved each delivery onto its `*-render.mp4` backup path after encoding. A second run replaced an existing pristine backup with the already-finalized delivery and re-encoded AAC audio again. A backup conflict in the second variant could also occur after the first variant had already been processed.

The script now checks both backup destinations before any subprocess or mutation. If either exists, it raises `FileExistsError` and preserves the existing files.

Regression evidence: [test_media_scripts.py](../../videos/backing-intro/tests/test_media_scripts.py) parameterizes the conflict across both variants and checks exact file bytes and the absence of encoding work. Both cases failed before the fix and pass afterward. Tests use temporary media placeholders; existing renders were not touched.

### F5 — Medium — First-run QA extraction failed without its output directory — fixed

Source and fix: [extract-qa.py:4](../../videos/backing-intro/scripts/extract-qa.py:4).

The extraction script wrote frames into `out/qa` before ensuring the directory existed. On a fresh output tree, the first extraction failed instead of producing the contact sheet.

The script now creates the QA directory before extracting frames.

Regression evidence: [test_media_scripts.py](../../videos/backing-intro/tests/test_media_scripts.py) starts without a QA directory, uses a narrow FFmpeg substitute to write actual Pillow images, and runs the real script. It verifies 20 extracted frames and a 1920×1950 contact sheet. The test failed before directory creation was added and passes afterward.

## Verification

All five fixes were preceded by regression failures reproducing their respective defects. Final verification results:

| Check | Result |
| --- | --- |
| Full backend suite, `backing` environment, `python -m pytest -q` from `backend/` | 829 passed, 1 skipped; exit 0 |
| Focused production/auth/runtime/settings tests | 42 passed; exit 0 |
| Full frontend suite, `npm --prefix frontend test` | 48 test files, 278 tests passed; exit 0 |
| Frontend typecheck | Passed |
| Frontend ESLint | Passed |
| Frontend production build, including independent bundle budgets | Passed; exit 0 |
| Prettier check on the changed Copilot component and its new test | Passed |
| Ruff on `operations.py` and the two deployment regression test files | Passed |
| Media utility regression tests, base Python with Pillow | 3 passed; exit 0 |
| `bash -n` on the three OCR-selected production shell scripts | Passed |
| `git --no-pager diff --no-ext-diff --no-textconv --no-color --check` | Passed |

Non-failing output included dependency deprecation warnings, React Router future-flag warnings, Git LF/CRLF notices, and Vite's generic large-chunk warning. The project's independent compressed bundle budgets all passed. The backend suite contained one skipped test; there were no failing backend tests.

## Verification limits

- Nginx and Compose were reviewed as configuration. The proxy regression exercises real Uvicorn and limiter behavior but does not start Nginx or containers.
- No Playwright or interactive browser session was run for this review.
- Media tests isolate the filesystem behavior. They do not run FFmpeg encodes, browser captures, Remotion renders, or a visual/audio acceptance pass.
- The downloaded Chromium text/configuration entries were reviewed as source/data. Downloaded executables and OCR-excluded binary assets were not executed or audited.
- No live model inference, market-provider request, deployment, or restore application was performed. The separate TradingAgents package was not changed or retested.

The fixes, regression tests, this report, and the per-file ledger remain uncommitted in the existing workspace.
