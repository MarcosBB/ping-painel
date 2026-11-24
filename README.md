# ping-painel

Painel de ping no terminal (Python + rich) que atualiza a cada 1 s:
média, 1% low, % e quantidade de pacotes perdidos, mediana, mín/máx,
jitter, histórico com as perdas e sequência de quedas.

- Apita (Sosumi) a cada perda ou ping > 1000 ms (`--mudo` desliga).
- Ao sair (Ctrl+C), pergunta se quer gerar um relatório PDF em `relatorios/`.

## Uso

    ~/Desktop/pingpainel.sh            # 8.8.8.8
    ~/Desktop/pingpainel.sh 1.1.1.1
    ~/Desktop/pingpainel.sh --mudo

Precisa do [uv](https://docs.astral.sh/uv/): as dependências (rich,
reportlab, matplotlib) ficam declaradas no próprio script e são
instaladas automaticamente.
