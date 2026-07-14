# Portfólio de Macro & Quant — Fase 1

**Nowcasting de ciclo econômico (EUA) + score de risk-on/risk-off de mercado, combinados numa matriz de ação única.**

Este é o primeiro dos três módulos de um projeto de portfólio (Fase 1 —
nowcasting; Fase 2 — alocação sistemática + backtest; Fase 3 — VaR/stress
test), construído para transição de carreira para finanças/macro. O
racional completo de cada decisão de design está formalizado em
[`Fase1_Escopo_Tecnico_Nowcasting_RiskOnOff.md`](Fase1_Escopo_Tecnico_Nowcasting_RiskOnOff.md);
este README resume o "porquê" de cada peça e documenta os problemas reais
encontrados construindo o pipeline — a parte que normalmente não aparece
num tutorial.

## O que o projeto faz

Dois módulos independentes, cada um respondendo uma pergunta diferente:

- **Módulo A — em que fase do ciclo econômico os EUA estão?** Classifica
  o momento em 4 regimes (Expansão / Recuperação / Desaceleração /
  Contração), usando indicadores mensais de atividade (produção,
  emprego, consumo), com uma camada extra de contexto (inflação e curva
  de juros) que qualifica — mas não altera — essa classificação.
- **Módulo B — o mercado está com apetite a risco ou defensivo, agora?**
  Um score diário de -2 a +2, combinando 6 indicadores de risco de
  mercado (volatilidade, crédito, câmbio, juros, ouro).

Os dois são cruzados numa **matriz 4×3 de 12 ações recomendadas** — o
regime dá a visão estratégica (onde estamos no ciclo), o risco tático dá
o timing (o mercado já está precificando isso?).

## Metodologia — resumo das decisões de design

Cobertura completa na Seção 1–4 do documento de escopo; aqui vai o
resumo de cada "porquê":

**Por que separar atividade econômica (Módulo A) de preço de mercado
(Módulo B) em vez de um score único?** Porque respondem perguntas
diferentes e podem discordar de propósito — ex: ciclo em Contração mas
mercado já Risk-on precificando recuperação (célula "bear market rally"
da matriz). Misturar os dois num único número esconderia exatamente esse
tipo de sinal.

**Por que nível × momentum em vez de só nível?** Nível (score acima ou
abaixo da média histórica) sozinho não distingue "expansão perdendo
força" de "contração ganhando força" — dois momentos com prognósticos
opostos que teriam o mesmo score de nível. Cruzar nível com momentum
(direção do score suavizado nos últimos 3 meses) resolve isso com uma
tabela 2×2.

**Por que a camada de contexto (inflação, curva de juros) fica fora da
média do regime?** Inflação e curva de juros são úteis para *qualificar*
o regime (ex: "expansão com inflação acelerando" é mais frágil que
"expansão com inflação caindo"), mas não são medidas de atividade — jogá-
las na mesma média dos indicadores de produção/emprego/consumo
misturaria "quanto a economia está crescendo" com "quão sustentável isso
é", duas perguntas diferentes.

**Por que z-score com janela móvel (trailing), nunca centrada?** Qualquer
padronização que "olhe para o futuro" (janela centrada, ou calculada com
o histórico completo de uma vez) introduz look-ahead bias — o modelo
teria informação em 2015 que só existiu porque sabemos o que aconteceu
em 2020. Todo o pipeline usa `.rolling()` trailing, propositalmente.

**Por que o Módulo B usa filtro de persistência (5 dias)?** Sem isso, um
único dia de dado ruidoso (não um choque real) poderia fazer a leitura
tática "piscar" entre risk-on e risk-off, gerando ruído que ninguém
seguiria na prática. O filtro só confirma uma mudança de lado depois do
sinal se manter no mesmo sentido por 5 dias úteis seguidos.

**Por que pesos diferentes no Módulo B (ouro com peso 0,5)?** Ouro reage
tanto a risk-off quanto a inflação — é um sinal "mais ruidoso" para essa
finalidade específica que os outros 5 indicadores, por isso pesa menos
na média em vez de ser excluído.

## Desafios técnicos reais (não teoria — coisas que quebraram e como foram resolvidas)

Esta seção existe de propósito: mostra o processo de construção, não só
o resultado final.

- **Restrição de licenciamento de dado descoberta em produção.** A série
  original de spread de high-yield (`BAMLH0A0HYM2`, ICE BofA) só devolve
  os últimos 3 anos pela API do FRED, mesmo pedindo histórico desde 1990
  — uma restrição real de licenciamento do provedor, visível só ao
  tentar puxar o dado (o site do FRED mostra o histórico completo, a API
  não). Resolvido trocando para `BAA10Y` (spread de crédito Baa da
  Moody's, sem essa restrição) e tornando o cálculo do composite
  tolerante a indicadores com históricos de tamanhos diferentes.
- **Bug de propagação de NaN no composite ponderado.** A primeira versão
  somava as séries indicador a indicador com o operador `+` do pandas,
  que propaga `NaN`: um único indicador sem dado numa data "contaminava"
  o composite inteiro naquela data, mesmo com os outros 5 indicadores
  válidos. Corrigido usando `DataFrame.sum(axis=1)` (que ignora `NaN` por
  padrão) e renormalizando os pesos por linha, só com os indicadores
  disponíveis naquele dia.
- **`.resample("D").ffill()` vs `.reindex(..., method="ffill")`.** Ao
  espalhar o regime mensal do Módulo A para o índice diário do Módulo B,
  `.resample().ffill()` só preenche até a última data já existente na
  série mensal — dias do mês corrente (antes do próximo dado mensal sair)
  ficavam `NaN`. `.reindex()` continua preenchendo para frente
  indefinidamente.
- **Contador de meses de inversão de curva "zerando" no mês errado.** O
  contador de meses consecutivos de curva invertida (via
  `groupby().cumsum()`) reseta no mesmo mês em que a curva desinverte —
  a mensagem de alerta usava esse valor já zerado, dizendo "desinverteu
  após 0 meses". Corrigido usando o valor do contador do mês *anterior*
  (`.shift(1)`) especificamente para essa mensagem.
- **`yfinance` devolvendo `MultiIndex` mesmo para 1 ticker.** Versões
  recentes às vezes retornam colunas em dois níveis (preço × ticker)
  mesmo pedindo um único papel, quebrando a conversão para `Series`.
  Corrigido com `.squeeze("columns")`.
- **Bug de eixo num gráfico só descoberto visualmente.** Um gráfico de
  dispersão (nível × momentum) estava lendo a coluna de datas como eixo
  X em vez do score — o arquivo Excel era gerado sem nenhum erro, só o
  gráfico ficava errado. Só foi encontrado renderizando o arquivo e
  comparando visualmente (não um teste que se pega com asserts
  numéricos). Reforça a lição: gráfico gerado por código também precisa
  de inspeção visual, não só "rodou sem exception".

## Estrutura do projeto

```
macro_portfolio/
├── Fase1_Escopo_Tecnico_Nowcasting_RiskOnOff.md   # racional completo de cada decisão
├── README.md                                       # este arquivo
├── requirements.txt
├── .env.example            # modelo do arquivo de credenciais (copiar para .env)
├── .gitignore               # garante que .env nunca vai para o GitHub
├── src/
│   ├── config.py             # todas as séries/tickers usados, num só lugar
│   ├── data_ingestion.py     # busca dados brutos no FRED e Yahoo Finance
│   ├── transformacao.py      # Módulo A: z-score, agregação, regime
│   ├── contexto.py           # camada de inflação + curva de juros
│   ├── modulo_b.py           # Módulo B: composite, discretização, persistência
│   ├── matriz.py             # cruza os dois módulos na matriz de ação
│   ├── exportar_excel.py     # exporta os 3 resultados para um .xlsx
│   ├── dashboard.py          # aba extra no Excel com gráficos/heatmap (opcional)
│   └── testar_*.py           # um script de teste por módulo, cada um com
│                              # checagem de sanidade contra evento histórico real
└── diagrama/
    └── gerar_diagrama.py     # gera diagrama_fase1.html — mapa visual do
                                # pipeline completo (indicador → ação)
```

## Como rodar

### 1. Pré-requisitos

- Python 3.10+
- Chave de API gratuita do FRED: https://fredaccount.stlouisfed.org/apikeys

### 2. Ambiente virtual

```bash
python -m venv venv

# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate
```

### 3. Instalar dependências

```bash
pip install -r requirements.txt
```

### 4. Configurar a chave

```bash
cp .env.example .env
```

Depois edite `.env` e cole a chave gerada no passo 1.

### 5. Validar o pipeline, módulo por módulo

```bash
cd src
python testar_ingestao.py       # confirma que os dados brutos chegam
python testar_transformacao.py  # Módulo A — checa contra Covid e 2021
python testar_contexto.py       # checa contra o ciclo de alta de juros 2022-23
python testar_modulo_b.py       # Módulo B — checa contra Covid
python testar_matriz.py         # matriz combinada — leitura atual + Covid
```

### 6. Gerar o Excel e o diagrama

```bash
python exportar_excel.py                 # gera fase1_dashboard.xlsx (3 abas de dados)
cd ../diagrama
python gerar_diagrama.py                 # gera diagrama_fase1.html
```

O `diagrama_fase1.html` é autocontido — abre em qualquer navegador, sem
precisar rodar nada. É o material mais fácil de mostrar numa entrevista:
mapeia visualmente os 12 indicadores brutos até as 12 ações finais da
matriz.

## Problemas comuns

- `RuntimeError: FRED_API_KEY não encontrada` → confira se o arquivo se
  chama exatamente `.env` (não `.env.txt` — alguns editores adicionam essa
  extensão sem avisar) e se ele está na raiz do projeto (não dentro de `src/`).
- `ModuleNotFoundError` → o ambiente virtual não foi ativado antes de
  rodar o script, ou o `pip install -r requirements.txt` não terminou
  sem erros — role para cima no terminal e veja se alguma instalação falhou.
- Erro vindo do `yfinance` (`Close` não encontrado, ou dados vazios) →
  às vezes o Yahoo Finance limita requisições repetidas em pouco tempo;
  espere um minuto e tente de novo.

## Limitações conhecidas

- A camada de contexto (inflação) fica sem leitura nos meses mais
  recentes por defasagem real de publicação do CPI/Core PCE (~1 mês de
  atraso) — não é um bug, é a natureza do dado.
- O pipeline busca dado ao vivo da API a cada execução (não há cache
  local em disco ainda) — cada rodada depende de FRED e Yahoo Finance
  estarem no ar.
- O peso de cada indicador (Módulo A e B) foi definido por julgamento
  qualitativo documentado no escopo técnico, não otimizado
  estatisticamente — é uma escolha consciente para a Fase 1 (evitar
  overfitting num framework que ainda não tem dados de retorno para
  validar contra).

## Próximos passos

Fase 2: transformar a leitura da matriz (regime + risco) numa regra de
alocação sistemática entre classes de ativos, e rodar um backtest
histórico para medir se essas 12 ações realmente teriam adicionado valor
desde 1990. Fase 3: framework de VaR / stress test sobre a carteira
resultante.
