"""
Transformação dos dados brutos do Módulo A em score de regime de ciclo
econômico — implementa a Seção 2.2 do documento de escopo técnico.

Este módulo assume que data_ingestion.py já resolveu o "buscar dado bruto".
Aqui a responsabilidade é diferente: pegar esse dado bruto e aplicar as
fórmulas (variação %, z-score, agregação, classificação) até chegar no
regime final (Expansão / Desaceleração / Contração / Recuperação).
"""

import pandas as pd

from config import MODULO_A_SERIES, DATA_INICIO, JANELA_ZSCORE_MODULO_A_MESES
from data_ingestion import fetch_fred_series


def transformar_serie(serie: pd.Series, tipo: str) -> pd.Series:
    """
    Aplica a transformação indicada (ver coluna "Transformação sugerida"
    da tabela de Módulo A no documento de escopo) a uma série bruta.

    Cada `if` abaixo corresponde a uma linha daquela tabela — a ideia é
    que, lendo esta função, você consiga voltar ao documento e achar
    exatamente de onde veio cada fórmula.
    """
    if tipo == "yoy":
        # Variação percentual em relação a 12 meses atrás. O `.pct_change(12)`
        # do pandas faz exatamente isso: (valor_hoje / valor_12_meses_atras) - 1.
        # Multiplicamos por 100 para expressar em pontos percentuais (ex: 3.2
        # em vez de 0.032).
        return serie.pct_change(12) * 100

    elif tipo == "diff_mensal":
        # Diferença simples em relação ao mês anterior (não percentual).
        # Para payrolls, isso dá "quantos empregos a mais ou a menos" no mês.
        return serie.diff()

    elif tipo == "nivel_invertido":
        # Só inverte o sinal. Uma taxa de desemprego que sobe devia empurrar
        # o score de atividade para baixo — multiplicar por -1 faz isso sem
        # precisar reescrever a lógica de agregação para tratar esse caso
        # especial mais adiante.
        return -serie

    elif tipo == "nivel_invertido_mm4":
        # Média móvel de 4 observações (nesta série, 4 semanas), depois
        # invertida. `.rolling(4)` olha para a própria observação e as 3
        # anteriores — nunca para o futuro, então não introduz look-ahead bias.
        return -serie.rolling(4).mean()

    elif tipo == "nivel":
        # Já vem pronta para uso (ex: Philly Fed já é um índice de difusão
        # centrado em zero) — não precisa de nenhuma transformação.
        return serie

    else:
        raise ValueError(f"Transformação desconhecida: '{tipo}'. Confira config.py.")


def construir_serie_mensal(nome_legivel: str, meta: dict, start_date: str) -> pd.Series:
    """
    Busca uma série (do Módulo A ou da camada de contexto), aplica sua
    transformação, e devolve sempre em frequência MENSAL — mesmo que a
    fonte original seja semanal (seguro-desemprego) ou diária (curva de
    juros).

    Por que fazer isso: se juntássemos séries de frequências diferentes
    direto num DataFrame, cada linha "extra" (semanal ou diária) ficaria
    com NaN nas colunas mensais (você viu isso acontecer no teste de
    ingestão). Reduzir tudo para mensal aqui, ANTES de juntar, evita esse
    problema na raiz, em vez de remendar depois.

    Esta função não sabe (nem precisa saber) de qual módulo a série é —
    ela só olha para o dicionário `meta` (fred_id, transformacao,
    frequencia). É por isso que a camada de contexto (Seção 2.3) consegue
    reaproveitar exatamente esta mesma função, sem duplicar código.
    """
    bruta = fetch_fred_series(meta["fred_id"], start_date=start_date)
    transformada = transformar_serie(bruta, meta["transformacao"])

    if meta["frequencia"] != "mensal":
        # .resample("MS") agrupa as observações por mês (MS = Month Start,
        # só um jeito de rotular cada grupo pelo primeiro dia do mês) e
        # .mean() tira a média das observações (semanais ou diárias) que
        # caem dentro de cada mês. Funciona igual não importa se a fonte
        # original era semanal ou diária — por isso não precisamos de um
        # `if` separado para cada caso, só "se não for mensal, resample".
        transformada = transformada.resample("MS").mean()

    return transformada


def calcular_zscore_trailing(
    serie: pd.Series, janela: int = JANELA_ZSCORE_MODULO_A_MESES, minimo_periodos: int = 24
) -> pd.Series:
    """
    Padroniza uma série em z-score, usando só dados até aquele momento
    (nunca do futuro) — ver Princípio de Design #3 no documento de escopo.

    `serie.rolling(window=janela, min_periods=minimo_periodos)` cria uma
    "janela deslizante": para calcular o valor na linha N, ele olha só
    para as linhas de N-janela+1 até N (nunca N+1 em diante). É isso que
    garante que não há look-ahead bias.

    `min_periods=24` significa: nos primeiros anos da série, quando ainda
    não há 120 meses de histórico, calcule mesmo assim usando o que tiver
    disponível (a partir de 24 meses) — em vez de devolver NaN até
    completar 10 anos inteiros. Isso é o que o documento chama de "janela
    expansiva nos primeiros anos da série".
    """
    media_movel = serie.rolling(window=janela, min_periods=minimo_periodos).mean()
    desvio_movel = serie.rolling(window=janela, min_periods=minimo_periodos).std()
    return (serie - media_movel) / desvio_movel


def classificar_regime(nivel: float, momentum: float) -> str | None:
    """
    Implementa a tabela 2x2 da Seção 2.2 do documento: cruza o *nível* do
    score (acima ou abaixo da média histórica) com o *momentum* (subindo
    ou caindo) para decidir o regime.

    Devolve None quando ainda não há dado suficiente para classificar
    (comum nos primeiros anos da série, antes da janela de z-score
    "esquentar").
    """
    if pd.isna(nivel) or pd.isna(momentum):
        return None
    if nivel > 0 and momentum > 0:
        return "Expansão"
    elif nivel > 0 and momentum <= 0:
        return "Desaceleração"
    elif nivel <= 0 and momentum > 0:
        return "Recuperação"
    else:
        return "Contração"


def calcular_modulo_a(start_date: str = DATA_INICIO) -> pd.DataFrame:
    """
    Roda o pipeline completo do Módulo A, do dado bruto até o regime
    classificado. É a função "principal" deste arquivo — as outras acima
    são os passos internos que ela orquestra, na mesma ordem em que
    aparecem na Seção 2.2 do documento:

    1. Buscar + transformar cada indicador (já em frequência mensal)
    2. Calcular o z-score de cada indicador individualmente
    3. Agregar os z-scores por categoria (produção, emprego, consumo)
    4. Score de nível = média das categorias
    5. Suavizar com média móvel de 3 meses
    6. Momentum = variação do score suavizado nos últimos 3 meses
    7. Classificar em regime (Expansão / Desaceleração / Contração / Recuperação)

    Retorna
    -------
    pandas.DataFrame
        Uma linha por mês, com as colunas: score_nivel, score_ma3,
        momentum, regime.
    """
    # Passo 1: buscar e transformar cada série (uma coluna por indicador)
    series_transformadas = {
        nome: construir_serie_mensal(nome, meta, start_date)
        for nome, meta in MODULO_A_SERIES.items()
    }
    df_transformado = pd.DataFrame(series_transformadas)

    # Passo 2: z-score de cada indicador, coluna por coluna.
    # `.apply(funcao)` num DataFrame roda `funcao` em cada coluna separadamente
    # e junta os resultados de volta num DataFrame do mesmo formato.
    df_zscore = df_transformado.apply(calcular_zscore_trailing)

    # Passo 3: agregar por categoria. Para cada categoria (produção, emprego,
    # consumo), pegamos a média das colunas que pertencem a ela.
    categorias_por_indicador = {nome: meta["categoria"] for nome, meta in MODULO_A_SERIES.items()}
    categorias_unicas = sorted(set(categorias_por_indicador.values()))

    df_categorias = pd.DataFrame({
        categoria: df_zscore[
            [nome for nome, cat in categorias_por_indicador.items() if cat == categoria]
        ].mean(axis=1)
        for categoria in categorias_unicas
    })

    # Passo 4: score de nível = média simples das categorias
    score_nivel = df_categorias.mean(axis=1)

    # Passo 5: suavização com média móvel de 3 meses
    score_ma3 = score_nivel.rolling(window=3, min_periods=3).mean()

    # Passo 6: momentum = variação do score suavizado nos últimos 3 meses
    momentum = score_ma3.diff(3)

    # Passo 7: classificar regime, linha a linha
    resultado = pd.DataFrame({
        "score_nivel": score_nivel,
        "score_ma3": score_ma3,
        "momentum": momentum,
    })
    resultado["regime"] = resultado.apply(
        lambda linha: classificar_regime(linha["score_ma3"], linha["momentum"]), axis=1
    )

    return resultado
