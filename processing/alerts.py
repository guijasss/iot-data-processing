from numpy import abs, array, max as npmax, mean, sqrt
from scipy.fft import fft, fftfreq
from datetime import datetime

from common.entities import Engine, SensorOutput


def detect_bearing_wear(output: SensorOutput, engine: Engine) -> dict | None:
    """Detecta desgaste de rolamento via vibração (RMS e pico em bearing_freq via FFT). Thresholds baseados em rated_speed."""
    vib_values = array(output["vibration"]["values"])
    vib_sr = output["vibration"]["sampling_rate"]
    rms_vib = sqrt(mean(vib_values ** 2))  # RMS para intensidade geral

    # FFT para pico na frequência de defeito
    fft_vib = fft(vib_values)
    freqs = fftfreq(len(vib_values), 1 / vib_sr)
    magnitudes = abs(fft_vib)
    base_freq = output["rpm"] / 60.0
    bearing_freq = 0.5 * base_freq  # Exemplo: BPFO

    idx = (freqs >= bearing_freq - 5) & (freqs <= bearing_freq + 5)
    peak_bearing = npmax(magnitudes[idx]) if any(idx) else 0

    # Thresholds dinâmicos: RMS baseado em rated_speed (ex: mais tolerância em alta velocidade)
    rms_threshold = 0.2 + (0.3 * (engine.rated_speed / 1800.0))  # Ex: 0.2g baixa speed, 0.5g alta
    peak_threshold = 10 * (engine.rated_speed / 1800.0)  # Escala com speed

    if rms_vib > rms_threshold and peak_bearing > peak_threshold:
        severity = "high" if rms_vib > rms_threshold * 1.5 else "medium"
        print("ALERTA")
        return {
            "event_id": output["event_id"],
            "sensor_id": output["sensor_id"],
            "timestamp": datetime.now(),
            "type": "bearing_wear",
            "severity": severity,
            "details": f"RMS={rms_vib:.2f}g (threshold={rms_threshold:.2f}), Pico={peak_bearing:.2f}@{bearing_freq:.1f}Hz (threshold={peak_threshold:.2f})"
        }
    return None


def detect_overload(output: SensorOutput, engine: Engine) -> dict | None:
    """Detecta sobrecarga elétrica via corrente (RMS e harmônicos via FFT). Thresholds baseados em rated_current."""
    curr_values = array(output["current"]["values"])
    curr_sr = output["current"]["sampling_rate"]
    rms_curr = sqrt(mean(curr_values ** 2))  # RMS para intensidade

    # FFT para harmônicos
    fft_curr = fft(curr_values)
    freqs_curr = fftfreq(len(curr_values), 1 / curr_sr)
    magnitudes_curr = abs(fft_curr)
    fundamental_freq = 50  # Rede (ajuste para 60Hz se necessário)
    idx_fund = (freqs_curr >= fundamental_freq - 5) & (freqs_curr <= fundamental_freq + 5)
    peak_fund = npmax(magnitudes_curr[idx_fund]) if any(idx_fund) else 0
    harmonic_freq = 150  # 3ª harmônica
    idx_harm = (freqs_curr >= harmonic_freq - 5) & (freqs_curr <= harmonic_freq + 5)
    peak_harm = npmax(magnitudes_curr[idx_harm]) if any(idx_harm) else 0

    # Thresholds dinâmicos baseados em rated_current
    rms_medium_threshold = engine.rated_current * 1.2  # Ex: 6.0A se rated=5.0A
    rms_high_threshold = engine.rated_current * 1.5  # Ex: 7.5A
    harmonic_threshold = 0.1  # Mantido 10%, mas escalável se quiser (ex: + fault_level)

    if rms_curr > rms_medium_threshold and (peak_harm / peak_fund > harmonic_threshold if peak_fund > 0 else False):
        severity = "high" if rms_curr > rms_high_threshold else "medium"
        return {
            "event_id": output["event_id"],
            "sensor_id": output["sensor_id"],
            "timestamp": datetime.now(),
            "type": "overload",
            "severity": severity,
            "details": f"RMS={rms_curr:.2f}A (threshold medium={rms_medium_threshold:.2f}, high={rms_high_threshold:.2f}), Harmônico={(peak_harm / peak_fund) * 100:.1f}%"
        }
    return None


def detect_overheating(output: SensorOutput, engine: Engine) -> dict | None:
    temperature = output["temperature"]
    alert = None

    if temperature > engine.max_temperature:
        alert = {
            "event_id": output["event_id"],
            "sensor_id": output["sensor_id"],
            "timestamp": datetime.now(),
            "type": "overheating",
            "severity": "high",
            "details": f"Temperatura: {temperature}"
        }

    return alert


def detect_alerts(output: SensorOutput, engine: Engine) -> list[dict]:
    alerts = []
    bearing_alert = detect_bearing_wear(output, engine)
    if bearing_alert:
        alerts.append(bearing_alert)
    overload_alert = detect_overload(output, engine)
    if overload_alert:
        alerts.append(overload_alert)
    overheating_alert = detect_overheating(output, engine)
    if overheating_alert:
        alerts.append(overheating_alert)
    return alerts
