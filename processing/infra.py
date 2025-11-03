from os import environ, getenv
from dotenv import load_dotenv

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

load_dotenv()
env = 'CLOUD'

def switch_environment_variables(old: str, new: str):
    environ[new] = getenv(old)
    del environ[old]

switch_environment_variables(f'{env}_INFLUX_URL', 'INFLUX_URL')
switch_environment_variables(f'{env}_INFLUX_TOKEN', 'INFLUX_TOKEN')
switch_environment_variables(f'{env}_INFLUX_ORG', 'INFLUX_ORG')
switch_environment_variables(f'{env}_INFLUX_BUCKET', 'INFLUX_BUCKET')

INFLUX_URL = getenv('INFLUX_URL', 'INFLUX_URL')
INFLUX_TOKEN = getenv('INFLUX_TOKEN', 'INFLUX_TOKEN')
INFLUX_ORG = getenv('INFLUX_ORG', 'INFLUX_ORG')
INFLUX_BUCKET = getenv('INFLUX_BUCKET', 'INFLUX_BUCKET')

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
