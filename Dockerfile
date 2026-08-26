FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-ml.txt ./
ARG INSTALL_ML=true
RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && if [ "$INSTALL_ML" = "true" ]; then pip install -r requirements-ml.txt; fi

COPY application application
COPY config config
COPY domain domain
COPY infrastructure infrastructure
COPY presentation presentation
COPY rules rules
COPY scripts scripts
COPY training training

RUN mkdir -p runtime/exports models rag_store data

EXPOSE 8000
CMD ["uvicorn", "presentation.main:app", "--host", "0.0.0.0", "--port", "8000"]
