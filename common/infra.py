from typing import Callable, Optional, Literal
from dotenv import load_dotenv
from os import getenv

import paho.mqtt.client as mqtt

load_dotenv()

configs = {
    "local": {
        "host": "mqtt",
        "port": 1883,
        "username": None,
        "password": None
    },
    "cloud": {
        "host": "1f7a01b9544f4063bb9409d0b91ac77c.s1.eu.hivemq.cloud",
        "port": 8883,
        "username": getenv("MQTT_USERNAME"),
        "password": getenv("MQTT_PASSWORD")
    }
}


class MQTTHandler:
    """Gerencia conexões e comunicações MQTT (local ou nuvem)"""

    def __init__(self, env: Literal["local", "cloud"]):
        config = configs[env]
        self.env = env
        self.broker = config["host"]
        self.port = config["port"]
        self.username = config["username"]
        self.password = config["password"]
        print(config)

        self.client: Optional[mqtt.Client] = None
        self._message_callback: Optional[Callable] = None

    def connect(self, topic: str, on_message: Callable) -> mqtt.Client:
        """Conecta ao broker MQTT e se inscreve no tópico"""
        self._message_callback = on_message

        # Usar v5 é uma boa prática para brokers modernos como HiveMQ
        self.client = mqtt.Client(protocol=mqtt.MQTTv5)
        self.client.on_message = self._on_message_wrapper

        # --- LÓGICA DE CONEXÃO NA NUVEM ---
        if self.env == "cloud":
            self.client.username_pw_set(self.username, self.password)

            self.client.tls_set()
            print("Conectando ao HiveMQ Cloud com TLS...")

        try:
            # 3. Conecta usando o host e a porta corretos
            self.client.connect(self.broker, self.port, 60)
            self.client.subscribe(topic)
            print(f"Conectado a {self.broker}:{self.port} e inscrito no tópico {topic}")
            return self.client
        except Exception as e:
            print(f"Erro ao conectar ao broker MQTT ({self.broker}): {e}")
            raise

    def _on_message_wrapper(self, client: mqtt.Client, _, msg: mqtt.MQTTMessage):
        """Wrapper para o callback de mensagem"""
        if self._message_callback:
            self._message_callback(client, msg)

    def publish(self, topic: str, message: str):
        """Publica mensagem em um tópico"""
        if self.client:
            self.client.publish(topic, message, qos=1)
        else:
            print("Erro: Cliente MQTT não conectado. Não foi possível publicar.")

    def start(self):
        """Inicia o loop MQTT"""
        if self.client:
            self.client.loop_forever()

    def stop(self):
        self.client.loop_stop()
