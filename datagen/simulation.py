from numpy import exp, linspace, pi, random, sin, sqrt
from datetime import datetime, timedelta
from time import monotonic, sleep

from common.entities import SensorOutput, WaveMeasure
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
    def __init__(self, device_id: str = "edge-001", initial_rpm: int = 1800):
        self.device_id = device_id
        self.current_timestamp = datetime.now()
        self.current_rpm = initial_rpm
        self.temperature = 40.0  # Inicial normal
        self.fault_level = 0.0  # Nível de falha (0-1, aumenta com o tempo)
        self.fault_type = None  # Tipo de falha a simular (ex: "bearing_wear")
        self.fault_scale = 0.1  # Reduzido de 0.2 para escalonamento mais lento geral

    def generate_output(self,
                        fault_type: str = None,
                        fault_increment: float = 0.05,
                        fault_trend_type: str = "exponential",
                        noise_level: float = 0.1) -> SensorOutput:
        duration = 1.0
        # Atualiza estado para dependência temporal
        self.current_timestamp += timedelta(seconds=10)  # Simula intervalo entre medições
        self.current_rpm = random.randint(max(1000, self.current_rpm - 50),
                                          min(3000, self.current_rpm + 50))  # Varia ligeiramente
        if fault_type:
            self.fault_type = fault_type
            # Aumento com tendência (não apenas linear) — igual ao seu
            if fault_trend_type == "exponential":
                effective_increment = fault_increment * self.fault_scale * exp(self.fault_level)
            elif fault_trend_type == "quadratic":
                effective_increment = fault_increment * (self.fault_level ** 2 + 0.1)
            elif fault_trend_type == "random":
                effective_increment = random.uniform(fault_increment / 2, fault_increment * 1.5)
            else:  # Padrão: linear
                effective_increment = fault_increment
            self.fault_level = min(1.0, self.fault_level + effective_increment)

            # Ajuste na Temperatura: Mais realista e gradual
            # Incremento baseado em sqrt(fault_level) para crescimento lento inicial, acelerando moderadamente
            # Multiplicador reduzido (*0.5 em vez de *2), e cap máximo para evitar valores irreais
            temp_increment = (sqrt(self.fault_level) * self.fault_scale) * 0.5  # Ex: max ~0.1-0.5 por chamada
            self.temperature += temp_increment
            self.temperature = min(150.0, self.temperature)  # Cap em 150°C (realista para falha grave)

        # Gera vibração usando a função integrada (com parâmetros do estado)
        vib_sr = 2000  # Hz
        vib_values = generate_vibration_values(
            sampling_rate=vib_sr,
            rpm=self.current_rpm,
            fault_level=self.fault_level,
            noise_level=noise_level,
            fault_type=self.fault_type
        )
        vibration = WaveMeasure(sampling_rate=vib_sr, values=vib_values)

        # Gera corrente (mantido similar; pode adicionar função equivalente se quiser)
        curr_sr = 1000  # Hz
        num_curr = int(curr_sr * duration)
        time_axis_curr = linspace(0, duration, num_curr)
        curr_signal = 5.0 + sin(2 * pi * 50 * time_axis_curr)  # Sinal base (50Hz rede) + offset
        curr_signal += random.normal(0, 0.2, num_curr)  # Ruído
        # Injeta falha (ex: overload aumenta harmônicos)
        if self.fault_type == "overload":
            harmonic_freq = 150  # 3ª harmônica
            curr_signal += self.fault_level * sin(2 * pi * harmonic_freq * time_axis_curr)
        current = WaveMeasure(sampling_rate=curr_sr, values=curr_signal.tolist())

        # Temperatura final (com variação pequena e realista)
        temperature = round(self.temperature + random.uniform(-0.5, 0.5), 1)  # Reduzido range de ruído

        return SensorOutput(
            device_id=self.device_id,
            timestamp=self.current_timestamp,
            rpm=self.current_rpm,
            vibration=vibration,
            current=current,
            temperature=temperature
        )


# O loop while True permanece igual ao seu (gera, converte para JSON, envia via MQTT, sleep 1s)
s = SensorSimulator()
mqtt_client = MQTTClient()
starttime = monotonic()
while True:
    event = event_to_json(
        s.generate_output(fault_type="bearing_wear", fault_increment=0.1, fault_trend_type="exponential"))
    mqtt_client.send(event)
    sleep(1.0 - ((monotonic() - starttime) % 1.0))
