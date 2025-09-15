from json import dumps, loads, JSONDecodeError
import paho.mqtt.client as mqtt
from datetime import datetime

from processing.alerts import detect_alerts
from common.entities import SensorOutput, WaveMeasure

# Configurações MQTT (de env vars no compose)
MQTT_BROKER = "mqtt"
MQTT_PORT = 1883
MQTT_TOPIC = "readings"

# Variável global para armazenar histórico (ex: para tendências como previous_temp)
previous_temp = None  # Inicialize; atualize em cada mensagem

# Callback: Chamado automaticamente quando uma mensagem chega ao tópico subscrito
def on_message(client, userdata, msg):
    global previous_temp  # Use global se precisar de estado persistente

    try:
        # Passo 1: "Pega" os dados brutos da mensagem (payload é bytes, decode para string)
        payload = msg.payload.decode('utf-8')
        print(f"Mensagem recebida no tópico {msg.topic}: {payload[:100]}...")  # Log para debug (trunca se longo)

        # Passo 2: Parseia o JSON para um dicionário Python
        data = loads(
            payload)  # Agora 'data' é um dict com os campos (ex: data['rpm'], data['vibration']['values'])

        # Passo 3: (Opcional) Recria o objeto SensorOutput do seu modelo para facilitar processamento
        # Se não precisar, pule e use 'data' diretamente (ex: rms = np.sqrt(np.mean(np.array(data['vibration']['values'])**2)))
        output = SensorOutput(
            device_id=data["device_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            rpm=data["rpm"],
            vibration=WaveMeasure(
                sampling_rate=data["vibration"]["sampling_rate"],
                values=data["vibration"]["values"]
            ),
            current=WaveMeasure(
                sampling_rate=data["current"]["sampling_rate"],
                values=data["current"]["values"]
            ),
            temperature=data["temperature"]
        )

        # Passo 4: Processa os dados (ex: detecta alertas)
        alerts = detect_alerts(output, previous_temp=previous_temp)  # Use previous_temp para tendências

        # Passo 5: Faz algo com os resultados (ex: log, envie alertas de volta via MQTT, armazene em DB)
        if alerts:
            print(f"Alertas detectados: {alerts}")
            # Exemplo: Publique alertas em outro tópico (veja extensão abaixo)
            client.publish("alerts/processed", dumps(alerts))  # Envie de volta
        else:
            print("Nenhum alerta detectado.")

        # Atualiza estado (ex: para próxima mensagem)
        previous_temp = output["temperature"]  # Armazena para tendência no próximo dado

    except JSONDecodeError as e:
        print(f"Erro ao parsear JSON: {e}")
    except Exception as e:
        print(f"Erro ao processar dados: {e}")


# Inicializa e configura o cliente MQTT
client = mqtt.Client()
client.on_message = on_message  # Associa o callback
client.connect(MQTT_BROKER, MQTT_PORT, 60)  # Conecta ao broker
client.subscribe(MQTT_TOPIC)  # Subscreve ao tópico onde datagen publica
print(f"Processing started: Subscribed to {MQTT_TOPIC} on {MQTT_BROKER}:{MQTT_PORT}")
client.loop_forever()  # Mantém o subscriber rodando indefinidamente
