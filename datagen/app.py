from numpy import exp, linspace, pi, random, sin, sqrt
from datetime import datetime
from time import monotonic, sleep
from uuid import uuid4
from json import dumps

from common.entities import SensorOutput, WaveMeasure
from common.properties import *
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

        vib_values = generate_vibration_values(
            sampling_rate=VIBRATION_SAMPLING_RATE,
            rpm=self.current_rpm,
            fault_level=self.fault_level,
            noise_level=NOISE_LEVEL,
            fault_type=self.fault_type
        )
        vibration = WaveMeasure(sampling_rate=VIBRATION_SAMPLING_RATE, values=vib_values)

        num_curr = int(CURRENT_SAMPLING_RATE * duration)
        time_axis_curr = linspace(0, duration, num_curr)
        curr_signal = 5.0 + sin(2 * pi * 50 * time_axis_curr)
        curr_signal += random.normal(0, 0.2, num_curr)

        if self.fault_type == "overload":
            harmonic_freq = 150
            curr_signal += self.fault_level * sin(2 * pi * harmonic_freq * time_axis_curr)
        current = WaveMeasure(sampling_rate=CURRENT_SAMPLING_RATE, values=curr_signal.tolist())

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
    # 1. Crie X instâncias de simuladores (uma para cada motor)
    simulators = []
    for i in range(NUM_MOTORS):
        simulators.append(SensorSimulator(sensor_id=f"edge-{i + 1:03d}"))

    mqtt_client = MQTTClient()

    # 2. Calcule o novo intervalo
    # Se NUM_MOTORS = 3, queremos 3 eventos/s
    # O intervalo entre eventos deve ser 1.0 / 3 = 0.333s
    try:
        INTERVAL = 1.0 / NUM_MOTORS
    except ZeroDivisionError:
        print("NUM_MOTORS não pode ser zero.")
        exit(1)

    starttime = monotonic()
    event_counter = 0

    print(f"Iniciando simulação com {NUM_MOTORS} motores.")
    print(f"Taxa alvo: {NUM_MOTORS} eventos/segundo (Intervalo: {INTERVAL:.4f}s)")

    while True:
        # 3. Determine qual motor deve enviar o evento agora (rodízio)
        # event_counter % NUM_MOTORS vai ciclar: 0, 1, 2, 0, 1, 2, ...
        motor_index = event_counter % NUM_MOTORS
        sensor = simulators[motor_index]

        # 4. Gere e envie o evento para ESTE motor
        # (A lógica da falha pode ser a mesma ou diferente por motor)
        event = sensor.generate_output(
            fault_type="bearing_wear",
            fault_increment=0.1,
            fault_trend_type="exponential"
        )

        with open(f"/app/logs/events_{NUM_MOTORS}_engines", "a") as file:
            file.write(event_to_json({
                "timestamp": event["timestamp"],
                "event_id": event["event_id"],
                "sensor_id": event["sensor_id"],
                "temperature": event["temperature"]
            }) + '\n')

        mqtt_client.send(event_to_json(event))

        event_counter += 1

        # 5. Use a sua lógica de sleep, mas com o novo INTERVAL
        # Isso garante que o loop tente rodar a cada 0.333s (para 3 motores)
        sleep(INTERVAL - ((monotonic() - starttime) % INTERVAL))


# sql_client = PostgreSQLHandler()
#
# sql_client.insert_one("events", {
#     "event_id": event["event_id"],
#     "sensor_id": event["sensor_id"],
#     "timestamp": event["timestamp"],
#     "payload": f'{{"temperature": {event["temperature"]}}}'
# })
