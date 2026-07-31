FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
ARG PYTORCH_INDEX_URL=https://download.pytorch.org/whl/cu124
RUN pip install --no-cache-dir torch==2.6.0 --index-url "${PYTORCH_INDEX_URL}" \
    && pip install --no-cache-dir ".[huggingface]"

RUN addgroup --system ai && adduser --system --ingroup ai ai
USER ai

EXPOSE 8100

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]
