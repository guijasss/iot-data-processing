from paho.mqtt.client import Client

MQTT_BROKER = 'mqtt'
MQTT_PORT = 1883
MQTT_TOPIC = 'readings'

class MQTTClient:
    def __init__(self):
        self.client = Client()
        self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
        self.client.loop_start()

    def send(self, message: str):
        self.client.publish(MQTT_TOPIC, message)
