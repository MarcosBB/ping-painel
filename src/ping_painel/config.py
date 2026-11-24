"""Constantes e configuração da execução."""
from dataclasses import dataclass
from pathlib import Path

ALVO_PADRAO = "8.8.8.8"
TIMEOUT_MS = 3000      # sem resposta em 3 s = perda (mesmo critério do pingbeep.sh)
LIMITE_LENTO = 1000    # ms; acima disso conta como "lento" e apita
JANELA = 60            # segundos das estatísticas "recentes"
SOM = "/System/Library/Sounds/Sosumi.aiff"

PASTA_RELATORIOS = Path.home() / "Downloads"   # padrão; muda com --pasta


@dataclass
class Config:
    alvo: str = ALVO_PADRAO
    mudo: bool = False
    pasta_relatorios: Path = PASTA_RELATORIOS
