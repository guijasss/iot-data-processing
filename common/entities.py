from datetime import datetime
from dataclasses import dataclass
from typing import List, TypedDict


class WaveMeasure(TypedDict):
    sampling_rate: int
    values: List[float]

class SensorOutput(TypedDict):
    device_id: str
    timestamp: datetime
    rpm: int
    vibration: WaveMeasure
    current: WaveMeasure
    temperature: float

class SensorOutputAggregation(TypedDict):
    device_id: str
    period_start: str
    period_end: str
    event_count: int
    avg_rpm: float
    min_rpm: int
    max_rpm: int
    avg_temperature: float
    min_temperature: float
    max_temperature: float
    std_temperature: float
    vibration: TypedDict("Vibration", {
        "avg_rms": float,
        "max_rms": float,
        "avg_peak_bearing": float,
        "avg_bearing_freq": float,
    })
    current: TypedDict("Current", {
        "avg_rms": float,
        "max_rms": float,
        "avg_harmonic_peak": float,
    })

@dataclass
class Engine:
    engine_id: str
    rated_speed: int
    rated_current: float
    max_temperature: float
