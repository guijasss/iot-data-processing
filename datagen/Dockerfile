FROM python:3.11-slim

WORKDIR /app

# Copia requirements primeiro
COPY datagen/requirements.txt ./datagen/

# Instala dependências
RUN pip install --no-cache-dir -r ./datagen/requirements.txt

# Copia código de datagen e common
COPY datagen ./datagen
COPY common ./common

# Adiciona /app ao PYTHONPATH
ENV PYTHONPATH=/app

# CMD para rodar app
# CMD ["python", "datagen/app.py"]
