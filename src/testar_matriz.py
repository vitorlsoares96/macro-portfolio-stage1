"""
Script de teste final da Fase 1: roda os três módulos (A, B e a matriz de
combinação) de ponta a ponta e mostra a leitura atual, além de uma
checagem de sanidade para março de 2020 (deveria mostrar Contração +
Risk-off, ação mais defensiva do framework).

Como rodar:
    cd src
    python testar_matriz.py
"""

import pandas as pd

from transformacao import calcular_modulo_a
from modulo_b import calcular_modulo_b
from matriz import combinar_modulos
from config import DATA_INICIO

pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 10)
pd.set_option("display.max_colwidth", 70)


if __name__ == "__main__":
    print("Calculando o Módulo A...")
    modulo_a = calcular_modulo_a(start_date=DATA_INICIO)

    print("Calculando o Módulo B...")
    modulo_b = calcular_modulo_b(start_date=DATA_INICIO)

    print("Combinando os dois módulos...\n")
    combinado = combinar_modulos(modulo_a["regime"], modulo_b["score_filtrado"])

    print("Leitura atual (últimos 5 dias):")
    print(combinado[["regime", "risco", "acao"]].tail(5))
    print()

    print("Checagem de sanidade — março de 2020, esperado: Contração + Risk-off:")
    print(combinado.loc["2020-03-15":"2020-03-25", ["regime", "risco", "acao"]])
