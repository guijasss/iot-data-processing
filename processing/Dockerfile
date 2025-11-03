FROM python:3.11-slim

WORKDIR /app

# Copia requirements primeiro
COPY processing/requirements.txt ./processing/

# Instala dependências
RUN pip install --no-cache-dir -r ./processing/requirements.txt

# Copia código de processing e common
COPY processing ./processing
COPY common ./common

# Adiciona /app ao PYTHONPATH
ENV PYTHONPATH=/app

# CMD para rodar app
# CMD ["python", "processing/app.py"]
