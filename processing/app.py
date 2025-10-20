from typing import cast
import paho.mqtt.client as mqtt
from datetime import datetime

# --- SUAS IMPORTAÇÕES REAIS ---
from common.entities import Engine
from common.utils import event_to_json
from common.infra import MQTTHandler, PostgreSQLHandler
from processing.event_processor import EventProcessor
import processing.monitor as GPIO


class MotorMonitor:
    def __init__(
            self,
            engine_id: str,
            rated_speed: int,
            rated_current: float,
            max_temperature: float,
            aggregation_interval: int
    ):
        # Configuração do motor (sem mudanças)
        self.engine = Engine(
            engine_id=engine_id,
            rated_speed=rated_speed,
            rated_current=rated_current,
            max_temperature=max_temperature
        )

        # --- MODIFICAÇÃO: Define os pinos físicos para os alertas ---
        # (Você pode mapear os tipos de alerta para pinos)
        self.PIN_ALERTA_TEMPERATURA = 11
        self.PIN_ALERTA_CORRENTE = 12
        # Adicione mais pinos se precisar

        # --- MODIFICAÇÃO: Configura os pinos do MOCK GPIO ---
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(self.PIN_ALERTA_TEMPERATURA, GPIO.OUT)
        GPIO.setup(self.PIN_ALERTA_CORRENTE, GPIO.OUT)
        # ----------------------------------------------------

        # Tópicos (Note que MQTT_TOPIC_ALERTS foi removido)
        self.MQTT_TOPIC_IN = "readings"
        self.MQTT_TOPIC_AGGREGATIONS = "sensors/aggregations"

        # Seus handlers reais (sem mudanças)
        self.mqtt_handler = MQTTHandler()
        self.sql_client = PostgreSQLHandler()
        self.event_processor = EventProcessor(self.engine, aggregation_interval)

    def start(self):
        # --- MODIFICAÇÃO: Inicia o "monitor" do terminal ---
        GPIO.start_renderer()
        # --------------------------------------------------

        print(f"\nMonitor do '{self.engine.engine_id}' iniciado.")
        print("Ouvindo mensagens MQTT reais...")
        print("Pressione CTRL+C para sair.")

        # Seu código de conexão MQTT real
        self.mqtt_handler.connect(self.MQTT_TOPIC_IN, self._on_message)
        self.mqtt_handler.start()  # Assume que isso bloqueia (ex: loop_forever())

    def _on_message(self, _, msg: mqtt.MQTTMessage):

        # --- MODIFICAÇÃO: Reseta os pinos de alerta ---
        # Garante que as luzes apaguem se o alerta parar
        GPIO.output(self.PIN_ALERTA_TEMPERATURA, GPIO.LOW)
        GPIO.output(self.PIN_ALERTA_CORRENTE, GPIO.LOW)
        # ---------------------------------------------

        payload = cast(bytes, msg.payload).decode('utf-8')

        alerts, aggregation = self.event_processor.process_event(payload)

        # Publica alertas (Lógica substituída)
        for alert in alerts:
            alert.update({"timestamp": datetime.now()})

            # --- LÓGICA DE SIMULAÇÃO SUBSTITUÍDA ---
            # Em vez de publicar no MQTT, aciona o pino GPIO
            alert_type = alert.get('type')  # Assumindo que seu alerta tem um 'type'

            if alert_type == 'high_temperature':  # (Ajuste para o nome real do seu alerta)
                GPIO.output(self.PIN_ALERTA_TEMPERATURA, GPIO.HIGH)

            elif alert_type == 'overheating':  # (Ajuste para o nome real do seu alerta)
                GPIO.output(self.PIN_ALERTA_CORRENTE, GPIO.HIGH)

            # Você pode adicionar mais 'elifs' para outros tipos de alerta
            # ------------------------------------------

            # Você ainda salva no banco (sem mudanças)
            self.sql_client.insert_one("alerts", alert)

        # Publica agregação se houver (sem mudanças)
        if aggregation:
            self.mqtt_handler.publish(
                self.MQTT_TOPIC_AGGREGATIONS,
                event_to_json(aggregation)
            )


# --- main.py (Modificado para incluir o cleanup) ---
if __name__ == "__main__":
    monitor = MotorMonitor(
        engine_id="motor-001",
        rated_speed=1800,
        rated_current=5.0,
        max_temperature=44.0,
        aggregation_interval=10
    )

    try:
        monitor.start()
    except KeyboardInterrupt:
        print("\nEncerrando monitor...")
    finally:
        # --- MODIFICAÇÃO: Garante a limpeza do simulador ---
        GPIO.cleanup()