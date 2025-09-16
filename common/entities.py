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

@dataclass
class Engine:
    engine_id: str
    rated_speed: int
    rated_current: float
    max_temperature: float
