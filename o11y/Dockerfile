FROM python:3.11-slim

WORKDIR /app

COPY o11y/requirements.txt ./o11y/

RUN pip install --no-cache-dir -r ./o11y/requirements.txt
RUN apt update
RUN apt install sqlite3

COPY o11y ./o11y
COPY common ./common

ENV PYTHONPATH=/app
