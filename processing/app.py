from typing import cast
import paho.mqtt.client as mqtt
from datetime import datetime

from common.entities import Engine
from common.properties import *
from common.utils import event_to_json
from common.infra import MQTTHandler, PostgreSQLHandler
from processing.event_processor import EventProcessor

import processing.monitor as gpio


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

        self.PIN_ALERTA_TEMPERATURA = 11
        self.PIN_ALERTA_CORRENTE = 12

        gpio.setmode(gpio.BOARD)
        gpio.setup(self.PIN_ALERTA_TEMPERATURA, gpio.OUT)
        gpio.setup(self.PIN_ALERTA_CORRENTE, gpio.OUT)

        self.MQTT_TOPIC_IN = "readings"
        self.MQTT_TOPIC_AGGREGATIONS = "sensors/aggregations"

        self.mqtt_handler = MQTTHandler()
        self.sql_client = PostgreSQLHandler()
        self.event_processor = EventProcessor(self.engine, aggregation_interval)

    def start(self):
        gpio.start_renderer()

        print(f"\nMonitor do '{self.engine.engine_id}' iniciado.")
        print("Ouvindo mensagens MQTT reais...")
        print("Pressione CTRL+C para sair.")

        self.mqtt_handler.connect(self.MQTT_TOPIC_IN, self._on_message)
        self.mqtt_handler.start()  # Assume que isso bloqueia (ex: loop_forever())

    def _on_message(self, _, msg: mqtt.MQTTMessage):
        gpio.output(self.PIN_ALERTA_TEMPERATURA, gpio.LOW)
        gpio.output(self.PIN_ALERTA_CORRENTE, gpio.LOW)

        payload = cast(bytes, msg.payload).decode('utf-8')

        alerts, aggregation = self.event_processor.process_event(payload)

        for alert in alerts:
            alert.update({"timestamp": datetime.now()})
            alert_type = alert.get('type')

            if alert_type == 'overheating':
                gpio.output(self.PIN_ALERTA_CORRENTE, gpio.HIGH)

            self.sql_client.insert_one("alerts", alert)

        if aggregation:
            self.mqtt_handler.publish(
                self.MQTT_TOPIC_AGGREGATIONS,
                event_to_json(aggregation)
            )


# --- main.py (Modificado para incluir o cleanup) ---
if __name__ == "__main__":
    print(f"Início do processamento! {datetime.now()}")

    monitor = MotorMonitor(
        engine_id="motor-001",
        rated_speed=RATED_SPEED,
        rated_current=RATED_CURRENT,
        max_temperature=MAX_TEMPERATURE,
        aggregation_interval=AGGREGATION_INTERVAL
    )

    try:
        monitor.start()
    except KeyboardInterrupt:
        print("\nEncerrando monitor...")
    finally:
        # --- MODIFICAÇÃO: Garante a limpeza do simulador ---
        gpio.cleanup()