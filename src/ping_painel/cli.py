"""Ponto de entrada: lê os argumentos, roda o painel e oferece o relatório."""
import argparse
import subprocess
import time
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.prompt import Confirm

from .config import ALVO_PADRAO, PASTA_RELATORIOS, Config
from .monitor import Estado, inicia
from .painel import fmt_dur, fmt_ms, render
from .stats import calc


class Confirma(Confirm):
    """Pergunta sim/não em português: [s/n]."""
    choices = ["s", "n"]
    validate_error_message = "[prompt.invalid]Responda s ou n"


def args():
    p = argparse.ArgumentParser(
        prog="ping-painel",
        description="Painel de ping ao vivo (atualiza a cada 1 s). "
                    "Apita a cada perda ou ping > 1000 ms.")
    p.add_argument("alvo", nargs="?", default=ALVO_PADRAO,
                   help=f"IP ou host (padrão: {ALVO_PADRAO})")
    p.add_argument("--mudo", action="store_true", help="não apita")
    p.add_argument("--pasta", type=Path, default=PASTA_RELATORIOS,
                   help=f"onde salvar o relatório PDF (padrão: {PASTA_RELATORIOS})")
    a = p.parse_args()
    return Config(alvo=a.alvo, mudo=a.mudo, pasta_relatorios=a.pasta.expanduser())


def main():
    config = args()
    console = Console()
    estado = Estado(config)
    parar = inicia(estado)
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

    g = calc([ms for _, ms in estado.copia_ordenada()])
    console.print(f"[bold]Resumo ({config.alvo}, {fmt_dur(fim - estado.inicio)}):[/] "
                  f"média {fmt_ms(g.get('media'))} · 1% low {fmt_ms(g.get('low1'))} · "
                  f"perda {g['perda_pct']:.2f}% ({g['perdas']}/{g['total']})")
    if not g["total"]:
        return

    try:
        if not Confirma.ask("Gerar relatório PDF?", default=True):
            return
    except (KeyboardInterrupt, EOFError):
        console.print()
        return
    from .relatorio import gera_pdf  # importa matplotlib só se precisar
    with console.status("Gerando relatório…"):
        caminho = gera_pdf(estado, fim)
    console.print(f"[green]Relatório salvo em[/] {caminho}")
    subprocess.run(["open", caminho])
