import json
from typing import cast, Dict
import paho.mqtt.client as mqtt
from datetime import datetime

# Supondo que 'Engine' e 'SensorOutput' estejam em common.entities
# e as constantes em common.properties
from common.entities import Engine, SensorOutput
from common.properties import *
from common.utils import event_to_json
from common.infra import MQTTHandler, PostgreSQLHandler
from processing.event_processor import EventProcessor

# O módulo 'monitor' (gpio) é global para a aplicação
import processing.monitor as gpio


class EdgeApp:
    def __init__(self, aggregation_interval: int):

        # --- Configuração Geral ---
        self.aggregation_interval = aggregation_interval
        self.MQTT_TOPIC_IN = "readings"
        self.MQTT_TOPIC_AGGREGATIONS = "sensors/aggregations"

        # --- Lógica Multi-Sensor ---
        # 1. Dicionário para armazenar as configurações estáticas de cada sensor
        #    (Chave: sensor_id, Valor: objeto Engine com seus limites)
        self.sensor_configs: Dict[str, Engine] = self._load_sensor_configs()

        # 2. Dicionário para armazenar os processadores de estado
        #    (Chave: sensor_id, Valor: instância do EventProcessor)
        self.processors: Dict[str, EventProcessor] = {}

        # --- Handlers (sem mudança) ---
        self.mqtt_handler = MQTTHandler()
        # self.sql_client = PostgreSQLHandler() # Descomente se for usar

        # --- Configuração do GPIO (Global) ---
        # Estes pinos agora refletem o estado de *qualquer* sensor
        self.PIN_ALERTA_TEMPERATURA = 11  # OBS: Este pino não estava sendo usado no seu código
        self.PIN_ALERTA_CORRENTE_OU_SOBREAQUECIMENTO = 12  # Pin 12

        gpio.setmode(gpio.BOARD)
        gpio.setup(self.PIN_ALERTA_TEMPERATURA, gpio.OUT)
        gpio.setup(self.PIN_ALERTA_CORRENTE_OU_SOBREAQUECIMENTO, gpio.OUT)

    @staticmethod
    def _load_sensor_configs() -> Dict[str, Engine]:
        """
        Carrega as configurações estáticas dos sensores.
        No TCC, isso viria de um arquivo de configuração ou banco.
        Aqui, vamos "chumbar" os 5 sensores que você simulou.
        """
        print("Carregando configuração dos sensores...")
        configs = {}
        for i in range(1, 6):  # Para 5 motores (edge-001 a edge-005)
            sensor_id = f"edge-{i:03d}"
            # Assumindo que todos têm as mesmas propriedades nominais
            configs[sensor_id] = Engine(
                engine_id=sensor_id,  # Usamos o sensor_id como engine_id
                rated_speed=RATED_SPEED,
                rated_current=RATED_CURRENT,
                max_temperature=MAX_TEMPERATURE
            )

        print(f"Carregados: {list(configs.keys())}")
        return configs

    @staticmethod
    def _get_sensor_id_from_payload(payload: str) -> str | None:
        """ Extrai o sensor_id do JSON sem decodificar o resto todo """
        try:
            # Carrega apenas o suficiente para pegar o ID
            data = json.loads(payload)
            sensor_id = data.get("sensor_id")
            if not sensor_id:
                print(f"Erro: Evento recebido sem 'sensor_id' no payload.")
                return None
            return sensor_id
        except json.JSONDecodeError:
            print(f"Erro: Payload MQTT não é um JSON válido: {payload[:50]}...")
            return None

    def _get_or_create_processor(self, sensor_id: str) -> EventProcessor | None:
        """
        Busca um processador existente. Se não existir, cria um novo.
        """
        # 1. Tenta buscar um processador já existente
        processor = self.processors.get(sensor_id)
        if processor:
            return processor

        # 2. Processador não existe, precisamos criar um novo
        # 2a. Buscar a configuração estática para este sensor
        config = self.sensor_configs.get(sensor_id)
        if not config:
            print(f"Alerta: Evento recebido para sensor desconhecido ('{sensor_id}'). Ignorando.")
            return None

        # 2b. Criar e armazenar o novo processador
        print(f"Detectado primeiro evento do sensor '{sensor_id}'. Criando processador...")
        processor = EventProcessor(config, self.aggregation_interval)
        self.processors[sensor_id] = processor
        return processor

    def start(self):
        gpio.start_renderer()
        print(f"\nProcessador de Borda ('EdgeApp') iniciado.")
        print(f"Ouvindo tópico MQTT: '{self.MQTT_TOPIC_IN}' para {len(self.sensor_configs)} sensores...")
        print("Pressione CTRL+C para sair.")

        self.mqtt_handler.connect(self.MQTT_TOPIC_IN, self._on_message)
        self.mqtt_handler.start()

    def _on_message(self, _, msg: mqtt.MQTTMessage):
        """
        Callback principal. Roteia eventos para o processador correto.
        """
        # --- Lógica de Roteamento ---
        payload = cast(bytes, msg.payload).decode('utf-8')

        sensor_id = self._get_sensor_id_from_payload(payload)
        if not sensor_id:
            return  # Ignora evento malformado ou sem ID

        processor = self._get_or_create_processor(sensor_id)
        if not processor:
            return  # Ignora evento de sensor desconhecido

        # --- Lógica de Processamento (agora por sensor) ---

        # Resetamos os pinos globais a cada evento recebido
        # (Isso fará a luz "piscar" se houver alertas)
        gpio.output(self.PIN_ALERTA_TEMPERATURA, gpio.LOW)
        gpio.output(self.PIN_ALERTA_CORRENTE_OU_SOBREAQUECIMENTO, gpio.LOW)

        alerts, aggregation = processor.process_event(payload)

        # --- Lógica de Saída (Alertas e Agregação) ---

        # Se *este* evento gerou alertas, aciona os pinos globais
        for alert in alerts:
            alert.update({"timestamp": datetime.now()})  # Atualiza timestamp
            alert_type = alert.get('type')

            if alert_type == 'overheating':
                # Seu código original acionava o pino 12 (CORRENTE) para 'overheating'
                gpio.output(self.PIN_ALERTA_CORRENTE_OU_SOBREAQUECIMENTO, gpio.HIGH)

            # TODO: Adicionar lógica para outros tipos de alerta (ex: pino 11)
            # if alert_type == 'overload':
            #    gpio.output(self.PIN_ALERTA_TEMPERATURA, gpio.HIGH) # Exemplo

            # Salvar no banco (descomente se for usar)
            # print(f"ALERTA [Sensor: {sensor_id}]: {alert_type}")
            # self.sql_client.insert_one("alerts", alert)

        # Se *este* processador decidiu agregar, publica a agregação
        if aggregation:
            # A agregação já contém o sensor_id correto
            # print(f"AGREGAÇÃO [Sensor: {sensor_id}]")
            self.mqtt_handler.publish(
                self.MQTT_TOPIC_AGGREGATIONS,
                event_to_json(aggregation)
            )


# --- Ponto de Entrada ---
if __name__ == "__main__":
    print(f"Início do processamento! {datetime.now()}")

    # Agora criamos a aplicação principal, que gerencia *todos* os sensores
    app = EdgeApp(
        aggregation_interval=AGGREGATION_INTERVAL
    )

    try:
        app.start()
    except KeyboardInterrupt:
        print("\nEncerrando processador de borda...")
    finally:
        # Garante a limpeza do GPIO
        gpio.cleanup()
