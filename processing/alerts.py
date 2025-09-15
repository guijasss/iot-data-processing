from numpy import abs, array, max as npmax, mean, sqrt
from scipy.fft import fft, fftfreq

from common.entities import SensorOutput


def detect_bearing_wear(output: SensorOutput) -> dict | None:
    """Detecta desgaste de rolamento via vibração (RMS e pico em bearing_freq via FFT)."""
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

    if rms_vib > 0.3 and peak_bearing > 10:  # Thresholds exemplo (ajuste com dados reais)
        severity = "high" if rms_vib > 0.8 else "medium"
        return {
            "type": "bearing_wear",
            "severity": severity,
            "details": f"RMS={rms_vib:.2f}g, Pico={peak_bearing:.2f}@{bearing_freq:.1f}Hz"
        }
    return None


def detect_overload(output: SensorOutput) -> dict | None:
    """Detecta sobrecarga elétrica via corrente (RMS e harmônicos via FFT)."""
    curr_values = array(output["current"]["values"])
    curr_sr = output["current"]["sampling_rate"]
    rms_curr = sqrt(mean(curr_values ** 2))  # RMS para intensidade

    # FFT para harmônicos
    fft_curr = fft(curr_values)
    freqs_curr = fftfreq(len(curr_values), 1 / curr_sr)
    magnitudes_curr = abs(fft_curr)
    fundamental_freq = 50  # Rede (ajuste para 60Hz se necessário)
    idx_fund = (freqs_curr >= fundamental_freq - 5) & (freqs_curr <= fundamental_freq + 5)
    peak_fund = max(magnitudes_curr[idx_fund]) if any(idx_fund) else 0
    harmonic_freq = 150  # 3ª harmônica
    idx_harm = (freqs_curr >= harmonic_freq - 5) & (freqs_curr <= harmonic_freq + 5)
    peak_harm = max(magnitudes_curr[idx_harm]) if any(idx_harm) else 0

    if rms_curr > 6 and (peak_harm / peak_fund > 0.1 if peak_fund > 0 else False):
        severity = "high" if rms_curr > 8 else "medium"
        return {
            "type": "overload",
            "severity": severity,
            "details": f"RMS={rms_curr:.2f}A, Harmônico={(peak_harm / peak_fund) * 100:.1f}%"
        }
    return None


def detect_overheating(output: SensorOutput, previous_temp: float = None) -> dict | None:
    """Detecta superaquecimento via temperatura (threshold e tendência)."""
    temp = output["temperature"]
    alert = None

    # Threshold simples
    if temp > 70:
        severity = "high" if temp > 80 else "medium"
        alert = {
            "type": "overheating",
            "severity": severity,
            "details": f"Temperatura={temp:.1f}°C"
        }

    # Tendência (opcional, requer temp anterior)
    if previous_temp is not None and (temp - previous_temp) > 5:
        trend_alert = {
            "type": "overheating_trend",
            "severity": "warning",
            "details": f"Aumento={temp - previous_temp:.1f}°C"
        }
        # Mescla se já houver alerta
        if alert:
            alert["details"] += f"; {trend_alert['details']}"
            alert["severity"] = max(alert["severity"], trend_alert["severity"],
                                    key=lambda s: ["warning", "medium", "high"].index(s))
        else:
            alert = trend_alert

    return alert


# Função wrapper opcional para detectar todos de uma vez
def detect_alerts(output: SensorOutput, previous_temp: float = None) -> list[dict]:
    alerts = []
    bearing_alert = detect_bearing_wear(output)
    if bearing_alert:
        alerts.append(bearing_alert)

    overload_alert = detect_overload(output)
    if overload_alert:
        alerts.append(overload_alert)

    overheating_alert = detect_overheating(output, previous_temp)
    if overheating_alert:
        alerts.append(overheating_alert)

    return alerts
