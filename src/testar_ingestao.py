"""
Script de teste: valida que a ingestão de dados está funcionando de
ponta a ponta, antes de seguirmos para as próximas etapas do pipeline
(transformação em z-score, classificação de regime).

Como rodar (depois de configurar o .env com sua chave do FRED — ver
README.md na raiz do projeto):

    cd src
    python testar_ingestao.py

Se algo der errado, copie a mensagem de erro completa e me envie —
é assim que vamos debugar juntos.
"""

from data_ingestion import fetch_fred_series, fetch_varias_series_fred
from config import MODULO_A_SERIES, DATA_INICIO


if __name__ == "__main__":
    # O bloco `if __name__ == "__main__":` é uma convenção do Python que
    # significa "só rode este código se este arquivo for executado
    # diretamente (python testar_ingestao.py), não se ele for importado
    # por outro arquivo". Isso importa porque este arquivo também define
    # (indiretamente, ao importar data_ingestion) funções reutilizáveis —
    # não queremos que o teste rode toda vez que outro script só quiser
    # usar uma função daqui.

    print("Teste 1: buscando uma única série (Produção Industrial, INDPRO)...")
    industrial = fetch_fred_series("INDPRO", start_date=DATA_INICIO)
    print(industrial.tail())  # .tail() mostra as últimas linhas = os dados mais recentes
    print(f"Total de observações: {len(industrial)}")
    print()

    print("Teste 2: buscando todas as séries do Módulo A de uma vez...")
    modulo_a = fetch_varias_series_fred(MODULO_A_SERIES, start_date=DATA_INICIO)
    print(modulo_a.tail())
    print(f"\nFormato do DataFrame (linhas, colunas): {modulo_a.shape}")
    print("\nSe você está vendo números de verdade acima (não erros), a ingestão do FRED está funcionando.")
