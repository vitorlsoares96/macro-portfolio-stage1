"""
Exportação para Excel — última peça da Fase 1.

Este arquivo não calcula nada de novo. Ele só chama os pipelines que já
existem (Módulo A + contexto, Módulo B, matriz de combinação) e escreve o
resultado num único arquivo .xlsx, com uma aba por peça. A partir daí, o
trabalho de montar o dashboard (tabelas dinâmicas, gráficos, formatação)
é feito por você, direto no Excel — este script só entrega os "dados
limpos", não tenta reproduzir Excel dentro do Python.

Por que juntar Módulo A e contexto numa aba só, em vez de duas: as duas
peças já são mensais e já compartilham o mesmo índice de datas (contexto
usa o regime do Módulo A como entrada), então faz mais sentido para quem
for montar tabela dinâmica ter uma linha por mês com TUDO (score, regime,
inflação, curva) do que ficar cruzando duas abas.

Como rodar:
    cd src
    python exportar_excel.py
"""

import pandas as pd

from config import DATA_INICIO
from transformacao import calcular_modulo_a
from contexto import calcular_contexto_completo
from modulo_b import calcular_modulo_b
from matriz import combinar_modulos
from dashboard import montar_dashboard


def montar_resumo_mensal(start_date: str = DATA_INICIO) -> pd.DataFrame:
    """
    Junta o Módulo A (score_nivel, score_ma3, momentum, regime) com a
    camada de contexto (tendência de inflação, alerta de curva, narrativa)
    numa única tabela mensal.

    Ponto que vale entender: `calcular_contexto_completo` já recebe o
    regime do Módulo A como parâmetro e devolve ele DE VOLTA como uma das
    colunas do resultado (é assim que a narrativa consegue combinar
    "regime + tendência de inflação" numa frase só). Isso significa que,
    se juntássemos os dois DataFrames sem cuidado, ficaríamos com duas
    colunas "regime" idênticas. `.drop(columns=["regime"])` remove essa
    duplicata do lado do contexto antes do join, para sobrar só uma.
    """
    modulo_a = calcular_modulo_a(start_date)
    contexto = calcular_contexto_completo(modulo_a["regime"], start_date)

    contexto_sem_regime_duplicado = contexto.drop(columns=["regime"])

    # .join() combina dois DataFrames pelo índice (a data). Como os dois
    # já vêm com o mesmo índice mensal (contexto foi calculado a partir do
    # regime do modulo_a), não precisamos passar nenhum parâmetro extra.
    resumo = modulo_a.join(contexto_sem_regime_duplicado)
    return resumo


def exportar_para_excel(caminho_saida: str = "fase1_dashboard.xlsx", start_date: str = DATA_INICIO) -> None:
    """
    Roda os três pipelines (Módulo A+contexto, Módulo B, matriz) e escreve
    tudo num único arquivo .xlsx, uma aba por peça.

    `pd.ExcelWriter` funciona como um "arquivo aberto para escrita": cada
    chamada de `.to_excel(writer, sheet_name=...)` escreve numa aba
    diferente do MESMO arquivo, em vez de sobrescrever. O `with` garante
    que o arquivo é salvo e fechado corretamente no final, mesmo se algo
    der errado no meio (o mesmo padrão que se usa para abrir arquivos
    normais em Python).

    `engine="openpyxl"` é a biblioteca que o pandas usa por baixo dos
    panos para gerar o .xlsx — precisa estar instalada no ambiente
    (`pip install openpyxl`; já está no requirements.txt).
    """
    print("Calculando Módulo A + contexto (mensal)...")
    resumo_mensal = montar_resumo_mensal(start_date)

    print("Calculando Módulo B (diário)...")
    modulo_b = calcular_modulo_b(start_date)

    print("Combinando os dois módulos na matriz de ação...")
    matriz_combinada = combinar_modulos(resumo_mensal["regime"], modulo_b["score_filtrado"])

    print(f"Escrevendo '{caminho_saida}'...")
    with pd.ExcelWriter(caminho_saida, engine="openpyxl") as writer:
        resumo_mensal.to_excel(writer, sheet_name="Modulo_A_Mensal", index_label="data")
        modulo_b.to_excel(writer, sheet_name="Modulo_B_Diario", index_label="data")
        matriz_combinada.to_excel(writer, sheet_name="Matriz_Combinada", index_label="data")

        # freeze_panes = "B2" "congela" a primeira linha (cabeçalho) e a
        # primeira coluna (a data) ao rolar a planilha — só um toque de
        # conforto para quem for explorar os dados manualmente no Excel.
        # writer.sheets é um dicionário {nome_da_aba: objeto da planilha do
        # openpyxl}, disponível depois que .to_excel() já escreveu a aba.
        for nome_aba in ["Modulo_A_Mensal", "Modulo_B_Diario", "Matriz_Combinada"]:
            writer.sheets[nome_aba].freeze_panes = "B2"

        print("Montando a aba Dashboard (gráficos, heatmap, cartão de status)...")
        montar_dashboard(writer, resumo_mensal, matriz_combinada)

    print("Pronto! Abra o arquivo no Excel para conferir.")


if __name__ == "__main__":
    exportar_para_excel()
