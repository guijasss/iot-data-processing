from json import loads
from time import time
from typing import List, Optional, cast
import numpy as np
from common.entities import SensorOutput, Engine, SensorOutputAggregation
from processing.alerts import detect_alerts


class EventProcessor:
    def __init__(self, engine: Engine, aggregation_interval: int):
        self.engine = engine
        self.aggregation_interval = aggregation_interval
        self.buffer: List[SensorOutput] = []
        self.previous_temp: Optional[float] = None
        self.last_aggregation_time = time()

    def process_event(self, payload: str) -> tuple[List[dict], Optional[SensorOutputAggregation]]:
        """
        Processa um evento e retorna alertas e agregação (se aplicável)

        Returns:
            tuple: (lista de alertas, agregação ou None)
        """
        output = loads(payload)

        # Detecta alertas
        alerts = self._detect_alerts(output)

        # Adiciona ao buffer
        self.buffer.append(output)

        # Verifica se deve agregar
        aggregation = None
        if self._should_aggregate():
            aggregation = self._aggregate_buffer()
            self.buffer.clear()
            self.last_aggregation_time = time()

        return alerts, aggregation

    def _detect_alerts(self, output: SensorOutput) -> List[dict]:
        """Detecta alertas baseados no output do sensor"""
        alerts = detect_alerts(output, self.engine, previous_temp=self.previous_temp)

        self.previous_temp = output["temperature"]
        return alerts

    def _should_aggregate(self) -> bool:
        """Verifica se é hora de agregar os dados"""
        return time() - self.last_aggregation_time >= self.aggregation_interval

    def _aggregate_buffer(self) -> SensorOutputAggregation:
        """Agrega os dados do buffer"""
        if not self.buffer:
            raise ValueError("Cannot aggregate empty buffer")

        aggregated = self._calculate_aggregations(self.buffer)
        return aggregated

    @staticmethod
    def _calculate_aggregations(buffer: List[SensorOutput]) -> SensorOutputAggregation:
        """Calcula as agregações dos dados no buffer"""
        # Dados básicos
        aggregated_data = {
            "sensor_id": buffer[0]["sensor_id"],
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

        # Calcula métricas de vibração e corrente
        vib_metrics = EventProcessor._calculate_vibration_metrics(buffer)
        curr_metrics = EventProcessor._calculate_current_metrics(buffer)

        aggregated_data["vibration"].update(vib_metrics)
        aggregated_data["current"].update(curr_metrics)

        return cast(SensorOutputAggregation, aggregated_data)

    @staticmethod
    def _calculate_vibration_metrics(buffer: List[SensorOutput]) -> dict:
        vib_rms_values = []
        bearing_peaks = []
        bearing_freqs = []

        for d in buffer:
            # RMS
            vib_values = np.array(d["vibration"]["values"])
            vib_rms = np.sqrt(np.mean(vib_values ** 2))
            vib_rms_values.append(vib_rms)

            base_freq = d["rpm"] / 60.0
            bearing_freq = 0.5 * base_freq
            bearing_freqs.append(bearing_freq)

            bearing_peak = np.max(np.abs(np.fft.fft(vib_values))) * 0.01
            bearing_peaks.append(bearing_peak)

        return {
            "avg_rms": np.mean(vib_rms_values),
            "max_rms": np.max(vib_rms_values),
            "avg_peak_bearing": np.mean(bearing_peaks),
            "avg_bearing_freq": np.mean(bearing_freqs)
        }

    @staticmethod
    def _calculate_current_metrics(buffer: List[SensorOutput]) -> dict:
        curr_rms_values = []
        harmonic_peaks = []

        for d in buffer:
            curr_values = np.array(d["current"]["values"])
            curr_rms = np.sqrt(np.mean(curr_values ** 2))
            curr_rms_values.append(curr_rms)

            harmonic_peak = np.max(np.abs(np.fft.fft(curr_values))) * 0.01
            harmonic_peaks.append(harmonic_peak)

        return {
            "avg_rms": np.mean(curr_rms_values),
            "max_rms": np.max(curr_rms_values),
            "avg_harmonic_peak": np.mean(harmonic_peaks)
        }
