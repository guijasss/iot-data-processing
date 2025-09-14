FROM python:3.11-slim

WORKDIR /app

RUN mkdir "processing"

# Copia requirements.txt primeiro (boa prática para cache de layers)
COPY requirements.txt ./processing

# Instala dependências do requirements.txt
RUN pip install --no-cache-dir -r ./processing/requirements.txt

# Copia o resto do código
COPY . ./processing

# Adiciona /app ao PYTHONPATH para resolver imports locais
ENV PYTHONPATH=/app

# CMD para rodar o app principal
# CMD ["python", "app.py"]
