"""
Script de teste: roda o Módulo B (risk-on/risk-off) e faz uma checagem
de sanidade contra março de 2020 (pânico do COVID nos mercados) — um dos
eventos de risk-off mais extremos e bem documentados da história
recente. Também mostra um período mais calmo para contraste.

Como rodar:
    cd src
    python testar_modulo_b.py
"""

import pandas as pd

from modulo_b import calcular_modulo_b
from config import DATA_INICIO

pd.set_option("display.width", 120)
pd.set_option("display.max_columns", 10)


if __name__ == "__main__":
    print("Calculando o Módulo B (busca 4 séries do FRED + 2 do Yahoo Finance, pode levar um pouco)...\n")
    resultado = calcular_modulo_b(start_date=DATA_INICIO)

    print("Últimos 10 dias úteis:")
    print(resultado.tail(10))
    print()

    print("Checagem de sanidade — março de 2020 (pânico do COVID), "
          "esperado: score_z bem negativo, score_discreto perto de -2:")
    print(resultado.loc["2020-03-01":"2020-03-31"])
    print()

    print("Contraste — um período mais calmo (segunda metade de 2019), "
          "esperado: scores próximos de 0, sem extremos:")
    print(resultado.loc["2019-07-01":"2019-08-31"].iloc[::5])  # a cada 5 dias, pra não poluir
