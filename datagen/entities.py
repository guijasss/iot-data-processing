from datetime import datetime
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
