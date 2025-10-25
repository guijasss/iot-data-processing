import time
import docker
import json
import os
import sys
import glob
from typing import Generator

# --- CONFIGURAÇÕES ---
DATAGEN_CONTAINER_NAME = "datagen"
PROCESSOR_CONTAINER_NAME = "processor"

LOG_DIR_HOST = "./logs"  # Onde os volumes estão no HOST
ALERTS_LOG_FILE = os.path.join(LOG_DIR_HOST, "alerts_detected.jsonl")
EVENTS_LOG_PATTERN = os.path.join(LOG_DIR_HOST, "events_generated_*.jsonl")
CHECK_INTERVAL = 0.1


# --- (Funções 'follow', 'restart_container', 'clear_log_files'...) ---
# (Estas funções são as mesmas da nossa discussão anterior)

def follow(filepath: str) -> Generator[str, None, None]:
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        open(filepath, 'a').close()
        with open(filepath, 'r') as f:
            f.seek(0, os.SEEK_END)
            while True:
                line = f.readline()
                if not line:
                    time.sleep(CHECK_INTERVAL)
                    continue
                yield line.strip()
    except Exception as e:
        print(f"Orchestrator: Erro ao ler '{filepath}': {e}. Tentando novamente...")
        time.sleep(1)
        yield from follow(filepath)


def restart_container(client: docker.DockerClient, container_name: str):
    try:
        print(f"Orchestrator: Reiniciando '{container_name}'...")
        container = client.containers.get(container_name)
        container.restart()
        print(f"Orchestrator: '{container_name}' reiniciado.")
    except Exception as e:
        print(f"Orchestrator: Erro ao reiniciar '{container_name}': {e}")


def clear_log_files(alert_log_path: str, events_log_pattern: str):
    print("Orchestrator: Limpando logs do ciclo anterior...")
    # Limpa log de alertas
    try:
        with open(alert_log_path, 'w') as f:
            pass
    except Exception:
        pass
    # Limpa logs de eventos
    for f in glob.glob(events_log_pattern):
        try:
            os.remove(f)
        except Exception:
            pass


# --- Fim das funções auxiliares ---

def main():
    print("--- Orquestrador de Teste de Latência Iniciado ---")
    try:
        docker_client = docker.from_env()
        print("Orchestrator: Conectado ao Docker daemon.")
    except Exception as e:
        print(f"Orchestrator: Erro fatal ao conectar ao Docker: {e}")
        return

    test_cycle_count = 0
    while True:
        test_cycle_count += 1
        print("\n" + "=" * 50)
        print(f"--- INICIANDO CICLO DE TESTE N° {test_cycle_count} ---")

        clear_log_files(ALERTS_LOG_FILE, EVENTS_LOG_PATTERN)

        restart_container(docker_client, DATAGEN_CONTAINER_NAME)

        print(f"\nOrchestrator: Containers reiniciados. Monitorando '{ALERTS_LOG_FILE}'...")

        # 4. Ouve o log de alertas (T2)
        log_lines = follow(ALERTS_LOG_FILE)

        found_trigger = False
        for line in log_lines:
            try:
                alert = json.loads(line)

                # 5. GATILHO: O primeiro alerta 'overheating'
                if alert.get("alert_type") == "overheating":
                    print("\n--- GATILHO 'overheating' DETECTADO! ---")
                    print(f"Orchestrator: Log de alerta recebido: {line}")
                    found_trigger = True
                    break  # Encerra o 'for' e finaliza este ciclo

            except Exception as e:
                print(f"Orchestrator: Erro no loop de monitoramento: {e}")

        if not found_trigger:
            print("Orchestrator: 'Follow' interrompido. Reiniciando ciclo.")

        print("Orchestrator: Ciclo de teste concluído. Aguardando 5s...")
        time.sleep(5)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOrquestrador encerrado pelo usuário.")
        sys.exit(0)
