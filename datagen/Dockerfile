FROM python:3.11-slim

WORKDIR /app

COPY datagen/requirements.txt ./datagen/

RUN pip install --no-cache-dir -r ./datagen/requirements.txt

COPY datagen ./datagen
COPY common ./common

ENV PYTHONPATH=/app
