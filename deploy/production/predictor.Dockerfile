ARG PYTHON_IMAGE=python:3.12-slim-bookworm
FROM ${PYTHON_IMAGE} AS runtime-base
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
RUN sed -i 's|http://deb.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::Retries=2 -o Acquire::https::Timeout=30 update \
    && apt-get -o Acquire::Retries=2 -o Acquire::https::Timeout=30 install -y --no-install-recommends ca-certificates libgomp1 tzdata \
    && rm -rf /var/lib/apt/lists/*
FROM runtime-base AS dependencies
COPY deploy/kronos/requirements.lock /tmp/requirements.lock
COPY production-wheels/predictor /wheels
RUN python -m pip install --no-cache-dir --no-index --find-links /wheels --prefix /install -r /tmp/requirements.lock

FROM runtime-base
COPY --from=dependencies /install /usr/local
WORKDIR /service
COPY deploy/kronos/service.py deploy/kronos/timesfm_adapter.py /service/
EXPOSE 8211
CMD ["python", "-m", "uvicorn", "service:app", "--host", "0.0.0.0", "--port", "8211", "--workers", "1", "--no-access-log"]
