from typing import Callable, Optional
import paho.mqtt.client as mqtt


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
        print(f"Connected to {self.broker}:{self.port} and subscribed to {topic}")
        return self.client

    def _on_message_wrapper(self, client: mqtt.Client, userdata, msg: mqtt.MQTTMessage):
        """Wrapper para o callback de mensagem"""
        if self._message_callback:
            self._message_callback(client, msg)

    def publish(self, topic: str, message: str):
        """Publica mensagem em um tópico"""
        if self.client:
            self.client.publish(topic, message)

    def start(self):
        """Inicia o loop MQTT"""
        if self.client:
            self.client.loop_forever()