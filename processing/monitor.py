import sys
import time
import threading

# --- Constantes da "biblioteca" ---
BOARD = 10
OUT = 11
HIGH = 1
LOW = 0

# --- Estado global (Thread-safe) ---
_pins = {}  # Guarda o estado de cada pino (ex: {11: {'state': LOW}})
_lock = threading.Lock()  # Protege o acesso ao dicionário _pins
_stop_event = threading.Event()  # Sinaliza para o renderer parar
_renderer_thread = None


def setmode(mode):
    """Simula a definição do modo dos pinos."""
    print(f"[MOCK GPIO] Modo dos pinos: BOARD")


def setup(pin, mode):
    """Simula a configuração de um pino como saída."""
    global _pins
    with _lock:
        if mode == OUT:
            _pins[pin] = {'state': LOW}  # Inicializa o pino como desligado
            print(f"[MOCK GPIO] Pino {pin} configurado como: SAÍDA (OUT)")


def output(pin, state):
    """Simula o envio de um sinal (ligar/desligar)."""
    global _pins
    with _lock:
        if pin not in _pins:
            print(f"[MOCK GPIO] ERRO: Pino {pin} não foi configurado (chame setup() primeiro)")
            return

        if state == HIGH:
            _pins[pin]['state'] = HIGH
        elif state == LOW:
            _pins[pin]['state'] = LOW


def _render_loop():
    """(THREAD SEPARADA) Loop que desenha o status dos pinos no terminal."""
    while not _stop_event.is_set():
        status_line = "STATUS DOS ALERTAS: |"
        with _lock:
            if not _pins:
                status_line += " (Nenhum pino configurado) "

            for pin_num, pin_data in _pins.items():
                if pin_data['state'] == HIGH:
                    # (●) Símbolo de círculo cheio para LIGADO (vermelho)
                    status_line += f" PINO {pin_num}: \033[91m(●) ALERTA!\033[0m |"
                else:
                    # (○) Símbolo de círculo vazio para DESLIGADO (verde)
                    status_line += f" PINO {pin_num}: \033[92m(○) OK\033[0m      |"

        # \r move o cursor para o início da linha (sem pular)
        sys.stdout.write(status_line + "   \r")
        sys.stdout.flush()

        time.sleep(0.5)  # Taxa de atualização da "tela"


def start_renderer():
    """Inicia o loop de renderização do terminal em uma thread separada."""
    global _renderer_thread
    if _renderer_thread is None:
        print("--- Iniciando Simulação GPIO (Terminal) ---")
        _renderer_thread = threading.Thread(target=_render_loop, daemon=True)
        _renderer_thread.start()


def cleanup():
    """Simula a limpeza dos pinos e para o renderer."""
    _stop_event.set()
    if _renderer_thread:
        _renderer_thread.join(timeout=1.0)  # Espera o thread terminar
    print("\n[MOCK GPIO] Limpeza de pinos executada.")