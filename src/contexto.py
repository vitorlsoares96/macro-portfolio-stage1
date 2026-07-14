"""
Camada de contexto do Módulo A — inflação e curva de juros.

Implementa a Seção 2.3 do documento de escopo técnico: regras que NÃO
entram no cálculo do regime (isso está em transformacao.py), mas que
qualificam esse regime com uma etiqueta extra de risco/contexto.
"""

import pandas as pd

from config import CONTEXTO_SERIES, DATA_INICIO
from transformacao import construir_serie_mensal


def buscar_contexto(start_date: str = DATA_INICIO) -> pd.DataFrame:
    """
    Busca as 4 séries de contexto (CPI, core PCE, spread 10y-2y, spread
    10y-3m), já transformadas e alinhadas em frequência mensal.

    Reaproveita `construir_serie_mensal` do módulo de transformação — a
    mesma função que usamos para o Módulo A serve aqui sem nenhuma
    alteração, porque ela só depende do dicionário de metadados
    (fred_id, transformacao, frequencia), não de qual "módulo" a série
    pertence. Isso é a recompensa de ter separado bem as responsabilidades
    desde o início: escrever uma vez, reaproveitar depois.
    """
    colunas = {
        nome: construir_serie_mensal(nome, meta, start_date)
        for nome, meta in CONTEXTO_SERIES.items()
    }
    return pd.DataFrame(colunas)


def calcular_tendencia_inflacao(df_contexto: pd.DataFrame) -> pd.Series:
    """
    Classifica a tendência de inflação (Seção 2.3-a do documento):
    compara o valor de hoje com o de 3 meses atrás — a "velocidade da
    inflação", não o nível dela — exigindo que CPI e Core PCE concordem
    sobre a direção antes de rotular. Se discordarem, o resultado é
    "Misto" (sinal indefinido), de propósito, para não forçar uma leitura
    clara quando o dado não é claro.
    """
    delta_cpi = df_contexto["cpi"] - df_contexto["cpi"].shift(3)
    delta_pce = df_contexto["core_pce"] - df_contexto["core_pce"].shift(3)

    def classificar(d_cpi, d_pce):
        if pd.isna(d_cpi) or pd.isna(d_pce):
            return None
        if d_cpi > 0 and d_pce > 0:
            return "Acelerando"
        elif d_cpi < 0 and d_pce < 0:
            return "Desacelerando"
        else:
            return "Misto"

    return pd.Series(
        [classificar(c, p) for c, p in zip(delta_cpi, delta_pce)],
        index=df_contexto.index,
        name="tendencia_inflacao",
    )


def calcular_alerta_curva(df_contexto: pd.DataFrame) -> pd.DataFrame:
    """
    Implementa a regra de alerta de curva de juros (Seção 2.3-b do
    documento): detecta inversão (T10Y2Y ou T10Y3M negativos), conta
    meses consecutivos invertida, e marca o evento de desinversão —
    historicamente o sinal mais próximo da recessão efetiva, mais do
    que a inversão em si.
    """
    invertida = (df_contexto["curva_10y2y"] < 0) | (df_contexto["curva_10y3m"] < 0)

    # Truque clássico do pandas para "contar sequências consecutivas de
    # True": cada vez que `invertida` é False, criamos um novo "grupo"
    # (via cumsum do oposto); dentro de cada grupo, somamos os True
    # acumulados. O resultado: um contador que zera toda vez que a curva
    # deixa de estar invertida, e volta a subir 1, 2, 3... enquanto ela
    # permanecer invertida.
    grupo = (~invertida).cumsum()
    meses_invertida = invertida.groupby(grupo).cumsum()

    # Desinversão: estava invertida no mês anterior (shift(1)) e não está
    # mais neste mês.
    desinversao = invertida.shift(1, fill_value=False) & (~invertida)

    # Bug encontrado testando com dados sintéticos: no mês em que a curva
    # desinverte, `meses_invertida` já zerou (porque o contador reseta no
    # mesmo mês em que `invertida` vira False) — então a mensagem dizia
    # "após 0 meses invertida", o que está errado. O que queremos mostrar
    # é quantos meses ela ESTEVE invertida antes de desinverter, ou seja,
    # o valor do contador no mês ANTERIOR (`.shift(1)`).
    meses_antes_de_desinverter = meses_invertida.shift(1, fill_value=0)

    def texto_alerta(inv, meses, des, meses_antes):
        if des:
            return (
                f"Curva acabou de desinverter após {int(meses_antes)} meses invertida — "
                "historicamente o sinal mais próximo da recessão efetiva."
            )
        if inv and meses >= 6:
            return f"Curva invertida há {int(meses)} meses — alerta elevado de recessão em 12 a 18 meses."
        if inv:
            return f"Curva invertida há {int(meses)} meses — monitorar."
        return "Curva normal (não invertida)."

    alerta = [
        texto_alerta(inv, meses, des, meses_antes)
        for inv, meses, des, meses_antes in zip(
            invertida, meses_invertida, desinversao, meses_antes_de_desinverter
        )
    ]

    return pd.DataFrame(
        {
            "curva_invertida": invertida,
            "meses_invertida": meses_invertida,
            "desinversao": desinversao,
            "alerta_curva": alerta,
        },
        index=df_contexto.index,
    )


# Tabela de narrativa regime x tendência de inflação — a mesma tabela 4x3
# da Seção 2.3-a do documento, agora como dicionário Python. A chave é
# uma tupla (regime, tendencia_inflacao); o valor é a frase explicativa.
NARRATIVA_INFLACAO = {
    ("Expansão", "Acelerando"): "Alerta de superaquecimento — Fed tende a apertar juros; a expansão pode durar menos do que o score sugere.",
    ("Expansão", "Desacelerando"): "Expansão saudável — crescimento sem pressão inflacionária, cenário mais favorável do quadro.",
    ("Expansão", "Misto"): "Expansão neutra, sem sinal inflacionário claro.",
    ("Recuperação", "Acelerando"): "Recuperação com inflação ainda alta — Fed pode manter juros restritivos e travar a retomada.",
    ("Recuperação", "Desacelerando"): "Recuperação limpa — Fed com espaço para cortar juros e apoiar o ciclo.",
    ("Recuperação", "Misto"): "Recuperação neutra.",
    ("Desaceleração", "Acelerando"): "Desaceleração com inflação subindo — risco de o Fed não conseguir agir a tempo.",
    ("Desaceleração", "Desacelerando"): 'Desaceleração "de manual" — Fed ganha espaço para cortar juros preventivamente.',
    ("Desaceleração", "Misto"): "Desaceleração neutra.",
    ("Contração", "Acelerando"): "Estagflação — cenário mais perigoso do quadro, Fed sem margem de manobra.",
    ("Contração", "Desacelerando"): 'Contração desinflacionária — cenário "padrão" de recessão, Fed com espaço para agir.',
    ("Contração", "Misto"): "Contração neutra.",
}


def gerar_narrativa(regime, tendencia_inflacao):
    """Combina regime (Módulo A) + tendência de inflação numa frase única."""
    if regime is None or tendencia_inflacao is None:
        return None
    return NARRATIVA_INFLACAO.get((regime, tendencia_inflacao))


def calcular_contexto_completo(regime: pd.Series, start_date: str = DATA_INICIO) -> pd.DataFrame:
    """
    Função "principal" deste arquivo: junta tudo — busca as séries de
    contexto, calcula tendência de inflação e alerta de curva, e gera a
    narrativa combinando com o regime do Módulo A (que é recebido como
    parâmetro, já calculado por transformacao.calcular_modulo_a — este
    arquivo não recalcula o regime, só o usa).
    """
    df_contexto = buscar_contexto(start_date)
    tendencia_inflacao = calcular_tendencia_inflacao(df_contexto)
    alerta_curva = calcular_alerta_curva(df_contexto)

    resultado = pd.DataFrame({
        "regime": regime,
        "tendencia_inflacao": tendencia_inflacao,
    })
    resultado = resultado.join(alerta_curva)
    resultado["narrativa"] = resultado.apply(
        lambda linha: gerar_narrativa(linha["regime"], linha["tendencia_inflacao"]), axis=1
    )
    return resultado
