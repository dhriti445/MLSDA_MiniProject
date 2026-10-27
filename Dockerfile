FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app PYTHONUNBUFFERED=1

RUN useradd -m app \
    && mkdir -p /data \
    && chown -R app:app /app /data

USER app