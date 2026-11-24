#!/usr/bin/env -S uv run --quiet --script
# /// script
# requires-python = ">=3.9"
# dependencies = ["rich>=13", "reportlab>=4", "matplotlib>=3.7"]
# ///
"""
Painel de ping ao vivo (atualiza a cada 1 s).

Uso:  ~/Desktop/pingpainel.sh [ip] [--mudo]     (padrão: 8.8.8.8)
      Ctrl+C para sair (mostra um resumo final).
      Apita (Sosumi) a cada perda de pacote ou ping > 1000 ms;
      --mudo desliga o som.
      Ao sair, pergunta se quer gerar um relatório PDF
      (salvo na pasta relatorios/ do projeto).

Usa o mesmo critério do pingbeep.sh: sem resposta em 3 s = perda;
acima de 1000 ms = lento.
"""
import io
import math
import os
import re
import statistics
import subprocess
import sys
import threading
import time
from collections import deque
from datetime import datetime, timedelta

from rich import box
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table
from rich.text import Text

_args = [a for a in sys.argv[1:] if not a.startswith("-")]
IP = _args[0] if _args else "8.8.8.8"
MUDO = "--mudo" in sys.argv
SOM = "/System/Library/Sounds/Sosumi.aiff"
TIMEOUT_MS = 3000
LIMITE_LENTO = 1000  # ms
JANELA = 60          # segundos para as estatísticas "recentes"

RE_TEMPO = re.compile(r"time=([0-9.]+)")
BLOCOS = "▁▂▃▄▅▆▇█"


class Estado:
    def __init__(self):
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


def um_ping(estado, ts):
    try:
        out = subprocess.run(
            ["ping", "-c", "1", "-W", str(TIMEOUT_MS), IP],
            capture_output=True, text=True, timeout=TIMEOUT_MS / 1000 + 2,
        ).stdout
        m = RE_TEMPO.search(out)
        ms = float(m.group(1)) if m else None
    except Exception:
        ms = None
    estado.registra(ts, ms)
    if not MUDO and (ms is None or ms > LIMITE_LENTO):
        beep()


def beep():
    try:
        subprocess.Popen(["afplay", SOM], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except Exception:
        print("\a", end="", flush=True)  # fallback: sino do terminal


def agendador(estado, parar):
    # Dispara um ping por segundo, cada um na sua thread, para que um
    # timeout de 3 s não atrase os próximos.
    prox = time.time()
    while not parar.is_set():
        threading.Thread(target=um_ping, args=(estado, prox), daemon=True).start()
        prox += 1
        parar.wait(max(0, prox - time.time()))


# ---------- estatísticas ----------

def calc(lista):
    oks = [x for x in lista if x is not None]
    total = len(lista)
    perdas = total - len(oks)
    r = {"total": total, "perdas": perdas,
         "perda_pct": (perdas / total * 100) if total else 0.0}
    if oks:
        ordenado = sorted(oks, reverse=True)
        n1 = max(1, math.ceil(len(oks) * 0.01))
        r["media"] = statistics.fmean(oks)
        r["low1"] = statistics.fmean(ordenado[:n1])   # média do pior 1 %
        r["min"] = ordenado[-1]
        r["max"] = ordenado[0]
        r["mediana"] = statistics.median(oks)
        r["jitter"] = (statistics.fmean(abs(a - b) for a, b in zip(oks, oks[1:]))
                       if len(oks) > 1 else 0.0)
    return r


def cor_ms(ms):
    if ms is None:
        return "bold red"
    if ms < 50:
        return "green"
    if ms < 100:
        return "yellow"
    if ms < LIMITE_LENTO:
        return "dark_orange"
    return "bold red"


def cor_perda(pct):
    if pct == 0:
        return "green"
    if pct < 1:
        return "yellow"
    if pct < 5:
        return "dark_orange"
    return "bold red"


def fmt_ms(v):
    return "—" if v is None else f"{v:.1f} ms"


def fmt_dur(seg):
    return str(timedelta(seconds=int(seg)))


def grafico(recentes, largura):
    dados = list(recentes)[-largura:]
    oks = [x for x in dados if x is not None]
    if not dados:
        return Text("aguardando respostas…", style="dim")
    lo, hi = (min(oks), max(oks)) if oks else (0, 1)
    faixa = max(hi - lo, 1e-9)
    t = Text()
    for x in dados:
        if x is None:
            t.append("✕", style="bold red")
        else:
            i = int((x - lo) / faixa * (len(BLOCOS) - 1)) if hi > lo else 0
            t.append(BLOCOS[i], style=cor_ms(x))
    return t


def linha(tabela, nome, geral, recente, estilo_g="", estilo_r=""):
    tabela.add_row(nome, Text(geral, style=estilo_g), Text(recente, style=estilo_r))


def render(estado, console):
    with estado.lock:
        amostras = list(estado.amostras)
        recentes = list(estado.recentes)
        ultima_perda = estado.ultima_perda
        seq = estado.seq_perdas
        maior_seq = estado.maior_seq_perdas
        lentos = estado.lentos

    agora = time.time()
    g = calc([ms for _, ms in amostras])
    j = calc([ms for ts, ms in amostras if ts >= agora - JANELA])
    atual = amostras[-1][1] if amostras else None

    # Cabeçalho: ping atual em destaque
    if not amostras:
        status = Text("iniciando…", style="dim")
    elif seq:
        status = Text(f"SEM RESPOSTA (há {seq} s)", style="bold white on red")
    else:
        status = Text(f"{atual:.1f} ms", style=cor_ms(atual) + " bold")
    topo = Table.grid(expand=True)
    topo.add_column(justify="left")
    topo.add_column(justify="right")
    topo.add_row(Text.assemble(("Alvo: ", "dim"), (IP, "bold cyan"),
                               ("   Ping atual: ", "dim"), status),
                 Text(("🔇 mudo  ·  " if MUDO else "🔔 som ligado  ·  ") +
                      f"rodando há {fmt_dur(agora - estado.inicio)}  ·  "
                      f"{datetime.now():%H:%M:%S}", style="dim"))

    # Tabela principal
    t = Table(box=box.SIMPLE_HEAVY, expand=True, header_style="bold")
    t.add_column("Métrica")
    t.add_column("Geral", justify="right")
    t.add_column(f"Últimos {JANELA}s", justify="right")

    linha(t, "Média", fmt_ms(g.get("media")), fmt_ms(j.get("media")),
          cor_ms(g.get("media")), cor_ms(j.get("media")))
    linha(t, "1% low (pior 1%)", fmt_ms(g.get("low1")), fmt_ms(j.get("low1")),
          cor_ms(g.get("low1")), cor_ms(j.get("low1")))
    linha(t, "Perda de pacote", f"{g['perda_pct']:.2f} %", f"{j['perda_pct']:.2f} %",
          cor_perda(g["perda_pct"]), cor_perda(j["perda_pct"]))
    linha(t, "Pacotes perdidos", f"{g['perdas']} / {g['total']}",
          f"{j['perdas']} / {j['total']}",
          "bold red" if g["perdas"] else "green",
          "bold red" if j["perdas"] else "green")
    t.add_section()
    linha(t, "Mediana", fmt_ms(g.get("mediana")), fmt_ms(j.get("mediana")), "dim", "dim")
    linha(t, "Mín / Máx",
          f"{fmt_ms(g.get('min'))} / {fmt_ms(g.get('max'))}",
          f"{fmt_ms(j.get('min'))} / {fmt_ms(j.get('max'))}", "dim", "dim")
    linha(t, "Jitter", fmt_ms(g.get("jitter")), fmt_ms(j.get("jitter")), "dim", "dim")

    # Rodapé com eventos
    if ultima_perda:
        desde = f"há {fmt_dur(agora - ultima_perda)} ({datetime.fromtimestamp(ultima_perda):%H:%M:%S})"
    else:
        desde = "nenhuma ainda"
    rodape = Text.assemble(
        ("Última perda: ", "dim"), (desde, "red" if ultima_perda else "green"),
        ("   Maior sequência de perdas: ", "dim"), (str(maior_seq), "red" if maior_seq else "green"),
        ("   Lentos (>1000 ms): ", "dim"), (str(lentos), "dark_orange" if lentos else "green"),
    )

    largura = max(10, console.width - 6)
    corpo = Group(topo, t, Text("Histórico (✕ = perda):", style="dim"),
                  grafico(recentes, largura), Text(""), rodape)
    return Panel(corpo, title="[bold]📡 Painel de Ping[/]",
                 subtitle="[dim]Ctrl+C para sair[/]", border_style="cyan")


# ---------- relatório PDF ----------

def quedas(amostras):
    """Agrupa perdas seguidas em quedas: [(inicio_ts, fim_ts, pacotes)]."""
    res, atual = [], None
    for ts, ms in amostras:
        if ms is None:
            if atual is None:
                atual = [ts, ts, 0]
            atual[1] = ts
            atual[2] += 1
        elif atual is not None:
            res.append(tuple(atual))
            atual = None
    if atual is not None:
        res.append(tuple(atual))
    return res


def gera_pdf(estado, fim):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (Image, Paragraph, SimpleDocTemplate,
                                    Spacer, Table as PTable, TableStyle)

    amostras = sorted(estado.amostras)
    g = calc([ms for _, ms in amostras])
    lista_quedas = quedas(amostras)
    inicio = estado.inicio

    pasta = os.path.join(os.path.dirname(os.path.realpath(__file__)), "relatorios")
    os.makedirs(pasta, exist_ok=True)
    nome = f"ping-{IP.replace(':', '_')}-{datetime.fromtimestamp(inicio):%Y%m%d-%H%M%S}.pdf"
    caminho = os.path.join(pasta, nome)

    def fig_png(fig):
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf

    # Gráfico 1: ping ao longo do tempo + perdas
    oks = [(datetime.fromtimestamp(ts), ms) for ts, ms in amostras if ms is not None]
    perdas_t = [datetime.fromtimestamp(ts) for ts, ms in amostras if ms is None]
    fig, ax = plt.subplots(figsize=(10, 3.6))
    if oks:
        xs, ys = zip(*oks)
        ax.plot(xs, ys, lw=0.8, color="#1f77b4", label="Ping (ms)")
        if "media" in g:
            ax.axhline(g["media"], color="#2ca02c", ls="--", lw=1,
                       label=f"Média {g['media']:.1f} ms")
            ax.axhline(g["low1"], color="#ff7f0e", ls=":", lw=1.2,
                       label=f"1% low {g['low1']:.1f} ms")
    for t in perdas_t:
        ax.axvline(t, color="red", alpha=0.35, lw=1)
    if perdas_t:
        ax.plot([], [], color="red", alpha=0.5, label=f"Perda ({len(perdas_t)})")
    ax.set_ylabel("ms")
    ax.set_title("Ping ao longo do tempo")
    ax.grid(alpha=0.3)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    fig.autofmt_xdate()
    ax.legend(loc="upper right", fontsize=8)
    img_tempo = fig_png(fig)

    # Gráfico 2: distribuição
    img_hist = None
    if oks:
        fig, ax = plt.subplots(figsize=(10, 2.8))
        ax.hist([y for _, y in oks], bins=min(60, max(10, len(oks) // 5)),
                color="#1f77b4", alpha=0.8)
        ax.set_xlabel("ms")
        ax.set_ylabel("pacotes")
        ax.set_title("Distribuição do ping")
        ax.grid(alpha=0.3)
        img_hist = fig_png(fig)

    est = getSampleStyleSheet()
    doc = SimpleDocTemplate(caminho, pagesize=A4, leftMargin=1.6 * cm,
                            rightMargin=1.6 * cm, topMargin=1.5 * cm,
                            bottomMargin=1.5 * cm, title=f"Relatório de ping {IP}")
    larg = A4[0] - 3.2 * cm
    el = [
        Paragraph(f"Relatório de ping: {IP}", est["Title"]),
        Paragraph(f"{datetime.fromtimestamp(inicio):%d/%m/%Y %H:%M:%S} até "
                  f"{datetime.fromtimestamp(fim):%d/%m/%Y %H:%M:%S} "
                  f"(duração {fmt_dur(fim - inicio)})", est["Normal"]),
        Spacer(1, 0.4 * cm),
    ]

    def ms(v):
        return "—" if v is None else f"{v:.1f} ms"

    resumo = [
        ["Métrica", "Valor"],
        ["Média", ms(g.get("media"))],
        ["1% low (média do pior 1%)", ms(g.get("low1"))],
        ["Perda de pacote", f"{g['perda_pct']:.2f} %"],
        ["Pacotes perdidos", f"{g['perdas']} de {g['total']}"],
        ["Mediana", ms(g.get("mediana"))],
        ["Mínimo / Máximo", f"{ms(g.get('min'))} / {ms(g.get('max'))}"],
        ["Jitter", ms(g.get("jitter"))],
        [f"Pings lentos (> {LIMITE_LENTO} ms)", str(estado.lentos)],
        ["Quedas (perdas seguidas agrupadas)", str(len(lista_quedas))],
        ["Maior sequência de perdas", f"{estado.maior_seq_perdas} pacotes"],
    ]
    estilo = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3b57")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4f8")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c0c8d0")),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
    ])
    t = PTable(resumo, colWidths=[larg * 0.6, larg * 0.4])
    t.setStyle(estilo)
    el += [t, Spacer(1, 0.5 * cm), Image(img_tempo, width=larg, height=larg * 0.36)]
    if img_hist:
        el += [Spacer(1, 0.3 * cm), Image(img_hist, width=larg, height=larg * 0.28)]

    el += [Spacer(1, 0.5 * cm), Paragraph("Quedas", est["Heading2"])]
    if lista_quedas:
        LIM = 300
        linhas = [["#", "Início", "Fim", "Pacotes perdidos"]]
        for i, (a, b, n) in enumerate(lista_quedas[:LIM], 1):
            linhas.append([str(i), f"{datetime.fromtimestamp(a):%H:%M:%S}",
                           f"{datetime.fromtimestamp(b):%H:%M:%S}", str(n)])
        tq = PTable(linhas, colWidths=[larg * 0.1, larg * 0.3, larg * 0.3, larg * 0.3],
                    repeatRows=1)
        tq.setStyle(estilo)
        el.append(tq)
        if len(lista_quedas) > LIM:
            el.append(Paragraph(f"… e mais {len(lista_quedas) - LIM} quedas.", est["Normal"]))
    else:
        el.append(Paragraph("Nenhuma perda de pacote no período. 🎉".replace(" 🎉", ""),
                            est["Normal"]))

    doc.build(el)
    return caminho


def main():
    console = Console()
    estado = Estado()
    parar = threading.Event()
    threading.Thread(target=agendador, args=(estado, parar), daemon=True).start()
    try:
        with Live(render(estado, console), console=console, screen=True,
                  refresh_per_second=4) as live:
            while True:
                time.sleep(1)
                live.update(render(estado, console))
    except KeyboardInterrupt:
        pass
    finally:
        parar.set()
    fim = time.time()
    g = calc([ms for _, ms in estado.amostras])
    console.print(f"[bold]Resumo ({IP}, {fmt_dur(time.time() - estado.inicio)}):[/] "
                  f"média {fmt_ms(g.get('media'))} · 1% low {fmt_ms(g.get('low1'))} · "
                  f"perda {g['perda_pct']:.2f}% ({g['perdas']}/{g['total']})")

    if not estado.amostras:
        return
    try:
        if not Confirm.ask("Gerar relatório PDF?", default=True):
            return
    except (KeyboardInterrupt, EOFError):
        console.print()
        return
    with console.status("Gerando relatório…"):
        caminho = gera_pdf(estado, fim)
    console.print(f"[green]Relatório salvo em[/] {caminho}")
    subprocess.run(["open", caminho])


if __name__ == "__main__":
    main()
