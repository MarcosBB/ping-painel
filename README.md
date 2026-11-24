# ping-painel

Painel de ping no terminal (Python + [rich](https://github.com/Textualize/rich))
que atualiza a cada 1 segundo.

- **Média**, **1% low** (média do pior 1% dos pings), **% de perda** e
  **quantidade de pacotes perdidos**, no geral e nos últimos 60 s
- Mediana, mín/máx, jitter, histórico com as perdas marcadas, última perda,
  maior sequência de perdas e pings lentos (> 1000 ms)
- Apita (som Sosumi do macOS) a cada perda ou ping > 1000 ms
- Ao sair (Ctrl+C), pergunta se quer gerar um **relatório PDF** com gráficos
  e a lista de quedas (salvo em `~/Downloads` por padrão)

## Uso

Projeto gerenciado com [uv](https://docs.astral.sh/uv/):

```bash
uv sync
uv run ping-painel                 # 8.8.8.8
uv run ping-painel 1.1.1.1
uv run ping-painel --mudo          # sem som
uv run ping-painel --pasta ~/Documents/relatorios
```

`scripts/pingpainel.sh` é um atalho para deixar na área de trabalho; ele chama
`uv run --project <pasta do projeto> ping-painel`.

## Estrutura

```
src/ping_painel/
├── cli.py        # argumentos, laço principal e pergunta do PDF
├── config.py     # constantes (timeout, limite de lento, pasta padrão…)
├── monitor.py    # dispara um ping por segundo, guarda resultados, apita
├── stats.py      # média, 1% low, perda, jitter, quedas
├── painel.py     # interface do terminal (rich)
└── relatorio.py  # relatório PDF (reportlab + matplotlib)
tests/            # testes (uv run pytest)
scripts/          # atalho .sh
```

## Testes

```bash
uv run pytest
```
