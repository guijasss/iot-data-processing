from json import dumps

from common.entities import SensorOutput


def event_to_json(event: SensorOutput) -> str:
    return dumps(event, default=lambda x: x.isoformat())
