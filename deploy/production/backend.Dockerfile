ARG PYTHON_IMAGE=python:3.12-slim-bookworm
FROM ${PYTHON_IMAGE} AS runtime-base
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
RUN sed -i 's|http://deb.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::Retries=2 -o Acquire::https::Timeout=30 update \
    && apt-get -o Acquire::Retries=2 -o Acquire::https::Timeout=30 install -y --no-install-recommends ca-certificates libgomp1 tzdata \
    && rm -rf /var/lib/apt/lists/*
FROM runtime-base AS dependencies
COPY backend/requirements.lock /tmp/requirements.lock
COPY production-wheels/backend /wheels
RUN python -c "from pathlib import Path; p=Path('/tmp/requirements.lock'); p.write_text('\n'.join('mootdx==0.11.7.post1' if l.startswith('mootdx @ ') else l for l in p.read_text().splitlines())+'\n')" \
    && python -m pip install --no-cache-dir --no-index --find-links /wheels --prefix /install -r /tmp/requirements.lock

FROM runtime-base
COPY --from=dependencies /install /usr/local
WORKDIR /app/backend
COPY TradingAgents-astock /app/TradingAgents-astock
RUN python -m pip install --no-cache-dir --no-index --no-build-isolation --no-deps -e /app/TradingAgents-astock
COPY backend /app/backend
COPY deploy/production/serve.py /app/serve.py
RUN chmod -R a+rX /app
EXPOSE 8808
CMD ["python", "/app/serve.py"]
