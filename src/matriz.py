"""
Matriz de combinação — Seção 4 do documento de escopo técnico.

Cruza o regime do Módulo A (mensal, estratégico) com o score filtrado do
Módulo B (diário, tático) para gerar uma leitura acionável única — é o
"produto final" da Fase 1, a peça que junta os dois módulos na mesma
história.
"""

import pandas as pd

# Tabela de ação — a matriz 4x3 da Seção 4 do documento. A chave é uma
# tupla (regime, risco); o valor é a ação recomendada. Ter isso como um
# dicionário, e não uma cadeia de `if/elif`, deixa a tabela "visualmente
# igual" à tabela do documento — mais fácil de conferir uma contra a
# outra do que uma sequência de condicionais.
MATRIZ_ACAO = {
    ("Expansão", "Risk-on"): "Aumentar exposição a cíclicos/beta alto",
    ("Expansão", "Neutro"): "Manter exposição-alvo",
    ("Expansão", "Risk-off"): "Risk-off temporário → manter posição, tratar como ruído",
    ("Recuperação", "Risk-on"): "Aumentar exposição gradualmente, começar a rotacionar para cíclicos",
    ("Recuperação", "Neutro"): "Postura neutra, aguardar confirmação",
    ("Recuperação", "Risk-off"): "Cautela — pode ser recuperação falsa; reduzir tamanho das posições",
    ("Desaceleração", "Risk-on"): "Reduzir gradualmente, rotacionar para qualidade/defensivos",
    ("Desaceleração", "Neutro"): "Reduzir exposição-alvo",
    ("Desaceleração", "Risk-off"): "Reduzir risco de forma decisiva",
    ("Contração", "Risk-on"): 'Alerta — possível "bear market rally"; não confiar no sinal tático sozinho',
    ("Contração", "Neutro"): "Reduzir risco de forma decisiva",
    ("Contração", "Risk-off"): "Reduzir risco de forma decisiva (posição mais defensiva do framework)",
}


def classificar_risco(score_filtrado: float):
    """
    Agrupa o score filtrado do Módulo B (-2 a +2) em 3 baldes — Risk-on,
    Neutro, Risk-off — para caber nas colunas da matriz do documento.
    """
    if pd.isna(score_filtrado):
        return None
    if score_filtrado >= 1:
        return "Risk-on"
    elif score_filtrado <= -1:
        return "Risk-off"
    else:
        return "Neutro"


def gerar_acao(regime: str, risco: str):
    """Consulta a matriz de ação com o par (regime, risco)."""
    if regime is None or risco is None:
        return None
    return MATRIZ_ACAO.get((regime, risco))


def combinar_modulos(regime_mensal: pd.Series, score_filtrado_diario: pd.Series) -> pd.DataFrame:
    """
    Junta o regime mensal do Módulo A com o score diário filtrado do
    Módulo B, numa única tabela diária com regime + risco + ação.

    O passo chave aqui: o Módulo A é mensal (uma leitura por mês), mas o
    Módulo B é diário. Para combinar os dois, "espalhamos" o regime
    mensal para todos os dias — cada dia herda o último regime mensal
    conhecido, até que um novo apareça.

    Bug que encontrei testando com dados sintéticos antes de mandar:
    minha primeira tentativa usava `.resample("D").ffill()`, mas isso só
    preenche até a ÚLTIMA data que já existe na série mensal original —
    dias depois disso (por exemplo, os dias de um mês em andamento, antes
    do próximo dado mensal sair) ficavam vazios. A correção é usar
    `.reindex(..., method="ffill")`, que continua preenchendo para frente
    indefinidamente com o último valor conhecido, em vez de parar no
    limite da série original.
    """
    regime_diario = regime_mensal.reindex(score_filtrado_diario.index, method="ffill")

    resultado = pd.DataFrame({
        "regime": regime_diario,
        "score_filtrado": score_filtrado_diario,
    })
    # Só mantemos dias em que o Módulo B tem dado — dias antes do início
    # do Módulo B, ou depois do fim do que o Módulo A já cobre, não têm
    # uma leitura combinada útil.
    resultado = resultado.dropna(subset=["score_filtrado"])

    resultado["risco"] = resultado["score_filtrado"].apply(classificar_risco)
    resultado["acao"] = resultado.apply(
        lambda linha: gerar_acao(linha["regime"], linha["risco"]), axis=1
    )
    return resultado
