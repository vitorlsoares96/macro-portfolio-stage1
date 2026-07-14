"""
Configuração central do projeto — Fase 1 (Nowcasting + Risk-on/Risk-off).

Por que este arquivo existe, e por que só tem "dados", nenhuma lógica:
Este arquivo não CALCULA nada. Ele só guarda constantes — valores fixos que
várias partes do código vão precisar (quais séries puxar, de qual fonte,
com qual transformação). A ideia de centralizar isso em UM lugar só é:
se um dia você quiser trocar a janela do z-score de 10 para 8 anos, ou
adicionar uma nova série, você muda em UM lugar. Sem isso, esse tipo de
número ficaria espalhado (e esquecido) em vários arquivos diferentes.

Isso também é o motivo de este arquivo bater 1:1 com as tabelas do
documento de escopo técnico (Fase1_Escopo_Tecnico...md) — o código não
"reinventa" as escolhas, ele só implementa o que já foi decidido e
justificado lá. Se um recrutador perguntar "por que você usou essa
série", a resposta está no documento, não perdida dentro do código.
"""

# ---------------------------------------------------------------------------
# Módulo A — indicadores de ciclo econômico (mensal / semanal)
# Estrutura: um dicionário de dicionários. A chave externa ("producao_industrial")
# é um nome legível que vamos usar no resto do código; o dicionário interno
# guarda os metadados de cada série (o ID real no FRED, a categoria do CFNAI
# a que pertence, e que transformação matemática aplicar).
# ---------------------------------------------------------------------------
MODULO_A_SERIES = {
    "producao_industrial": {
        "fred_id": "INDPRO",
        "categoria": "producao",
        "transformacao": "yoy",  # variação % ano contra ano
        "frequencia": "mensal",
    },
    "payrolls": {
        "fred_id": "PAYEMS",
        "categoria": "emprego",
        "transformacao": "diff_mensal",  # variação absoluta mês a mês (milhares de empregos)
        "frequencia": "mensal",
    },
    "desemprego": {
        "fred_id": "UNRATE",
        "categoria": "emprego",
        "transformacao": "nivel_invertido",  # nível, mas sinal invertido (queda = positivo)
        "frequencia": "mensal",
    },
    "seguro_desemprego": {
        "fred_id": "ICSA",
        "categoria": "emprego",
        "transformacao": "nivel_invertido_mm4",  # média móvel 4 semanas, sinal invertido
        "frequencia": "semanal",  # precisa ser reduzida para mensal antes de juntar com as outras
    },
    "vendas_varejo": {
        "fred_id": "RSAFS",
        "categoria": "consumo",
        "transformacao": "yoy",
        "frequencia": "mensal",
    },
    "philly_fed": {
        "fred_id": "GACDFSA066MSFRBPHI",
        "categoria": "consumo",  # ver nota do doc: proxy de sentimento de manufatura
        "transformacao": "nivel",  # já é um índice de difusão centrado em 0
        "frequencia": "mensal",
    },
}

# ---------------------------------------------------------------------------
# Camada de contexto — inflação e curva de juros (NÃO entram na média do
# Módulo A; ver Seção 2.3 do documento de escopo para a regra completa)
# ---------------------------------------------------------------------------
CONTEXTO_SERIES = {
    "cpi": {"fred_id": "CPIAUCSL", "transformacao": "yoy", "frequencia": "mensal"},
    "core_pce": {"fred_id": "PCEPILFE", "transformacao": "yoy", "frequencia": "mensal"},
    "curva_10y2y": {"fred_id": "T10Y2Y", "transformacao": "nivel", "frequencia": "diaria"},
    "curva_10y3m": {"fred_id": "T10Y3M", "transformacao": "nivel", "frequencia": "diaria"},
}

# ---------------------------------------------------------------------------
# Módulo B — risk-on / risk-off (diário)
# Separado em duas fontes porque vêm de bibliotecas Python diferentes:
# FRED usa a biblioteca `fredapi`; os tickers de câmbio/commodity usam
# `yfinance`, porque não existem no FRED.
# ---------------------------------------------------------------------------
MODULO_B_FRED_SERIES = {
    "vix": {"fred_id": "VIXCLS", "inverter_sinal": True},
    # ATUALIZAÇÃO (achado testando com dados reais): a série original do
    # documento, BAMLH0A0HYM2 (spread de high yield do ICE BofA), tem uma
    # restrição de licenciamento no FRED — a API só devolve os últimos 3
    # anos, mesmo pedindo histórico desde 1990 (o site mostra tudo, a API
    # não). Trocamos para BAA10Y (spread de crédito Baa da Moody's, dado
    # público sem essa restrição, com histórico desde 1986) — mede a
    # mesma ideia (prêmio de risco de crédito), só que com um universo de
    # rating um pouco mais alto (Baa é "investment grade" baixo, não
    # "high yield" propriamente). Vale mencionar essa troca numa
    # entrevista: é um exemplo real de limitação de fonte de dados
    # descoberta e contornada, não só teoria.
    "credit_spread_hy": {"fred_id": "BAA10Y", "inverter_sinal": True},
    "jpy_usd": {"fred_id": "DEXJPUS", "inverter_sinal": True},
    "treasury_10y": {"fred_id": "DGS10", "inverter_sinal": True},
}

MODULO_B_YAHOO_TICKERS = {
    "aud_jpy": {"ticker": "AUDJPY=X", "inverter_sinal": False},
    "ouro": {"ticker": "GC=F", "inverter_sinal": False, "peso": 0.5},
}

# ---------------------------------------------------------------------------
# Parâmetros gerais
# ---------------------------------------------------------------------------
DATA_INICIO = "1990-01-01"  # janela ampla o suficiente para cobrir 2001, 2008 e 2020
JANELA_ZSCORE_MODULO_A_MESES = 120  # 10 anos — ver Seção 2.2 do documento
JANELA_ZSCORE_MODULO_B_DIAS = 504  # ~2 anos úteis — ver Seção 3.2 do documento
