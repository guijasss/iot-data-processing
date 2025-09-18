from json import dumps
from datetime import datetime

from numpy import int64, float64


def event_to_json(event: dict) -> str:
    return dumps(
        event,
        default=lambda x: (
            x.isoformat() if isinstance(x, datetime) else
            x.item() if isinstance(x, (int64, float64)) else
            TypeError(f"Tipo {type(x)} não serializável para JSON.")
        )
    )
