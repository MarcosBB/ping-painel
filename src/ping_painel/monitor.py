"""Coleta: dispara um ping por segundo, guarda os resultados e apita."""
import re
import subprocess
import threading
import time
from collections import deque

from .config import LIMITE_LENTO, SOM, TIMEOUT_MS, Config

RE_TEMPO = re.compile(r"time=([0-9.]+)")


class Estado:
    """Tudo o que foi medido até agora (acesso protegido por lock)."""

    def __init__(self, config: Config):
        self.config = config
        self.lock = threading.Lock()
        self.inicio = time.time()
        self.amostras = []            # (timestamp, ms ou None)
        self.recentes = deque(maxlen=400)
        self.ultima_perda = None
        self.seq_perdas = 0           # perdas seguidas agora
        self.maior_seq_perdas = 0
        self.lentos = 0

    def registra(self, ts, ms):
        with self.lock:
            self.amostras.append((ts, ms))
            self.recentes.append(ms)
            if ms is None:
                self.ultima_perda = ts
                self.seq_perdas += 1
                self.maior_seq_perdas = max(self.maior_seq_perdas, self.seq_perdas)
            else:
                self.seq_perdas = 0
                if ms > LIMITE_LENTO:
                    self.lentos += 1

    def copia_ordenada(self):
        with self.lock:
            return sorted(self.amostras)


def beep():
    try:
        subprocess.Popen(["afplay", SOM], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except Exception:
        print("\a", end="", flush=True)  # sem afplay: sino do terminal


def um_ping(estado: Estado, ts: float):
    try:
        out = subprocess.run(
            ["ping", "-c", "1", "-W", str(TIMEOUT_MS), estado.config.alvo],
            capture_output=True, text=True, timeout=TIMEOUT_MS / 1000 + 2,
        ).stdout
        m = RE_TEMPO.search(out)
        ms = float(m.group(1)) if m else None
    except Exception:
        ms = None
    estado.registra(ts, ms)
    if not estado.config.mudo and (ms is None or ms > LIMITE_LENTO):
        beep()


def agendador(estado: Estado, parar: threading.Event):
    """Dispara um ping por segundo, cada um na sua thread, para que um
    timeout de 3 s não atrase os próximos."""
    prox = time.time()
    while not parar.is_set():
        threading.Thread(target=um_ping, args=(estado, prox), daemon=True).start()
        prox += 1
        parar.wait(max(0, prox - time.time()))


def inicia(estado: Estado) -> threading.Event:
    parar = threading.Event()
    threading.Thread(target=agendador, args=(estado, parar), daemon=True).start()
    return parar
