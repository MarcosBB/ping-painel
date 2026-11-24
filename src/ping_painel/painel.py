"""Interface do terminal (rich): monta o painel que é redesenhado a cada 1 s."""
import time
from datetime import datetime, timedelta

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .config import JANELA, LIMITE_LENTO
from .stats import calc

BLOCOS = "▁▂▃▄▅▆▇█"


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
    topo.add_row(Text.assemble(("Alvo: ", "dim"), (estado.config.alvo, "bold cyan"),
                               ("   Ping atual: ", "dim"), status),
                 Text(("🔇 mudo  ·  " if estado.config.mudo else "🔔 som ligado  ·  ") +
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
