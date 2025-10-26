import json
from typing import cast, Dict
import paho.mqtt.client as mqtt
from datetime import datetime

from common.entities import Engine
from common.properties import *
from common.utils import event_to_json
from common.infra import MQTTHandler
from processing.event_processor import EventProcessor


class EdgeApp:
    def __init__(self):

        # --- Configuração Geral ---
        self.aggregation_interval = AGGREGATION_INTERVAL
        self.MQTT_TOPIC_IN = "readings"
        self.MQTT_TOPIC_AGGREGATIONS = "sensors/aggregations"

        self.sensor_configs: Dict[str, Engine] = self._load_sensor_configs()
        self.processors: Dict[str, EventProcessor] = {}
        self.mqtt_handler = MQTTHandler()


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
        print(f"\nProcessador de Borda ('EdgeApp') iniciado.")
        print(f"Ouvindo tópico MQTT: '{self.MQTT_TOPIC_IN}' para {len(self.sensor_configs)} sensores...")
        print("Pressione CTRL+C para sair.")

        self.mqtt_handler.connect(self.MQTT_TOPIC_IN, self._on_message)
        self.mqtt_handler.start()

    def _on_message(self, _, msg: mqtt.MQTTMessage):
        payload = cast(bytes, msg.payload).decode('utf-8')

        sensor_id = self._get_sensor_id_from_payload(payload)
        if not sensor_id:
            return

        processor = self._get_or_create_processor(sensor_id)
        if not processor:
            return

        alerts, aggregation = processor.process_event(payload)

        for alert in alerts:
            alert_type = alert.get('type')

            if alert_type == 'bearing_wear':
                with open(f"/app/logs/alerts_{NUM_MOTORS}_engines", "a") as file:
                    file.write(event_to_json({
                        "timestamp": alert["timestamp"],
                        "event_id": alert["event_id"],
                        "sensor_id": alert["sensor_id"],
                        "temperature": alert["details"]
                    }) + '\n')

        if aggregation:
            self.mqtt_handler.publish(
                self.MQTT_TOPIC_AGGREGATIONS,
                event_to_json(aggregation)
            )


# --- Ponto de Entrada ---
if __name__ == "__main__":
    print(f"Início do processamento! {datetime.now()}")
    app = EdgeApp()

    try:
        app.start()
    except KeyboardInterrupt:
        print("\nEncerrando processador de borda...")
