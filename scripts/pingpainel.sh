#!/bin/bash
# Atalho para a área de trabalho. Uso: ./pingpainel.sh [ip] [--mudo] [--pasta DIR]
D="$HOME/Desktop/projetos-pessoais/ping-painel"
exec uv run --quiet --project "$D" ping-painel "$@"
