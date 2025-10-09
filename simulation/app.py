import time
import docker
import psycopg2
from psycopg2 import OperationalError

# --- CONFIGURAÇÕES ---
DB_PARAMS = {
    'dbname': 'metrics',
    'user': 'user_tcc',
    'password': 'password_tcc',
    'host': 'metrics_db',
    'port': 5432
}

# Nomes dos contêineres que este script irá controlar
DATAGEN_CONTAINER_NAME = "datagen"
POLLING_INTERVAL_SECONDS = 5  # Intervalo para verificar o banco

def get_alerts_count() -> int:
    """Consulta o banco de dados e retorna o número de alertas."""
    conn = None
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cursor = conn.cursor()
        # Ajuste a query conforme sua necessidade
        cursor.execute("SELECT COUNT(1) FROM alerts WHERE type = 'overheating';")
        result = cursor.fetchone()
        return result[0] if result else 0
    except OperationalError as e:
        print(f"Aviso: Não foi possível conectar ao DB para checar alertas: {e}")
        return -1  # Sinaliza um erro de conexão
    finally:
        if conn:
            conn.close()


def main():
    """Script principal do orquestrador."""
    print("--- Orquestrador de Simulação Iniciado ---")

    try:
        docker_client = docker.from_env()
        print("Conectado ao Docker daemon.")
    except Exception as e:
        print(f"Erro: Não foi possível conectar ao Docker daemon. Verifique se o Docker está rodando. {e}")
        return

    # Espera inicial para o banco de dados iniciar
    print("Aguardando o banco de dados ficar disponível...")
    time.sleep(10)

    baseline_alerts_count = get_alerts_count()
    if baseline_alerts_count == -1:
        print("Não foi possível obter a contagem inicial de alertas. Verifique a conexão com o DB.")
        # Pode ser normal se o DB ainda não estiver pronto, então vamos tentar de novo.
        baseline_alerts_count = 0

    print(f"Contagem de alertas inicial: {baseline_alerts_count}. Monitorando por mudanças...")

    while True:
        current_alerts_count = get_alerts_count()

        if current_alerts_count > baseline_alerts_count:
            print("\n--- DETECTADO NOVO ALERTA! ---")
            print(f"Contagem de alertas mudou de {baseline_alerts_count} para {current_alerts_count}.")

            try:
                print(f"Reiniciando o contêiner '{DATAGEN_CONTAINER_NAME}' para resetar o estado...")
                datagen_container = docker_client.containers.get(DATAGEN_CONTAINER_NAME)
                datagen_container.restart()
                print(f"Contêiner '{DATAGEN_CONTAINER_NAME}' reiniciado com sucesso.")

                # Atualiza a linha de base para a nova contagem
                baseline_alerts_count = current_alerts_count

            except docker.errors.NotFound:
                print(f"Erro: Contêiner '{DATAGEN_CONTAINER_NAME}' não encontrado.")
            except Exception as e:
                print(f"Erro ao tentar reiniciar o contêiner: {e}")

            print("---------------------------------\n")

        time.sleep(POLLING_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
