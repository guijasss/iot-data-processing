from json import loads
from datetime import datetime
from time import time

import numpy as np
import paho.mqtt.client as mqtt

from processing.alerts import detect_alerts
from common.utils import event_to_json
from common.entities import SensorOutput, WaveMeasure, Engine


class MotorMonitor:
    def __init__(self, engine_id="motor-001", rated_speed=1800, rated_current=5.0, max_temperature=80.0):
        self.engine = Engine(engine_id=engine_id, rated_speed=rated_speed, rated_current=rated_current,
                             max_temperature=max_temperature)
        self.MQTT_BROKER = "mqtt"
        self.MQTT_PORT = 1883
        self.MQTT_TOPIC = "readings"
        self.MQTT_TOPIC_OUT = "sensors/aggregations"
        self.AGGREGATION_INTERVAL = 10
        self.buffer = []
        self.previous_temp = None
        self.last_aggregation_time = time()

    def create_client(self):
        client = mqtt.Client()
        client.on_message = self.on_message_callback
        client.connect(self.MQTT_BROKER, self.MQTT_PORT, 60)
        client.subscribe(self.MQTT_TOPIC)
        print(f"Processing started: Subscribed to {self.MQTT_TOPIC} on {self.MQTT_BROKER}:{self.MQTT_PORT}")
        return client

    def on_message_callback(self, client, userdata, msg):
        payload = msg.payload.decode('utf-8')
        print(f"Mensagem recebida no tópico {msg.topic}: {payload[:100]}...")  # Log para debug (trunca se longo)
        data = loads(payload)
        output = self.process_message(data)
        self.handle_alerts(client, output)
        self.buffer.append(output)
        self.check_aggregation_threshold(client)

    def process_message(self, data):
        return SensorOutput(
            device_id=data["device_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            rpm=data["rpm"],
            vibration=WaveMeasure(
                sampling_rate=data["vibration"]["sampling_rate"],
                values=data["vibration"]["values"]
            ),
            current=WaveMeasure(
                sampling_rate=data["current"]["sampling_rate"],
                values=data["current"]["values"]
            ),
            temperature=data["temperature"]
        )

    def handle_alerts(self, client, output: SensorOutput):
        alerts = detect_alerts(output, self.engine, previous_temp=self.previous_temp)
        if alerts:
            print(f"Alertas detectados: {alerts}")
            for alert in alerts:
                alert.pop("details")
                client.publish("sensors/alerts", event_to_json(alert))
        else:
            print("Nenhum alerta detectado.")
        self.previous_temp = output["temperature"]

    def check_aggregation_threshold(self, client):
        if time() - self.last_aggregation_time >= self.AGGREGATION_INTERVAL:
            aggregated = self.aggregate_data(self.buffer)
            client.publish(self.MQTT_TOPIC_OUT, event_to_json(aggregated))
            print(f"Resumo agregado enviado: {aggregated}")
            self.buffer.clear()
            self.last_aggregation_time = time()

    def aggregate_data(self, buffer):
        if not buffer:
            return {"error": "Nenhum dado para agregar"}

        # Calcula aggregations
        aggregated_data = {
            "device_id": buffer[0]["device_id"],
            "period_start": min(d["timestamp"] for d in buffer),
            "period_end": max(d["timestamp"] for d in buffer),
            "event_count": len(buffer),
            "avg_rpm": np.mean([d["rpm"] for d in buffer]),
            "min_rpm": np.min([d["rpm"] for d in buffer]),
            "max_rpm": np.max([d["rpm"] for d in buffer]),
            "avg_temperature": np.mean([d["temperature"] for d in buffer]),
            "min_temperature": np.min([d["temperature"] for d in buffer]),
            "max_temperature": np.max([d["temperature"] for d in buffer]),
            "std_temperature": np.std([d["temperature"] for d in buffer]),
            "vibration": {},
            "current": {}
        }

        # Calcula agregações para vibração e corrente
        vib_rms_values = []
        curr_rms_values = []
        bearing_peaks = []
        bearing_freqs = []
        harmonic_peaks = []

        for d in buffer:
            # Calcula RMS
            vib_rms = np.sqrt(np.mean(np.array(d["vibration"]["values"]) ** 2))
            curr_rms = np.sqrt(np.mean(np.array(d["current"]["values"]) ** 2))
            vib_rms_values.append(vib_rms)
            curr_rms_values.append(curr_rms)

            # Extrai frequências e picos
            base_freq = d["rpm"] / 60.0
            bearing_freq = 0.5 * base_freq
            bearing_freqs.append(bearing_freq)

            # Pico para rolamentos
            bearing_peak = np.max(np.abs(np.fft.fft(d["vibration"]["values"]))) * 0.01
            bearing_peaks.append(bearing_peak)

            # Pico para harmônicas
            harmonic_peak = np.max(np.abs(np.fft.fft(d["current"]["values"]))) * 0.01
            harmonic_peaks.append(harmonic_peak)

        aggregated_data["vibration"]["avg_rms"] = np.mean(vib_rms_values)
        aggregated_data["vibration"]["max_rms"] = np.max(vib_rms_values)
        aggregated_data["vibration"]["avg_peak_bearing"] = np.mean(bearing_peaks)
        aggregated_data["vibration"]["avg_bearing_freq"] = np.mean(bearing_freqs)

        aggregated_data["current"]["avg_rms"] = np.mean(curr_rms_values)
        aggregated_data["current"]["max_rms"] = np.max(curr_rms_values)
        aggregated_data["current"]["avg_harmonic_peak"] = np.mean(harmonic_peaks)

        return aggregated_data


# Uso do sistema
if __name__ == "__main__":
    monitor = MotorMonitor()
    client = monitor.create_client()
    client.loop_forever()
