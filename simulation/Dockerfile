FROM python:3.11-slim

WORKDIR /app

COPY simulation/requirements.txt ./simulation/

RUN pip install --no-cache-dir -r ./simulation/requirements.txt

COPY simulation ./simulation

ENV PYTHONPATH=/app
