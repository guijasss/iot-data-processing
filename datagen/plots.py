import matplotlib

import matplotlib.pyplot as plt
import numpy as np
import os

# Pasta para salvar plots (crie no container ou mount via compose)
PLOT_DIR = '/app/plots'
os.makedirs(PLOT_DIR, exist_ok=True)


# Função para plotar um sinal (ex: vibração ou corrente) de uma geração
def plot_signal(values: list[float], sampling_rate: int, title: str, ylabel: str, filename: str):
    duration = len(values) / sampling_rate  # Calcula duração em segundos
    time_axis = np.linspace(0, duration, len(values))  # Eixo de tempo

    plt.figure(figsize=(10, 4))
    plt.plot(time_axis, values, label='Sinal', color='blue')
    plt.title(title)
    plt.xlabel('Tempo (s)')
    plt.ylabel(ylabel)
    plt.grid(True)
    plt.legend()
    plt.savefig(os.path.join(PLOT_DIR, filename))
    plt.close()  # Fecha para liberar memória


# Função para plotar evolução temporal (ex: temperatura, RMS ao longo de iterações)
# Use uma lista para armazenar histórico (ex: adicione no loop)
def plot_time_series(history: dict, filename: str):
    iterations = list(range(len(history['temperature'])))  # Eixo x: número de gerações

    plt.figure(figsize=(10, 6))
    plt.plot(iterations, history['temperature'], label='Temperatura (°C)', color='red')
    plt.plot(iterations, history['vib_rms'], label='RMS Vibração (g)', color='blue')
    plt.plot(iterations, history['curr_rms'], label='RMS Corrente (A)', color='green')
    plt.plot(iterations, history['fault_level'], label='Fault Level', color='black', linestyle='--')
    plt.title('Evolução dos Sinais ao Longo das Gerações')
    plt.xlabel('Geração (Iteração)')
    plt.ylabel('Valor')
    plt.grid(True)
    plt.legend()
    plt.savefig(os.path.join(PLOT_DIR, filename))
    plt.close()


# No seu loop while True, adicione lógica para plotar
# Exemplo: Armazene histórico e plote a cada 10 iterações
history = {'temperature': [], 'vib_rms': [], 'curr_rms': [], 'fault_level': []}  # Inicialize fora do loop
iteration = 0

while True:
    event_obj = s.generate_output(fault_type="bearing_wear", fault_increment=0.05,
                                  fault_trend_type="exponential")  # Gere o objeto antes de JSON
    event = event_to_json(event_obj)
    mqtt_client.send(event)

    # Calcula RMS para histórico (exemplo de métricas resumidas)
    vib_rms = np.sqrt(np.mean(np.array(event_obj.vibration.values) ** 2))
    curr_rms = np.sqrt(np.mean(np.array(event_obj.current.values) ** 2))

    # Armazena no histórico
    history['temperature'].append(event_obj.temperature)
    history['vib_rms'].append(vib_rms)
    history['curr_rms'].append(curr_rms)
    history['fault_level'].append(s.fault_level)

    # Plota sinal individual (ex: vibração da geração atual)
    if iteration % 5 == 0:  # A cada 5 iterações para não sobrecarregar
        plot_signal(
            values=event_obj.vibration.values[:200],  # Subset para plot mais rápido (ex: primeiros 200 pontos)
            sampling_rate=event_obj.vibration.sampling_rate,
            title=f'Vibração (Iteração {iteration}, Fault Level: {s.fault_level:.2f})',
            ylabel='Vibração (g)',
            filename=f'vibration_{iteration}.png'
        )
        plot_signal(
            values=event_obj.current.values[:200],
            sampling_rate=event_obj.current.sampling_rate,
            title=f'Corrente (Iteração {iteration}, Fault Level: {s.fault_level:.2f})',
            ylabel='Corrente (A)',
            filename=f'current_{iteration}.png'
        )

    # Plota série temporal (evolução)
    if iteration % 10 == 0 and iteration > 0:  # A cada 10, após algumas iterações
        plot_time_series(history, filename=f'time_series_{iteration}.png')

    iteration += 1
    sleep(1.0 - ((monotonic() - starttime) % 1.0))