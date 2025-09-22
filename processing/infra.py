from os import getenv

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# Config (de env vars)
INFLUX_URL = getenv('INFLUX_URL', 'http://influxdb:8086')
INFLUX_TOKEN = getenv('INFLUX_TOKEN', 'ObhIcDp2oFAIXr0YZJJH8bEYntIRaLBQ10bNuz0h-9CRs-HBW6VpRo0GZUh0m9fUNQmCd7Eb_ueIPysowj2jKA==')  # Gere no InfluxUI
INFLUX_ORG = getenv('INFLUX_ORG', 'yourorg')
INFLUX_BUCKET = getenv('INFLUX_BUCKET', 'sensor_data')

client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = client.write_api(write_options=SYNCHRONOUS)

def save_aggregated_to_influx(aggregated: dict):
    point = Point("aggregations") \
        .tag("device_id", aggregated["device_id"]) \
        .field("avg_rpm", aggregated["avg_rpm"]) \
        .field("avg_temperature", aggregated["avg_temperature"]) \
        .field("vib_avg_rms", aggregated["vibration"]["avg_rms"]) \
        .field("vib_avg_peak_bearing", aggregated["vibration"]["avg_peak_bearing"]) \
        .field("vib_avg_bearing_freq", aggregated["vibration"]["avg_bearing_freq"]) \
        .field("curr_avg_rms", aggregated["current"]["avg_rms"]) \
        .field("alerts_bearing_count", aggregated["alerts_summary"].get("bearing_wear", {}).get("count", 0)) \
        .time(aggregated["period_start"])  # Timestamp do período
    write_api.write(bucket=INFLUX_BUCKET, record=point)
    print("Agregado salvo no InfluxDB")
