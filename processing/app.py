from typing import cast
import paho.mqtt.client as mqtt
from datetime import datetime

from common.entities import Engine
from common.utils import event_to_json
from common.infra import MQTTHandler, PostgreSQLHandler
from event_processor import EventProcessor


class MotorMonitor:
    def __init__(
            self,
            engine_id: str = "engine-001",
            rated_speed: int = 1800,
            rated_current: float = 5.0,
            max_temperature: float = 50.0,
            aggregation_interval: int = 10
    ):
        # Configuração do motor
        self.engine = Engine(
            engine_id=engine_id,
            rated_speed=rated_speed,
            rated_current=rated_current,
            max_temperature=max_temperature
        )

        self.MQTT_TOPIC_IN = "readings"
        self.MQTT_TOPIC_ALERTS = "sensors/alerts"
        self.MQTT_TOPIC_AGGREGATIONS = "sensors/aggregations"

        self.mqtt_handler = MQTTHandler()
        self.sql_client = PostgreSQLHandler()
        self.event_processor = EventProcessor(self.engine, aggregation_interval)

    def start(self):
        self.mqtt_handler.connect(self.MQTT_TOPIC_IN, self._on_message)
        self.mqtt_handler.start()

    def _on_message(self, _, msg: mqtt.MQTTMessage):
        payload = cast(bytes, msg.payload).decode('utf-8')

        alerts, aggregation = self.event_processor.process_event(payload)

        # Publica alertas
        for alert in alerts:
            alert.update({"timestamp": datetime.now()})
            self.mqtt_handler.publish(
                self.MQTT_TOPIC_ALERTS,
                event_to_json(alert)
            )
            self.sql_client.insert_one("alerts", alert)

        # Publica agregação se houver
        if aggregation:
            self.mqtt_handler.publish(
                self.MQTT_TOPIC_AGGREGATIONS,
                event_to_json(aggregation)
            )


# main.py
if __name__ == "__main__":
    monitor = MotorMonitor(
        engine_id="motor-001",
        rated_speed=1800,
        rated_current=5.0,
        max_temperature=44.0,
        aggregation_interval=10
    )
    monitor.start()
