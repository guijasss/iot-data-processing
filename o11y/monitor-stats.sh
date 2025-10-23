#!/bin/bash

# --- Configurações ---
DB_NAME="metrics"
DB_USER="user_tcc"
DB_PASSWORD="password_tcc"
DB_HOST="localhost" # Ou o nome do serviço se rodar em outro container
DB_PORT="5432"
INTERVAL=1 # Segundos entre coletas - Reduzido para 1s conforme seu log
TARGET_CONTAINERS=("processing" "mqtt-broker" "datagen") # Verifique esses nomes!

# --- Verifica se jq está instalado ---
if ! command -v jq &> /dev/null
then
    echo "Erro: O comando 'jq' não foi encontrado. Instale-o (ex: sudo apt-get install jq)."
    exit 1
fi

echo "Iniciando monitoramento de stats do Docker (a cada ${INTERVAL}s)... Pressione Ctrl+C para sair."

while true; do
    batch_timestamp=$(date -u +"%Y-%m-%d %H:%M:%S.%N%:z")

    echo "DEBUG: Executando docker stats..." # <-- DEBUG 1

    # Captura a saída do docker stats + jq para uma variável para depuração
    json_output=$(docker stats --no-stream --format '{{json .}}' | \
                  jq -c '. | select(.Name | IN('\"$(printf "%s" "${TARGET_CONTAINERS[@]}" | paste -sd '","')\"'))')

    # Verifica se a variável json_output está vazia
    if [ -z "$json_output" ]; then
        echo "DEBUG: Nenhum JSON retornado pelo docker stats | jq. Verifique os nomes dos contêineres ou se estão rodando." # <-- DEBUG 2
    else
        echo "DEBUG: JSON retornado:" # <-- DEBUG 3
        echo "$json_output"
    fi

    # Processa cada linha JSON filtrada (se houver alguma)
    echo "$json_output" | while IFS= read -r line; do
        echo "DEBUG: Processando linha JSON: $line" # <-- DEBUG 4: Este print confirma que o loop interno começou

        # Extrai os dados com jq
        container_name=$(echo "$line" | jq -r '.Name')
        # ... (resto do seu código de extração e inserção) ...
        cpu_percent_str=$(echo "$line" | jq -r '.CPUPerc')
        mem_usage_str=$(echo "$line" | jq -r '.MemUsage') # Ex: "65.8MiB / 250MiB"
        mem_limit_str=$(echo "$line" | jq -r '.MemUsage') # Para extrair o limite

        # Limpa e calcula os valores numéricos
        cpu_percent=$(echo "$cpu_percent_str" | sed 's/%//')
        mem_usage=$(echo "$mem_usage_str" | sed -n 's/^\([0-9.]*\)MiB.*/\1/p')
        mem_limit=$(echo "$mem_limit_str" | sed -n 's/.* \/ \([0-9.]*\)MiB$/\1/p')

        # Calcula mem_percent (evita divisão por zero)
        if [[ -n "$mem_limit" && $(echo "$mem_limit > 0" | bc -l) -eq 1 ]]; then
            mem_percent=$(echo "scale=2; ($mem_usage / $mem_limit) * 100" | bc -l)
        else
            mem_percent=0.0
            # Adiciona um valor padrão ou log se o limite for zero ou não encontrado
             if [ -z "$mem_limit" ]; then
                 echo "DEBUG: Limite de memória não encontrado para $container_name. Usando 0."
                 mem_limit=0
             fi
        fi

        # ... (Simplificando I/O por enquanto) ...
        rx_mb=0.0
        tx_mb=0.0
        io_read_mb=0.0
        io_write_mb=0.0
        restarts=0

        SQL_COMMAND="INSERT INTO metrics (timestamp, container, cpu_percent, mem_usage, mem_limit, mem_percent, rx_bytes, tx_bytes, io_read, io_write, restarts) VALUES ('$batch_timestamp', '$container_name', $cpu_percent, $mem_usage, $mem_limit, $mem_percent, $rx_mb, $tx_mb, $io_read_mb, $io_write_mb, $restarts);"

        echo "DEBUG: Executando SQL: $SQL_COMMAND" # <-- DEBUG 5

        PGPASSWORD=$DB_PASSWORD psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "$SQL_COMMAND" > /dev/null 2>&1
        if [ $? -ne 0 ]; then
             echo "Erro ao inserir dados para $container_name no banco."
        fi
    done

    # Espera o intervalo definido
    sleep "$INTERVAL"
done