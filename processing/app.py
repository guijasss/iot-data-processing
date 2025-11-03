import json
from typing import cast, Dict
import paho.mqtt.client as mqtt
from datetime import datetime
from time import sleep  # Importado para o loop principal

# Supondo que o handler que você quer usar é o do seu Canvas
# Mude 'mqtt_handler_cloud' se o nome do seu arquivo for outro
try:
    from mqtt_handler_cloud import MQTTHandler
except ImportError:
    print("=" * 50)
    print("ERRO: 'mqtt_handler_cloud.py' não encontrado.")
    print("Por favor, garanta que o arquivo do Canvas esteja salvo no mesmo diretório.")
    print("Usando o import 'common.infra.MQTTHandler' como fallback...")
    print("=" * 50)
    # Fallback para o seu import original
    from common.infra import MQTTHandler

# Seus imports originais
from common.entities import Engine
from common.properties import *
from common.utils import event_to_json
from processing.event_processor import EventProcessor


class EdgeApp:
    def __init__(self):
        self.aggregation_interval = AGGREGATION_INTERVAL

        # Tópicos de entrada (Lido do Local)
        self.MQTT_TOPIC_IN = "readings"

        # Tópicos de saída (Escrito na Nuvem)
        self.MQTT_TOPIC_AGGREGATIONS = "sensors/aggregations"
        self.MQTT_TOPIC_ALERTS = "sensors/alerts"  # Tópico para o dashboard

        self.sensor_configs: Dict[str, Engine] = self._load_sensor_configs()
        self.processors: Dict[str, EventProcessor] = {}

        # --- MUDANÇA PRINCIPAL: DOIS HANDLERS ---

        # 1. Handler para ESCUTAR (Subscribe) o broker local
        print("Iniciando handler MQTT local (para escutar)...")
        self.mqtt_local_handler = MQTTHandler(env="local")

        # 2. Handler para PUBLICAR (Publish) na nuvem
        print("Iniciando handler MQTT cloud (para publicar)...")
        self.mqtt_cloud_handler = MQTTHandler(env="cloud")
        # ----------------------------------------

    @staticmethod
    def _load_sensor_configs() -> Dict[str, Engine]:
        # (Sem alteração)
        print("Carregando configuração dos sensores...")
        configs = {}
        for i in range(1, NUM_MOTORS + 1):
            sensor_id = f"edge-{i:03d}"

            configs[sensor_id] = Engine(
                engine_id=sensor_id,
                rated_speed=RATED_SPEED,
                rated_current=RATED_CURRENT,
                max_temperature=MAX_TEMPERATURE
            )

        print(f"Carregados: {list(configs.keys())}")
        return configs

    @staticmethod
    def _get_sensor_id_from_payload(payload: str) -> str | None:
        # (Sem alteração)
        try:
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
        # (Sem alteração)
        processor = self.processors.get(sensor_id)
        if processor:
            return processor

        config = self.sensor_configs.get(sensor_id)
        if not config:
            print(f"Alerta: Evento recebido para sensor desconhecido ('{sensor_id}'). Ignorando.")
            return None

        print(f"Detectado primeiro evento do sensor '{sensor_id}'. Criando processador...")
        processor = EventProcessor(config, self.aggregation_interval)
        self.processors[sensor_id] = processor
        return processor

    def start(self):
        """
        Conecta ambos os handlers e inicia seus loops (não-bloqueantes).
        """
        print(f"\nProcessador de Borda ('EdgeApp') iniciando modo ponte...")

        # 1. Conecta e escuta o broker LOCAL
        print(f"Conectando ao broker LOCAL para escutar: {self.MQTT_TOPIC_IN}")
        self.mqtt_local_handler.connect(self.MQTT_TOPIC_IN, self._on_message)

        # 2. Apenas conecta o broker da NUVEM (para poder publicar)
        #    Escutamos um tópico "dummy" só para estabelecer a conexão.
        print("Conectando ao broker CLOUD para publicar...")
        self.mqtt_cloud_handler.connect("sensors/alerts", lambda c, m: None)  # Callback vazio

        # 3. Inicia os loops (não-bloqueantes, vindo de mqtt_handler_cloud.py)
        self.mqtt_local_handler.start()
        self.mqtt_cloud_handler.start()

        print("\nPronto. Escutando localmente e publicando na nuvem.")

    def stop(self):
        """Para os loops MQTT de forma limpa."""
        print("\nEncerrando processador de borda...")
        if self.mqtt_local_handler:
            self.mqtt_local_handler.stop()
        if self.mqtt_cloud_handler:
            self.mqtt_cloud_handler.stop()

    def _on_message(self, _, msg: mqtt.MQTTMessage):
        """
        Callback: Chamado quando uma mensagem chega do broker LOCAL.
        """
        payload = cast(bytes, msg.payload).decode('utf-8')

        sensor_id = self._get_sensor_id_from_payload(payload)
        if not sensor_id:
            return

        processor = self._get_or_create_processor(sensor_id)
        if not processor:
            return

        # Processa o evento (sem mudança)
        alerts, aggregation = processor.process_event(payload)

        # --- MUDANÇA: PUBLICAR NA NUVEM ---

        # 1. Lida com Alertas
        for alert in alerts:
            alert_type = alert.get('type')

            # (Sua lógica de log local)
            if alert_type == 'bearing_wear':
                with open(f"/app/logs/alerts_{NUM_MOTORS}_engines", "a") as file:
                    # Correção: "temperature" -> "details"
                    file.write(event_to_json({
                        "timestamp": alert["timestamp"],
                        "event_id": alert["event_id"],
                        "sensor_id": alert["sensor_id"],
                        "details": alert["details"]
                    }) + '\n')

            # Publica o alerta na NUVEM
            print(f"Publicando alerta '{alert_type}' do sensor '{sensor_id}' na NUVEM.")
            self.mqtt_cloud_handler.publish(
                self.MQTT_TOPIC_ALERTS,  # Tópico de Alertas
                event_to_json(alert)  # Envia o alerta completo
            )

        # 2. Lida com Agregações
        if aggregation:
            # Publica a agregação na NUVEM
            print(f"Publicando agregação do sensor '{sensor_id}' na NUVEM.")
            self.mqtt_cloud_handler.publish(
                self.MQTT_TOPIC_AGGREGATIONS,  # Tópico de Agregações
                event_to_json(aggregation)
            )


# --- Ponto de Entrada ---
if __name__ == "__main__":
    print(f"Início do processamento! {datetime.now()}")
    app = EdgeApp()

    try:
        app.start()
        print("Processador rodando. Pressione CTRL+C para sair.")
        while True:
            sleep(10)
    except KeyboardInterrupt:
        print("\nCTRL+C detectado. Encerrando...")
    except Exception as e:
        print(f"Erro inesperado no loop principal: {e}")
    finally:
        app.stop()  # Garante que os loops MQTT parem
