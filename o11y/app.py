#!/usr/bin/env python3

import subprocess
import json
import time
from datetime import datetime, timezone
import os
import sys

# --- Configuração ---
OUTPUT_FILE = "../experiments/changing_frequency/docker_stats_log_streaming.jsonl"
# --------------------

DOCKER_CMD = [
    "docker", "stats",
    "--format", "{{json .}}"
]

print(f"Iniciando monitoramento de 'docker stats' (Modo Streaming)...")
print(f"Salvando dados em: {OUTPUT_FILE}")
print("Pressione Ctrl+C para parar a coleta.")

process = None
try:
    process = subprocess.Popen(
        DOCKER_CMD,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8',
        bufsize=1
    )

    with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
        for line in process.stdout:

            # --- INÍCIO DA CORREÇÃO v3 ---

            # 1. Tira espaços em branco *comuns* (não resolve o problema)
            line_stripped = line.strip()

            if not line_stripped:
                continue

            # 2. Encontra o PRIMEIRO '{'
            json_start_index = line_stripped.find('{')

            # 3. Encontra o ÚLTIMO '}'
            # Usamos rfind() para "find reverso"
            json_end_index = line_stripped.rfind('}')

            # 4. Validação
            # Se não achou um { ou }, ou se o } veio antes do {
            if json_start_index == -1 or json_end_index == -1 or json_end_index < json_start_index:
                # Linha inválida, pular
                continue

            # 5. Extrai a string JSON limpa
            # Do primeiro { até o último } (incluindo ele, por isso +1)
            json_string = line_stripped[json_start_index: json_end_index + 1]

            # --- FIM DA CORREÇÃO v3 ---

            snapshot_time_utc = datetime.now(timezone.utc).isoformat()

            try:
                # 6. Tente decodificar a string JSON agora BEM definida
                container_stat = json.loads(json_string)

                log_entry = {
                    "timestamp_utc": snapshot_time_utc,
                    "container": container_stat
                }

                f.write(json.dumps(log_entry) + '\n')

            except json.JSONDecodeError as e:
                print(f"[{snapshot_time_utc}] Erro ao decodificar JSON: {e} | Linha (fatiada): {json_string}",
                      file=sys.stderr)

    # O resto do script é idêntico...
    stderr_output = process.stderr.read()
    if stderr_output:
        print(f"\nErro reportado pelo 'docker stats':\n{stderr_output}", file=sys.stderr)

except KeyboardInterrupt:
    print("\nMonitoramento interrompido pelo usuário.")
    if process:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
    print(f"Dados salvos em {OUTPUT_FILE}")

except FileNotFoundError:
    print("Erro: Comando 'docker' não encontrado. Verifique sua instalação e PATH.", file=sys.stderr)

except Exception as e:
    print(f"Um erro inesperado ocorreu: {e}", file=sys.stderr)
    if process:
        process.kill()