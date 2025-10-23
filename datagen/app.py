from numpy import exp, linspace, pi, random, sin, sqrt
from datetime import datetime
from time import monotonic, sleep
from uuid import uuid4

from common.entities import SensorOutput, WaveMeasure
from common.properties import *
from common.infra import PostgreSQLHandler
from datagen.infra import MQTTClient
from common.utils import event_to_json

def generate_vibration_values(
        sampling_rate: int,
        rpm: int,
        fault_level: float,
        noise_level: float,
        fault_type: str
) -> list[float]:
    duration = 1

    num_samples = int(sampling_rate * duration)
    time_axis = linspace(0, duration, num_samples)

    # Frequência base de rotação (Hz)
    base_freq = rpm / 1.0

    # Sinal base: senoidal na frequência de rotação
    vib_signal = 0.2 * sin(2 * pi * base_freq * time_axis)  # Amplitude baixa para normal

    # Adiciona ruído gaussiano para realismo
    vib_signal += random.normal(0, noise_level, num_samples)

    # Injeta falha progressiva (ex: bearing wear adiciona pico em bearing_freq)
    if fault_type == "bearing_wear":
        bearing_freq = 0.5 * base_freq  # Exemplo: Ball Pass Frequency Outer (BPFO)
        fault_signal = fault_level * sin(
            2 * pi * bearing_freq * time_axis)  # Amplitude cresce com fault_level
        vib_signal += fault_signal  # Adiciona ao sinal base, criando variação crescente

    # Simula uma tendência de aumento (como no exemplo de lista crescente)
    trend = linspace(0, fault_level * 0.5, num_samples)  # Aumento linear sutil
    vib_signal += trend

    return vib_signal.tolist()


class SensorSimulator:

    def __init__(self, sensor_id: str):
        self.sensor_id = sensor_id
        self.current_timestamp = datetime.now()
        self.current_rpm = INITIAL_RPM
        self.temperature = INITIAL_TEMPERATURE
        self.fault_level = FAULT_LEVEL
        self.fault_type = None
        self.fault_scale = FAULT_SCALE

        sqlite_client = PostgreSQLHandler()
        sqlite_client.init_db()

    def generate_output(self,
                        fault_increment: float,
                        fault_type: str = None,
                        fault_trend_type: str = "exponential",
                        ) -> SensorOutput:
        duration = 1.0
        self.current_timestamp = datetime.now()
        self.current_rpm = random.randint(max(1000, self.current_rpm - 50),
                                          min(3000, self.current_rpm + 50))
        if fault_type:
            self.fault_type = fault_type

            if fault_trend_type == "exponential":
                effective_increment = fault_increment * self.fault_scale * exp(self.fault_level)
            elif fault_trend_type == "quadratic":
                effective_increment = fault_increment * (self.fault_level ** 2 + 0.1)
            elif fault_trend_type == "random":
                effective_increment = random.uniform(fault_increment / 2, fault_increment * 1.5)
            else:
                effective_increment = fault_increment
            self.fault_level = min(1.0, self.fault_level + effective_increment)

            temp_increment = (sqrt(self.fault_level) * self.fault_scale) * 0.5
            self.temperature += temp_increment
            self.temperature = min(150.0, self.temperature)

        vib_sr = 2000  # Hz
        vib_values = generate_vibration_values(
            sampling_rate=vib_sr,
            rpm=self.current_rpm,
            fault_level=self.fault_level,
            noise_level=NOISE_LEVEL,
            fault_type=self.fault_type
        )
        vibration = WaveMeasure(sampling_rate=vib_sr, values=vib_values)

        curr_sr = 1000
        num_curr = int(curr_sr * duration)
        time_axis_curr = linspace(0, duration, num_curr)
        curr_signal = 5.0 + sin(2 * pi * 50 * time_axis_curr)
        curr_signal += random.normal(0, 0.2, num_curr)

        if self.fault_type == "overload":
            harmonic_freq = 150
            curr_signal += self.fault_level * sin(2 * pi * harmonic_freq * time_axis_curr)
        current = WaveMeasure(sampling_rate=curr_sr, values=curr_signal.tolist())

        temperature = round(self.temperature + random.uniform(1, -1), 1)

        return SensorOutput(
            event_id=str(uuid4()),
            sensor_id=self.sensor_id,
            timestamp=self.current_timestamp,
            rpm=self.current_rpm,
            vibration=vibration,
            current=current,
            temperature=temperature
        )

if __name__ == "__main__":
    s = SensorSimulator(sensor_id="edge-001")
    mqtt_client = MQTTClient()
    sql_client = PostgreSQLHandler()

    starttime = monotonic()
    while True:
        event = s.generate_output(fault_type="bearing_wear", fault_increment=0.1, fault_trend_type="exponential")
        mqtt_client.send(event_to_json(event))

        sql_client.insert_one("events", {
            "event_id": event["event_id"],
            "sensor_id": event["sensor_id"],
            "timestamp": event["timestamp"],
            "payload": f'{{"temperature": {event["temperature"]}}}'
        })

        sleep(1.0 - ((monotonic() - starttime) % 1.0))
