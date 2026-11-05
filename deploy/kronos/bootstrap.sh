#!/usr/bin/env bash
set -euo pipefail
target=/home/yanxx/kronos-service
source_root=/home/yanxx/newsstock/kronos_vlm_research
revision=67b630e67f6a18c9e9be918d9b4337c960db1e9a
test ! -L "$target"
mkdir -p "$target/models" "$target/vendor/Kronos"
for model in Kronos-small Kronos-base Kronos-Tokenizer-base; do
    mkdir -p "$target/models/$model"
    for file in config.json model.safetensors revision.json; do
        if ! cmp -s "$source_root/models/$model/$file" "$target/models/$model/$file"; then
            cp --reflink=auto "$source_root/models/$model/$file" "$target/models/$model/$file"
        fi
    done
done
git -C "$source_root/vendor/Kronos" archive "$revision" | tar -x -C "$target/vendor/Kronos"
printf '%s\n' "$revision" > "$target/UPSTREAM_REVISION.txt"
if ! test -x "$target/.venv/bin/python"; then
    if test -d "$target/.venv/lib/python3.10/site-packages"; then
        # Resume an interrupted clone without copying its large CUDA wheels again.
        /opt/miniconda3/bin/conda list --prefix /opt/miniconda3/envs/newsstock --explicit > "$target/conda-explicit.txt"
        /opt/miniconda3/bin/conda create --prefix "$target/.venv" --file "$target/conda-explicit.txt" -y
    else
        /opt/miniconda3/bin/conda create --prefix "$target/.venv" --clone /opt/miniconda3/envs/newsstock -y
    fi
fi
/opt/miniconda3/bin/uv pip install --python "$target/.venv/bin/python" -r "$target/requirements.txt"
"$target/.venv/bin/python" "$target/lock_runtime.py"
chown -R yanxx:yanxx "$target"
