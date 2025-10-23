import docker
import threading
import sys
import time
from datetime import datetime
from common.infra import PostgreSQLHandler  # (Importa sua classe do Postgres)

# Lista de contêineres que queremos monitorar
TARGET_CONTAINERS = ['processing', 'mqtt-broker', 'datagen']

DEFAULT_PRECISION = 2


def parse_stats(stats_dict, container_name):
    """
    Função auxiliar para extrair e calcular as métricas do JSON de estatísticas.
    Esta lógica é a mesma do seu script anterior.
    """
    try:
        # Pega o 'precpu_stats'. Pode estar vazio na primeira leitura, por isso o .get()
        precpu_stats = stats_dict.get("precpu_stats", {})

        # CPU %
        # (Tratamento de erro para a primeira leitura, onde precpu_stats pode não ter as chaves)
        cpu_usage = stats_dict["cpu_stats"].get("cpu_usage", {})
        precpu_usage = precpu_stats.get("cpu_usage", {})

        cpu_delta = cpu_usage.get("total_usage", 0) - precpu_usage.get("total_usage", 0)
        system_delta = stats_dict["cpu_stats"].get("system_cpu_usage", 0) - precpu_stats.get("system_cpu_usage", 0)

        percpu = cpu_usage.get("percpu_usage", [])
        num_cpus = len(percpu) if percpu else 1

        cpu_percent = round((cpu_delta / system_delta) * num_cpus * 100.0,
                            DEFAULT_PRECISION) if system_delta > 0 and cpu_delta > 0 else 0.0

        # Memória
        mem_stats = stats_dict.get("memory_stats", {})
        mem_used = round(mem_stats.get("usage", 0) / (1024 * 1024), DEFAULT_PRECISION)
        mem_limit = round(mem_stats.get("limit", 0) / (1024 * 1024), DEFAULT_PRECISION)
        mem_percent = round((mem_used / mem_limit * 100), DEFAULT_PRECISION) if mem_limit > 0 else 0.0

        # Rede
        networks = stats_dict.get("networks", {})
        rx = round(sum(n["rx_bytes"] for n in networks.values()) / (1024 * 1024), DEFAULT_PRECISION)
        tx = round(sum(n["tx_bytes"] for n in networks.values()) / (1024 * 1024), DEFAULT_PRECISION)

        # I/O (simplificado para evitar erros se blkio não existir)
        blkio = stats_dict.get("blkio_stats", {}).get("io_service_bytes_recursive") or []
        io_read = sum(x["value"] for x in blkio if x.get("op") == "Read") / (1024 * 1024)
        io_write = sum(x["value"] for x in blkio if x.get("op") == "Write") / (1024 * 1024)

        # Reinícios (Não disponível no stream de stats, temos que pegar do atributo do contêiner)
        # restarts = container_obj.attrs.get("RestartCount", 0) # Deixado de fora por simplicidade

        # Retorna o dicionário pronto para o banco
        return {
            "timestamp": datetime.now(),  # Você pode usar datetime.now() ou stats_dict.get("read")
            "container": container_name,
            "cpu_percent": cpu_percent,
            "mem_usage": mem_used,
            "mem_limit": mem_limit,
            "mem_percent": mem_percent,
            "rx_bytes": rx,
            "tx_bytes": tx,
            "io_read": io_read,
            "io_write": io_write,
            "restarts": 0  # (Definido como 0, pois a API de stream não fornece isso)
        }

    except (KeyError, TypeError) as e:
        # É normal falhar na primeira leitura (onde precpu_stats está vazio)
        print(f"[Thread-{container_name}] Aviso: Erro de parsing (normal na primeira leitura): {e}")
        return None


def stream_container_stats(container):
    """
    Função alvo para cada thread.
    Cria um "listener" para um contêiner e escreve no banco.
    """
    print(type(container))
    container_name = container.name

    # IMPORTANTE: Conexões de banco (psycopg2) NÃO são thread-safe.
    # Cada thread DEVE criar sua própria instância do handler.
    db_handler = PostgreSQLHandler(containerized=False)

    print(f"[Thread-{container_name}] Iniciando listener e conexão com o banco...")

    try:
        print(f"[Thread-{container_name}] Iniciando loop do stream...")  # DEBUG
        for i, stats in enumerate(container.stats(stream=True, decode=True)):
            print(f"[Thread-{container_name}] Recebido stats #{i + 1}")  # DEBUG: O loop está rodando?

            metrics = parse_stats(stats, container_name)
            print(f"[Thread-{container_name}] Resultado do parse_stats: {metrics}")  # DEBUG: O parsing funcionou?

            if metrics:
                try:
                    print(f"[Thread-{container_name}] Tentando inserir no DB...")  # DEBUG
                    db_handler.insert_one("metrics", metrics)
                    print(f"[Thread-{container_name}] Inserção (aparentemente) bem-sucedida.")  # DEBUG
                except Exception as e:
                    print(f"[Thread-{container_name}] ERRO AO INSERIR NO DB: {e}")  # DEBUG: Falha na inserção?

        # Se chegar aqui, o stream terminou inesperadamente
        print(f"[Thread-{container_name}] AVISO: Loop 'for stats in ...' terminou.")

    except Exception as e:
        print(f"[Thread-{container_name}] Erro fatal no stream: {e}")
    finally:
        # Garante que a conexão do banco seja fechada quando a thread morrer
        db_handler.close_connection()
        print(f"[Thread-{container_name}] Listener encerrado.")


def main():
    try:
        client = docker.from_env()
    except Exception as e:
        print(f"Erro: Não foi possível conectar ao Docker daemon. {e}")
        print("Verifique se o Docker está rodando e se você tem permissão.")
        sys.exit(1)

    threads = []

    print("Iniciando 'listener' de stats do Docker...")

    try:
        # Itera sobre todos os contêineres rodando
        for container in client.containers.list():
            if container.name in TARGET_CONTAINERS:
                print(f"Iniciando thread para o contêiner: {container.name}")
                # daemon=True: Faz a thread fechar quando o script principal fechar
                t = threading.Thread(
                    target=stream_container_stats,
                    args=(container,),
                    daemon=True
                )
                threads.append(t)
                t.start()
            else:
                print(f"Ignorando contêiner: {container.name}")

        # Se não encontramos nenhum contêiner alvo
        if not threads:
            print(f"Nenhum dos contêineres alvo foi encontrado: {TARGET_CONTAINERS}")
            sys.exit(1)

        print("\nListeners iniciados. Pressione Ctrl+C para sair.")

        # Mantém o script principal vivo para as threads poderem rodar
        while True:
            time.sleep(60)

    except KeyboardInterrupt:
        print("\nSaindo... Os listeners serão encerrados.")
        sys.exit(0)


if __name__ == "__main__":
    main()