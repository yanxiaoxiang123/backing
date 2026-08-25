#!/usr/bin/env bash
set -euo pipefail

# Fetch the exact upstream revision used by the quant plugin without checking
# the multi-gigabyte dependency into this repository.
REPO_URL="${DSH_REPO_URL:-https://github.com/deepseek-ai/deepseek-harness.git}"
PINNED_COMMIT="${DSH_COMMIT:-47f943859bef60e4160492346772ded9b24f765a}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
TARGET="${REPO_ROOT}/deepseek-harness"

if [[ -d "${TARGET}/.git" ]]; then
  git -C "${TARGET}" fetch --quiet --depth 1 origin "${PINNED_COMMIT}"
else
  git clone --filter=blob:none --no-checkout "${REPO_URL}" "${TARGET}"
  git -C "${TARGET}" fetch --quiet --depth 1 origin "${PINNED_COMMIT}"
fi

git -C "${TARGET}" checkout --quiet --detach "${PINNED_COMMIT}"
actual="$(git -C "${TARGET}" rev-parse HEAD)"
if [[ "${actual}" != "${PINNED_COMMIT}" ]]; then
  echo "Pinned DeepSeek Harness checkout failed: ${actual}" >&2
  exit 1
fi
echo "DeepSeek Harness ready at ${TARGET} (${actual})"
