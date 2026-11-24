"""Geração do relatório PDF (reportlab + gráficos com matplotlib)."""
import io
from datetime import datetime

from .config import LIMITE_LENTO
from .painel import fmt_dur
from .stats import calc, quedas


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

    amostras = estado.copia_ordenada()
    alvo = estado.config.alvo
    g = calc([ms for _, ms in amostras])
    lista_quedas = quedas(amostras)
    inicio = estado.inicio

    pasta = estado.config.pasta_relatorios
    pasta.mkdir(parents=True, exist_ok=True)
    nome = f"ping-{alvo.replace(':', '_')}-{datetime.fromtimestamp(inicio):%Y%m%d-%H%M%S}.pdf"
    caminho = str(pasta / nome)

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
                            bottomMargin=1.5 * cm, title=f"Relatório de ping {alvo}")
    larg = A4[0] - 3.2 * cm
    el = [
        Paragraph(f"Relatório de ping: {alvo}", est["Title"]),
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
