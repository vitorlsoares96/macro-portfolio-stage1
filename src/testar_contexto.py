"""
Script de teste: roda a camada de contexto (inflação + curva de juros) e
junta com o regime do Módulo A, mostrando os últimos meses e uma
checagem de sanidade para 2022-2023 (ciclo de aperto monetário do Fed,
quando a curva de juros ficou invertida por um período longo e
conhecido).

Como rodar:
    cd src
    python testar_contexto.py
"""

import pandas as pd

from transformacao import calcular_modulo_a
from contexto import calcular_contexto_completo
from config import DATA_INICIO

pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 10)
pd.set_option("display.max_colwidth", 70)


if __name__ == "__main__":
    print("Calculando o Módulo A...")
    modulo_a = calcular_modulo_a(start_date=DATA_INICIO)

    print("Calculando a camada de contexto (inflação + curva de juros)...\n")
    contexto = calcular_contexto_completo(modulo_a["regime"], start_date=DATA_INICIO)

    print("Últimos 6 meses — regime + narrativa:")
    print(contexto[["regime", "tendencia_inflacao", "narrativa"]].tail(6))
    print()

    print("Últimos 6 meses — alerta de curva:")
    print(contexto[["curva_invertida", "meses_invertida", "desinversao", "alerta_curva"]].tail(6))
    print()

    print("Checagem de sanidade — 2022 a 2023 (ciclo de aperto monetário do Fed, "
          "a curva deveria aparecer invertida na maior parte deste período):")
    print(contexto.loc["2022-07-01":"2023-06-01", ["curva_invertida", "meses_invertida", "alerta_curva"]])
