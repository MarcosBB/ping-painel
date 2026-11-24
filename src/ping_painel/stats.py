"""Cálculo das estatísticas a partir das amostras de ping."""
import math
import statistics


def calc(lista):
    """Recebe latências em ms (None = perda) e devolve um dicionário de métricas.

    "low1" é o 1% low: a média do pior 1% dos pings (os mais altos).
    """
    oks = [x for x in lista if x is not None]
    total = len(lista)
    perdas = total - len(oks)
    r = {"total": total, "perdas": perdas,
         "perda_pct": (perdas / total * 100) if total else 0.0}
    if oks:
        ordenado = sorted(oks, reverse=True)
        n1 = max(1, math.ceil(len(oks) * 0.01))
        r["media"] = statistics.fmean(oks)
        r["low1"] = statistics.fmean(ordenado[:n1])
        r["min"] = ordenado[-1]
        r["max"] = ordenado[0]
        r["mediana"] = statistics.median(oks)
        r["jitter"] = (statistics.fmean(abs(a - b) for a, b in zip(oks, oks[1:]))
                       if len(oks) > 1 else 0.0)
    return r


def quedas(amostras):
    """Agrupa perdas seguidas em quedas: [(inicio_ts, fim_ts, pacotes)].

    `amostras` é uma lista de (timestamp, ms ou None) em ordem de tempo.
    """
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
