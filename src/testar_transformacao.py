"""
Script de teste: roda o pipeline completo do Módulo A (dado bruto até
regime classificado) e mostra o resultado recente + uma checagem rápida
contra a recessão de 2020 (COVID), que já sabemos que aconteceu, para
validar se o modelo "faz sentido" antes de confiarmos nele.

Como rodar:
    cd src
    python testar_transformacao.py
"""

import pandas as pd

from transformacao import calcular_modulo_a
from config import DATA_INICIO

# Mostra todas as colunas sem cortar, e mais casas decimais — só para essa
# checagem visual ficar mais fácil de ler no terminal.
pd.set_option("display.width", 120)
pd.set_option("display.max_columns", 10)


if __name__ == "__main__":
    print("Calculando o Módulo A (isso busca ~6 séries no FRED, pode levar alguns segundos)...\n")
    resultado = calcular_modulo_a(start_date=DATA_INICIO)

    print("Últimos 6 meses classificados:")
    print(resultado.tail(6))
    print()

    print("Checagem de sanidade — março a junho de 2020 (COVID), deveria aparecer como Contração:")
    print(resultado.loc["2020-03-01":"2020-06-01"])
    print()

    print("Checagem de sanidade — 2021, deveria aparecer como Recuperação ou Expansão:")
    print(resultado.loc["2021-01-01":"2021-06-01"])