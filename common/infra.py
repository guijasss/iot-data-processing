from typing import Callable, Optional
from time import sleep

from psycopg2 import connect, OperationalError

import paho.mqtt.client as mqtt
from psycopg2.extras import execute_values


class MQTTHandler:
    """Gerencia conexões e comunicações MQTT"""
    def __init__(self, broker: str = "mqtt", port: int = 1883):
        self.broker = broker
        self.port = port
        self.client: Optional[mqtt.Client] = None
        self._message_callback: Optional[Callable] = None

    def connect(self, topic: str, on_message: Callable) -> mqtt.Client:
        """Conecta ao broker MQTT e se inscreve no tópico"""
        self._message_callback = on_message
        self.client = mqtt.Client()
        self.client.on_message = self._on_message_wrapper
        self.client.connect(self.broker, self.port, 60)
        self.client.subscribe(topic)
        print(f"connected to {self.broker}:{self.port} and subscribed to {topic}")
        return self.client

    def _on_message_wrapper(self, client: mqtt.Client, _, msg: mqtt.MQTTMessage):
        """Wrapper para o callback de mensagem"""
        if self._message_callback:
            self._message_callback(client, msg)

    def publish(self, topic: str, message: str):
        """Publica mensagem em um tópico"""
        if self.client:
            self.client.publish(topic, message, qos=1)

    def start(self):
        """Inicia o loop MQTT"""
        if self.client:
            self.client.loop_forever()


class PostgreSQLHandler:
    """Gerencia conexões e operações com o PostgreSQL."""

    def __init__(self, containerized: bool = True):
        # Carrega os parâmetros de conexão a partir de variáveis de ambiente
        self.db_params = {
            'dbname': 'metrics',
            'user': 'user_tcc',
            'password': 'password_tcc',
            'host': 'metrics_db' if containerized == True else 'localhost',
            'port': 5432
        }
        self.connection = self.init_db()

    def init_db(self):
        """Tenta conectar ao DB e inicializa as tabelas se não existirem."""
        conn = None
        attempts = 5
        while attempts > 0 and conn is None:
            try:
                print("Tentando conectar ao PostgreSQL...")
                conn = connect(**self.db_params)
                print("Conexão bem-sucedida!")
            except OperationalError as e:
                print(f"Erro ao conectar: {e}. Tentando novamente em 5 segundos...")
                attempts -= 1
                sleep(5)

        if conn is None:
            print("Não foi possível conectar ao banco de dados após várias tentativas.")
            raise OperationalError("Falha na conexão com o PostgreSQL.")

        cursor = conn.cursor()

        # Sintaxe ajustada para PostgreSQL (SERIAL ao invés de AUTOINCREMENT)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS metrics (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMPTZ,
            container TEXT,
            cpu_percent REAL,
            mem_usage REAL,
            mem_limit REAL,
            mem_percent REAL,
            rx_bytes REAL,
            tx_bytes REAL,
            io_read REAL,
            io_write REAL,
            restarts INTEGER
        )
       ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            event_id VARCHAR,
            sensor_id VARCHAR,
            timestamp TIMESTAMPTZ,
            payload JSON
        )
        ''')

        cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            event_id VARCHAR,
            sensor_id VARCHAR,
            timestamp TIMESTAMPTZ,
            type VARCHAR,
            severity VARCHAR,
            details VARCHAR
        )
        ''')

        conn.commit()
        cursor.close()
        return conn

    def insert_one(self, table_name: str, data_dict: dict):
        self.insert_many(table_name, [data_dict])

    def insert_many(self, table_name: str, data_list: list[dict]):
        if not data_list:
            print("A lista de dados está vazia. Nenhuma inserção foi realizada.")
            return

        cursor = self.connection.cursor()

        columns = data_list[0].keys()
        column_names = '", "'.join(columns)
        insert_query = f'INSERT INTO "{table_name}" ("{column_names}") VALUES %s'
        values_to_insert = [tuple(d.values()) for d in data_list]

        try:
            execute_values(cursor, insert_query, values_to_insert)
            self.connection.commit()
        except Exception as e:
            print(f"Erro ao inserir dados na tabela '{table_name}': {e.args}")
            self.connection.rollback()
        finally:
            cursor.close()

    def run_query(self, sql: str) -> list:
        cursor = self.connection.cursor()
        cursor.execute(sql)
        results = cursor.fetchall()
        self.connection.commit()
        return results

    def clean_tables(self) -> None:
        try:
            cursor = self.connection.cursor()
            # TRUNCATE é mais rápido que DELETE para limpar tabelas inteiras
            # RESTART IDENTITY reseta os contadores dos campos SERIAL
            print("Limpando tabelas: metrics, events, aggregates...")
            cursor.execute("TRUNCATE TABLE metrics, events, alerts RESTART IDENTITY;")
            self.connection.commit()
            cursor.close()
            print("Tabelas limpas com sucesso.")
        except Exception as e:
            print(f"Erro ao limpar as tabelas: {e}")
            self.connection.rollback()  # Desfaz a transação em caso de erro

    def close_connection(self) -> None:
        if self.connection:
            self.connection.close()
            print("Conexão com o PostgreSQL fechada.")