"""
Funções de ingestão de dados — Fase 1.

Este módulo não faz nenhum cálculo de score. Ele sabe fazer só uma coisa:
buscar dados brutos nas fontes (FRED e Yahoo Finance) e devolver como
pandas Series/DataFrame, prontos para os módulos que ainda vamos escrever
(transformação em z-score, classificação de regime, etc.) usarem.

Por que separar "buscar dado" de "calcular coisa com o dado" em arquivos
diferentes: isso se chama separação de responsabilidades (separation of
concerns) — um princípio central de engenharia de software. Na prática
significa que você pode trocar a fonte de um dado (ex: usar outra API no
lugar do FRED) sem tocar em uma linha da lógica de cálculo, e pode testar
cada parte isoladamente.
"""

import os
from fredapi import Fred
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

# load_dotenv() lê o arquivo .env (se existir) e "injeta" as variáveis dele
# no ambiente do processo Python — é como se você tivesse rodado
# `export FRED_API_KEY=...` no terminal antes de chamar o script.
load_dotenv()


def _get_fred_client() -> Fred:
    """
    Cria e devolve um cliente autenticado da API do FRED.

    O underscore no início do nome (_get_fred_client) é uma convenção do
    Python: sinaliza "isso é uso interno deste arquivo", não é pensado
    para outras partes do código chamarem diretamente. Quem for usar
    este módulo de fora deve chamar as funções fetch_* abaixo, não esta.
    """
    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        raise RuntimeError(
            "FRED_API_KEY não encontrada nas variáveis de ambiente. "
            "Copie .env.example para .env e cole sua chave gratuita "
            "(instruções no README.md)."
        )
    return Fred(api_key=api_key)


def fetch_fred_series(series_id: str, start_date: str = "1990-01-01") -> pd.Series:
    """
    Busca uma única série de dados no FRED.

    Parâmetros
    ----------
    series_id : str
        O identificador da série no FRED (ex: "INDPRO"). Os IDs usados
        neste projeto estão documentados em src/config.py e no documento
        de escopo técnico da Fase 1.
    start_date : str
        Data mínima a considerar, formato "AAAA-MM-DD".

    Retorna
    -------
    pandas.Series
        Uma série indexada por data (o índice já vem como DatetimeIndex
        do pandas — um tipo de índice "consciente de datas", que permite
        fazer coisas como series.rolling("365D") mais tarde).
    """
    fred = _get_fred_client()
    serie = fred.get_series(series_id, observation_start=start_date)
    serie.name = series_id  # nomeia a série — útil quando juntarmos várias num DataFrame
    return serie


def fetch_varias_series_fred(series_dict: dict, start_date: str = "1990-01-01") -> pd.DataFrame:
    """
    Busca várias séries do FRED de uma vez e junta tudo num único DataFrame.

    Parâmetros
    ----------
    series_dict : dict
        Um dicionário no formato de MODULO_A_SERIES, CONTEXTO_SERIES ou
        MODULO_B_FRED_SERIES (ver src/config.py) — a chave é um nome
        legível (ex: "producao_industrial"), o valor é um dicionário com
        pelo menos a chave "fred_id".

    Retorna
    -------
    pandas.DataFrame
        Um DataFrame com uma coluna por indicador, usando o nome legível
        como nome da coluna. Séries com frequências diferentes (ex: uma
        mensal e outra semanal) ficam alinhadas pelo mesmo índice de
        datas automaticamente — o pandas preenche com NaN (vazio) os
        dias em que uma série específica não tem observação. Isso é
        esperado e será tratado na etapa de transformação, não aqui.
    """
    colunas = {}
    for nome_legivel, meta in series_dict.items():
        colunas[nome_legivel] = fetch_fred_series(meta["fred_id"], start_date)
    return pd.DataFrame(colunas)


def fetch_varios_tickers_yahoo(tickers_dict: dict, start_date: str = "1990-01-01") -> pd.DataFrame:
    """
    Busca vários tickers do Yahoo Finance (câmbio, ouro) de uma vez.

    Parâmetros
    ----------
    tickers_dict : dict
        Um dicionário no formato de MODULO_B_YAHOO_TICKERS (ver
        src/config.py) — a chave é um nome legível, o valor tem a chave
        "ticker" com o símbolo real do Yahoo Finance (ex: "AUDJPY=X").

    Retorna
    -------
    pandas.DataFrame
        Um DataFrame com uma coluna por ticker, usando o preço de
        fechamento ajustado ("Close"). Diferente do FRED, o yfinance
        devolve várias colunas por ticker (Open, High, Low, Close,
        Volume) — por isso a função extrai só a coluna "Close" de cada
        um antes de juntar.
    """
    colunas = {}
    for nome_legivel, meta in tickers_dict.items():
        dados = yf.download(meta["ticker"], start=start_date, progress=False)
        fechamento = dados["Close"]

        # Versões recentes do yfinance às vezes devolvem as colunas em
        # dois níveis (MultiIndex: preço + ticker) mesmo pedindo um único
        # ticker — nesse caso, dados["Close"] vem como um DataFrame de
        # uma coluna só, em vez de uma Series. `.squeeze("columns")`
        # "achata" isso para Series quando há exatamente uma coluna, sem
        # alterar nada se já vier como Series (comportamento antigo).
        if isinstance(fechamento, pd.DataFrame):
            fechamento = fechamento.squeeze("columns")

        colunas[nome_legivel] = fechamento
    return pd.DataFrame(colunas)
