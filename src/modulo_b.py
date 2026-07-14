"""
Cálculo do Módulo B — risk-on/risk-off, implementa a Seção 3.2 do
documento de escopo técnico.

Assim como transformacao.py cuida do Módulo A, este arquivo cuida
inteiramente do Módulo B: busca os indicadores diários, padroniza,
combina, discretiza em -2 a +2, e aplica o filtro de persistência.
"""

import pandas as pd

from config import (
    MODULO_B_FRED_SERIES,
    MODULO_B_YAHOO_TICKERS,
    DATA_INICIO,
    JANELA_ZSCORE_MODULO_B_DIAS,
)
from data_ingestion import fetch_fred_series, fetch_varios_tickers_yahoo
from transformacao import calcular_zscore_trailing  # reaproveitada do Módulo A


def buscar_modulo_b(start_date: str = DATA_INICIO) -> pd.DataFrame:
    """
    Busca os 6 indicadores diários do Módulo B (4 do FRED + 2 do Yahoo
    Finance) e junta tudo num único DataFrame diário.
    """
    colunas_fred = {
        nome: fetch_fred_series(meta["fred_id"], start_date=start_date)
        for nome, meta in MODULO_B_FRED_SERIES.items()
    }
    df_fred = pd.DataFrame(colunas_fred)

    df_yahoo = fetch_varios_tickers_yahoo(MODULO_B_YAHOO_TICKERS, start_date=start_date)

    # .join junta os dois DataFrames pela data (o índice). how="outer"
    # mantém qualquer data que apareça em QUALQUER um dos dois conjuntos
    # de séries — bolsas diferentes têm feriados diferentes (ex: um
    # feriado nos EUA não é feriado no Japão), então nem todo dia tem
    # observação de tudo ao mesmo tempo.
    df = df_fred.join(df_yahoo, how="outer")
    df = df.sort_index()

    # .ffill() ("forward fill") propaga o último valor conhecido para
    # frente, cobrindo esses buracos de feriado — assumimos que, se um
    # mercado não abriu, o valor de ontem "continua valendo" até a
    # próxima observação real.
    df = df.ffill()
    return df


def discretizar_score(z: float):
    """
    Seção 3.2, passo 4 do documento: transforma o z-score composto (um
    número contínuo, tipicamente entre -3 e +3) num inteiro de -2 a +2,
    usando as bandas definidas na tabela do documento.
    """
    if pd.isna(z):
        return None
    if z > 1.5:
        return 2
    elif z > 0.5:
        return 1
    elif z >= -0.5:
        return 0
    elif z >= -1.5:
        return -1
    else:
        return -2


def aplicar_filtro_persistencia(serie_score: pd.Series, dias_minimos: int = 5) -> pd.Series:
    """
    Seção 3.2, passo 5 do documento: só "confirma" uma mudança de lado
    (risk-on vs risk-off) depois que o SINAL do score (positivo, negativo
    ou zero) se mantiver igual por `dias_minimos` dias úteis seguidos.
    Enquanto não confirmado, o valor filtrado permanece igual ao último
    valor confirmado — é isso que evita que um susto de um dia único
    (um dado ruim que se dissipa no dia seguinte) mude a leitura tática.

    Nota sobre a implementação: aqui usamos um loop explícito em vez do
    truque de groupby+cumsum que usamos para contar meses de curva
    invertida em contexto.py. As duas abordagens resolvem problemas
    parecidos ("olhar para trás no tempo"); um loop é mais fácil de ler
    passo a passo, o groupby+cumsum é mais rápido e mais "pandas idiomático".
    Vale conhecer as duas.
    """
    sinal = serie_score.apply(
        lambda x: None if pd.isna(x) else (1 if x > 0 else (-1 if x < 0 else 0))
    )

    resultado = []
    ultimo_confirmado = None
    for i in range(len(sinal)):
        # Pega os últimos `dias_minimos` dias até hoje (inclusive).
        janela = sinal.iloc[max(0, i - dias_minimos + 1): i + 1]
        sinais_validos = janela.dropna()
        mesmo_sinal_o_periodo_todo = (
            len(sinais_validos) == dias_minimos and sinais_validos.nunique() == 1
        )
        if mesmo_sinal_o_periodo_todo:
            ultimo_confirmado = serie_score.iloc[i]
        resultado.append(ultimo_confirmado)

    return pd.Series(resultado, index=serie_score.index, name="score_filtrado")


def calcular_modulo_b(
    start_date: str = DATA_INICIO, dias_persistencia: int = 5, minimo_indicadores: int = 2
) -> pd.DataFrame:
    """
    Pipeline completo do Módulo B, da busca de dados até o score final
    filtrado. Função "principal" deste arquivo, na mesma lógica de
    transformacao.calcular_modulo_a.

    Parâmetro novo, `minimo_indicadores`: número mínimo de indicadores
    com dado válido num dia para aquele dia ter um composite calculado
    (ver explicação abaixo, no Passo 3) — proteção para quando algum
    indicador tem histórico mais curto que os outros (aconteceu com o
    AUD/JPY e o ouro, que só têm dado no Yahoo Finance a partir dos anos
    2000, bem depois de 1990).
    """
    df_bruto = buscar_modulo_b(start_date)

    # Junta os metadados dos dois grupos (FRED + Yahoo) num dicionário só,
    # já que a partir daqui o pipeline trata todo mundo do mesmo jeito.
    metas = {**MODULO_B_FRED_SERIES, **MODULO_B_YAHOO_TICKERS}

    # Passo 1: z-score diário de cada indicador (janela de ~2 anos úteis).
    df_zscore = pd.DataFrame({
        nome: calcular_zscore_trailing(
            df_bruto[nome], janela=JANELA_ZSCORE_MODULO_B_DIAS, minimo_periodos=60
        )
        for nome in metas
    })

    # Passo 2: inverte o sinal onde necessário (ver config.py), para que
    # em toda coluna um valor positivo signifique "mais risk-on".
    for nome, meta in metas.items():
        if meta.get("inverter_sinal"):
            df_zscore[nome] = -df_zscore[nome]

    # Passo 3: composite ponderado, tolerante a indicadores ausentes num
    # dia específico.
    #
    # A versão anterior fazia `sum(coluna * peso for ...)` somando as
    # Series do pandas com o operador `+` do Python — e a soma padrão do
    # pandas propaga NaN: se QUALQUER coluna tiver NaN numa data, o
    # resultado daquela data vira NaN, mesmo que as outras 5 colunas
    # tenham dado válido. Foi exatamente isso que "contaminou" quase todo
    # o histórico quando descobrimos que uma série tinha bem menos dado
    # que as outras.
    #
    # A correção: usar `.sum(axis=1)` de um DataFrame em vez de somar
    # Series uma a uma. `DataFrame.sum(axis=1)` IGNORA NaN por padrão
    # (trata como se a coluna não existisse naquela linha) em vez de
    # propagá-lo. Ao mesmo tempo, para a média ficar correta, também
    # somamos só os PESOS dos indicadores que realmente tinham dado
    # naquele dia — senão um dia com só 2 de 6 indicadores ficaria com
    # escala errada (dividindo por um "soma_pesos" fixo que não bate
    # com o que foi de fato somado).
    pesos = pd.Series({nome: meta.get("peso", 1.0) for nome, meta in metas.items()})

    contribuicoes = df_zscore.mul(pesos, axis=1)
    pesos_disponiveis = df_zscore.notna().mul(pesos, axis=1)
    numero_indicadores_disponiveis = df_zscore.notna().sum(axis=1)

    soma_pesos_disponiveis = pesos_disponiveis.sum(axis=1)
    score_z = contribuicoes.sum(axis=1) / soma_pesos_disponiveis

    # Exige um mínimo de indicadores válidos naquele dia; abaixo disso, o
    # composite fica indefinido (NaN) em vez de se apoiar num único
    # indicador isolado, o que daria uma falsa sensação de precisão.
    score_z[numero_indicadores_disponiveis < minimo_indicadores] = float("nan")
    score_z.name = "score_z"

    # Passo 4: discretização em -2 a +2.
    score_discreto = score_z.apply(discretizar_score)
    score_discreto.name = "score_discreto"

    # Passo 5: filtro de persistência.
    score_filtrado = aplicar_filtro_persistencia(score_discreto, dias_minimos=dias_persistencia)

    return pd.DataFrame({
        "score_z": score_z,
        "score_discreto": score_discreto,
        "score_filtrado": score_filtrado,
    })
