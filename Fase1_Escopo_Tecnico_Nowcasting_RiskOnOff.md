# Fase 1 — Escopo Técnico
## Nowcasting de Ciclo Econômico + Risk-on/Risk-off (EUA)

**Projeto:** Portfolio de Macro & Quant
**Escopo geográfico:** Estados Unidos (fonte única: FRED + Yahoo Finance)
**Data:** julho/2026

---

## 1. Princípios de design

Antes das fontes de dados, três decisões metodológicas que valem a pena deixar explícitas — inclusive numa entrevista, porque mostram que o projeto foi pensado, não só copiado:

1. **Módulo A (nowcasting) mede atividade, não preço.** Seguindo o desenho do Chicago Fed National Activity Index (CFNAI), o índice de ciclo é construído a partir de indicadores de produção, emprego e consumo — a inflação e a curva de juros entram como **camada de contexto**, não dentro da mesma média. Misturar tudo num único z-score reduz a interpretabilidade (um CPI alto e um payroll forte empurram o índice na mesma direção por razões opostas). Essa separação é um ponto de discussão de design, não um detalhe técnico.
2. **Regime = nível × direção, não só nível.** Os quatro regimes (Expansão, Desaceleração, Contração, Recuperação) só existem se o modelo tiver dois eixos: o *nível* do score (acima ou abaixo da média histórica) e o seu *momentum* (subindo ou caindo). É o mesmo princípio por trás do "growth cycle clock" que a OECD usa nos seus Composite Leading Indicators (nível do CLI vs. taxa de variação em 6 meses).
3. **Nada de look-ahead bias.** Toda padronização (z-score) usa apenas dados disponíveis até aquele momento (janela móvel *trailing*, nunca centrada). Isso é obrigatório porque a Fase 2 vai rodar backtest em cima destes scores — se o z-score "olhar para o futuro" ao ser calculado, o backtest fica inválido antes mesmo de começar.

---

## 2. Módulo A — Ciclo Econômico (Nowcasting)

### 2.1 Fontes de dados

Estrutura inspirada nas 4 categorias do CFNAI (produção/renda, emprego, consumo, vendas/pedidos), com todas as séries disponíveis gratuitamente via **API do FRED**.

| Categoria | Indicador | Series ID (FRED) | Frequência | Transformação sugerida |
|---|---|---|---|---|
| Produção | Produção Industrial | `INDPRO` | Mensal | Var. % YoY |
| Emprego | Payrolls não-agrícolas | `PAYEMS` | Mensal | Variação mensal (milhares) |
| Emprego | Taxa de desemprego | `UNRATE` | Mensal | Nível, sinal invertido (queda = positivo) |
| Emprego (alta freq.) | Pedidos de seguro-desemprego | `ICSA` | Semanal | Média móvel 4 semanas, sinal invertido |
| Consumo | Vendas no varejo | `RSAFS` | Mensal | Var. % YoY |
| Vendas/pedidos (proxy manufatura) | Philly Fed Business Outlook (Current General Activity) | `GACDFSA066MSFRBPHI` | Mensal | Nível (já é índice de difusão centrado em 0) |

**Camada de contexto (não entra na média, mas qualifica o regime):**

| Indicador | Series ID (FRED) | Uso |
|---|---|---|
| CPI headline | `CPIAUCSL` | Var. % YoY — distingue "contração desinflacionária" de "estagflação" |
| Core PCE (preferido do Fed) | `PCEPILFE` | Var. % YoY — mesmo uso, é a métrica que o FOMC observa |
| Spread 10y-2y | `T10Y2Y` | Nível — indicador líder clássico de recessão (12-18 meses de antecedência) |
| Spread 10y-3m | `T10Y3M` | Nível — versão preferida pelo NY Fed para modelo de probabilidade de recessão |

**Nota sobre o ISM Manufacturing PMI:** é o indicador mais "reconhecível" de sentimento de manufatura, mas o ISM [removeu seus dados históricos do FRED em 2016](https://news.research.stlouisfed.org/2016/06/institute-for-supply-management-data-to-be-removed-from-fred/) por questão de licenciamento — hoje só está disponível via assinatura paga ou como número mensal avulso e gratuito no [site do ISM](https://www.ismworld.org/supply-management-news-and-reports/reports/ism-pmi-reports/). Duas opções, sem precisar pagar assinatura:
- **Opção A (recomendada para o MVP):** usar o Philly Fed Business Outlook como proxy de sentimento de manufatura — é gratuito, tem série longa no FRED e historicamente correlacionado com o ISM.
- **Opção B (enriquecimento opcional):** inserir manualmente o valor mensal do ISM PMI (leva 2 minutos por mês, o número é publicado de graça) para dar mais credibilidade ao dashboard em entrevistas, sem depender dele para o cálculo automatizado.

### 2.2 Transformação em score numérico

1. **Padronização (z-score):** para cada indicador, calcular `z = (valor_t − média_móvel_trailing) / desvio_padrão_móvel_trailing`, com janela de 10 anos (120 meses) quando houver histórico suficiente, ou janela expansiva nos primeiros anos da série. Isso replica a lógica do CFNAI, que também padroniza cada componente antes de agregar.
2. **Agregação por categoria:** média simples dos z-scores dentro de cada categoria (Produção, Emprego, Consumo/Vendas).
3. **Composite de nível:** média das 3 categorias → `Score_Nível` (equivalente ao CFNAI mensal, mas com 3 blocos em vez de 4).
4. **Suavização:** média móvel de 3 meses do composite (`Score_MA3`) — mesma lógica do CFNAI-MA3, para reduzir ruído mês a mês.
5. **Momentum:** variação do `Score_MA3` nos últimos 3 meses → `Score_Momentum`.
6. **Classificação em quadrante:**

| | Momentum > 0 (subindo) | Momentum ≤ 0 (caindo) |
|---|---|---|
| **Nível > 0** (acima da média histórica) | **Expansão** | **Desaceleração** |
| **Nível ≤ 0** (abaixo da média histórica) | **Recuperação** | **Contração** |

Como referência de calibração, o próprio Chicago Fed usa `CFNAI-MA3 > −0,70` como fronteira entre expansão e contração — um ponto de partida defensável para o threshold do eixo "Nível" antes de calibrar com dados próprios.

### 2.3 Camada de contexto: regras formais (inflação e curva de juros)

Estas duas variáveis não entram no cálculo do `Score_Nível`/`Score_Momentum` (Seção 2.2) — elas são calculadas à parte e depois anexadas ao regime já classificado, como uma etiqueta. Abaixo, a regra exata de cada uma.

**a) Tendência de inflação**

1. Calcular a variação em 3 meses de cada série de inflação (já em % YoY, ver Seção 2.1):
   `ΔCPI = CPI_YoY_t − CPI_YoY_{t−3}`
   `ΔPCE = PCE_YoY_t − PCE_YoY_{t−3}`
2. Classificar:
   - **Acelerando**, se `ΔCPI > 0` **e** `ΔPCE > 0` (as duas séries confirmam a mesma direção)
   - **Desacelerando**, se `ΔCPI < 0` **e** `ΔPCE < 0`
   - **Misto**, se as duas séries discordarem (trata-se como sinal indefinido — não força uma etiqueta quando o dado não é claro)

Exigir que CPI e Core PCE concordem é proposital: são duas medidas de inflação com metodologias diferentes, e usar as duas como confirmação cruzada evita que um mês de ruído numa série só já dispare uma etiqueta.

3. Cruzar `Inflation_Trend` com o regime do Módulo A para gerar a narrativa de contexto:

| Regime \ Inflação | Acelerando | Desacelerando | Misto |
|---|---|---|---|
| **Expansão** | Alerta de superaquecimento — Fed tende a apertar juros; a expansão pode durar menos do que o score sugere | Expansão saudável — crescimento sem pressão inflacionária, cenário mais favorável do quadro | Expansão neutra, sem sinal inflacionário claro |
| **Recuperação** | Recuperação com inflação ainda alta — Fed pode manter juros restritivos e travar a retomada | Recuperação limpa — Fed com espaço para cortar juros e apoiar o ciclo | Recuperação neutra |
| **Desaceleração** | Desaceleração com inflação subindo — risco de o Fed não conseguir agir a tempo | Desaceleração "de manual" — Fed ganha espaço para cortar juros preventivamente | Desaceleração neutra |
| **Contração** | **Estagflação** — cenário mais perigoso do quadro, Fed sem margem de manobra | Contração desinflacionária — cenário "padrão" de recessão, Fed com espaço para agir | Contração neutra |

**b) Alerta de curva de juros**

1. Definir inversão mês a mês: `Curve_Inverted_t = 1` se `T10Y2Y_t < 0` **ou** `T10Y3M_t < 0`; caso contrário, `0`. (As duas séries costumam divergir por semanas — reportar as duas no dashboard, não só uma, já que a `T10Y3M` é a preferida pelo modelo de probabilidade de recessão do NY Fed e a `T10Y2Y` é a mais citada pelo mercado.)
2. Contar meses consecutivos invertida: `Months_Inverted` (zera sempre que `Curve_Inverted` volta a `0`).
3. Marcar o evento de **desinversão**: `Des_Inversão_t = 1` quando `Curve_Inverted_{t−1} = 1` e `Curve_Inverted_t = 0` — ou seja, o spread acabou de voltar a ficar positivo depois de um período negativo. Esse evento, e não a inversão em si, é historicamente o sinal mais próximo da recessão efetiva.
4. Texto de alerta gerado automaticamente:
   - Se `Curve_Inverted = 1` e `Months_Inverted < 6`: *"Curva invertida há N meses — monitorar."*
   - Se `Curve_Inverted = 1` e `Months_Inverted ≥ 6`: *"Curva invertida há N meses — alerta elevado de recessão em 12 a 18 meses."*
   - Se `Des_Inversão = 1`: *"Curva acabou de desinverter após N meses invertida — historicamente o sinal mais próximo da recessão efetiva."*

Essa bandeira aparece no dashboard **ao lado** do regime do Módulo A, nunca substituindo-o — o objetivo é permitir a leitura "o modelo está classificando Expansão hoje, mas há um alerta de curva ativo há N meses", que é uma leitura mais rica do que qualquer um dos dois sinais isolados.

---

## 3. Módulo B — Risk-on / Risk-off

Se o Módulo A responde "em que fase do ciclo a economia está" — um sinal fundamentalista, atualizado mensalmente, que muda devagar — o Módulo B responde uma pergunta diferente e complementar: "o mercado, agora, está com apetite para correr risco ou está com medo?" É um sinal comportamental e de curto prazo, atualizado diariamente, que frequentemente se move antes (ou de forma independente) dos dados econômicos reais aparecerem. Por isso a padronização usa janela mais curta (2 anos em vez de 10) e frequência diária em vez de mensal: sentimento de mercado muda de semana em semana, o ciclo econômico muda de trimestre em trimestre.

### 3.1 Fontes de dados

Indicadores diários, combinando FRED (dados oficiais) e Yahoo Finance (via `yfinance`, para câmbio cruzado e commodities que não estão no FRED).

| Dimensão | Indicador | Fonte | Series ID / Ticker | Sinal de risk-on |
|---|---|---|---|---|
| Volatilidade | VIX | FRED (ou Yahoo) | `VIXCLS` / `^VIX` | VIX **baixo** → inverter sinal |
| Crédito | Spread Baa (Moody's) vs. Treasuries | FRED | `BAA10Y` | Spread **estreito** → inverter sinal |
| Câmbio (risco vs. refúgio) | AUD/JPY | Yahoo Finance | `AUDJPY=X` | Par **em alta** → sinal direto (não inverter) |
| Câmbio (refúgio) | JPY/USD | FRED | `DEXJPUS` | Ien **se apreciando** (`DEXJPUS` caindo) → inverter sinal |
| Taxa livre de risco | Treasury 10 anos | FRED | `DGS10` | Yields **em queda rápida** (flight-to-quality) → inverter sinal |
| Ouro (opcional, peso menor) | Ouro spot | Yahoo Finance | `GC=F` | Ambíguo — correlaciona também com juros reais e USD; usar com peso reduzido ou como razão Ouro/S&P500 |

**Nota sobre a mudança do spread de crédito (achado testando com dados reais):** a escolha original era `BAMLH0A0HYM2` (spread de high yield do ICE BofA), mas essa série tem uma restrição de licenciamento no FRED — a API só devolve os últimos 3 anos de histórico, mesmo pedindo dados desde 1990 (o site mostra o histórico completo, a API não, por acordo comercial entre o FRED e o provedor ICE Data Indices). Isso só apareceu ao testar com dados reais, não seria visível só lendo a documentação da série. Trocamos para `BAA10Y` (spread de crédito Baa da Moody's, sem essa restrição, histórico desde 1986) — mede a mesma ideia (prêmio de risco de crédito), com um universo de rating um pouco mais alto (Baa é o degrau mais baixo de "investment grade", não "high yield" propriamente, mas ainda sensível a estresse de crédito). Vale mencionar esse tipo de achado numa entrevista: é evidência de ter mesmo testado o pipeline contra dados reais, não só desenhado no papel.

**Racional de cada indicador — por que este e não outro:**

**VIX** é o indicador default de qualquer modelo de sentimento de mercado: mede quanto os investidores pagam por proteção via opções sobre o S&P 500, preço que dispara junto com a incerteza. É o sinal mais rápido e mais observado de pânico — difícil de justificar deixar de fora.

**Spread de crédito (`BAA10Y`)** mede quanto a mais de juros empresas com rating Baa pagam para se financiar, em relação a Treasuries. É o termômetro de quanto prêmio os investidores exigem para aceitar risco de crédito — e costuma "sentir" o estresse financeiro antes da bolsa de ações, porque reflete o mercado de dívida, não só o de ações.

**AUD/JPY** é o "termômetro" clássico de apetite ao risco em mesas de câmbio — AUD é moeda de risco (ligada a commodities e carry trade), JPY é moeda de funding/refúgio. Quando o par sobe, o mercado está comprando risco; quando cai, há fuga para segurança. É um proxy mais limpo do que olhar o USD isoladamente, porque o dólar pode subir tanto em risk-off (procurado como refúgio) quanto em risk-on (economia americana forte) — um sinal ambíguo, por isso não entrou como indicador principal.

**JPY/USD (`DEXJPUS`)** entra separado do AUD/JPY para isolar o lado "refúgio" do iene do lado "commodity" do dólar australiano — quando o iene se aprecia de forma mais ampla (não só contra o AUD), é um sinal adicional e mais "puro" de fuga para segurança.

**Treasury 10 anos (`DGS10`)** captura o comportamento clássico de *flight-to-quality*: em pânico, o mercado compra títulos do governo americano (o ativo mais seguro do mundo), empurrando o preço para cima e o yield para baixo. Uma queda rápida e abrupta do yield, fora do contexto de um dado econômico específico, costuma sinalizar medo.

**Ouro** entra com peso menor porque o sinal dele é mais "sujo" — reage tanto a sentimento de risco quanto a juros reais, força do dólar e demanda de bancos centrais. Funciona como reforço opcional, não como pilar do modelo.

### 3.2 Transformação em score numérico (-2 a +2)

1. **Padronização diária:** z-score de cada indicador com janela móvel *trailing* mais curta que o Módulo A (2 anos / ~500 dias úteis), porque regimes de mercado mudam mais rápido que o ciclo econômico.
2. **Inversão de sinal** onde aplicável (ver tabela acima), de forma que em todos os indicadores um z-score positivo signifique "mais risk-on".
3. **Composite:** média ponderada dos z-scores invertidos → `Score_Z` (peso igual para a maioria, peso reduzido para o ouro). **Importante na implementação:** o composite precisa tolerar indicadores com histórico mais curto que os outros (AUD/JPY e ouro só têm dado no Yahoo Finance a partir dos anos 2000) — se um único indicador ausente "contaminasse" o dia inteiro com valor vazio, o histórico anterior a essa data ficaria inutilizável. A solução é recalcular a média só entre os indicadores disponíveis naquele dia específico (com um mínimo de indicadores exigido, para não computar o composite a partir de um único sinal isolado).
4. **Discretização em escala -2 a +2:**

| Score_Z (z-score composto) | Score final | Interpretação |
|---|---|---|
| > 1,5 | **+2** | Risk-on forte |
| 0,5 a 1,5 | **+1** | Risk-on moderado |
| −0,5 a 0,5 | **0** | Neutro |
| −1,5 a −0,5 | **−1** | Risk-off moderado |
| < −1,5 | **−2** | Risk-off forte |

Cinco níveis em vez de um simples binário risk-on/risk-off porque a escala binária perderia informação de intensidade — um dia de VIX levemente elevado não é a mesma coisa que um VIX disparando como em março de 2020, e a resposta de alocação certa (reduzir um pouco vs. reduzir decisivamente) depende dessa diferença.

5. **Filtro de persistência (evitar ruído):** para diferenciar um sinal real de risk-off de um "susto" de um dia, exigir que o `Score_Z` permaneça do mesmo lado do zero por pelo menos **5 a 10 dias úteis consecutivos** antes de considerar que houve mudança de regime tático. Isso é o que dá sentido técnico à ideia de "risk-off temporário = ruído" que está na definição da matriz — sem essa regra, o modelo trocaria de estado o tempo todo e a Fase 2 (backtest) teria giro de carteira (turnover) irrealista.

---

## 4. Matriz de combinação

Cruzando os 4 regimes do Módulo A com 3 faixas do Módulo B (agrupando −2/−1 = Risk-off, 0 = Neutro, +1/+2 = Risk-on, já após o filtro de persistência):

| Ciclo \ Risco | Risk-on | Neutro | Risk-off |
|---|---|---|---|
| **Expansão** | Aumentar exposição a cíclicos/beta alto | Manter exposição-alvo | Risk-off temporário → manter posição, tratar como ruído (respeitando o filtro de persistência) |
| **Recuperação** | Aumentar exposição gradualmente, começar a rotacionar para cíclicos | Postura neutra, aguardar confirmação | Cautela — pode ser recuperação falsa; reduzir tamanho das posições |
| **Desaceleração** | Reduzir gradualmente, rotacionar para qualidade/defensivos | Reduzir exposição-alvo | Reduzir risco de forma decisiva |
| **Contração** | **Alerta** — possível "bear market rally"; não confiar no sinal tático sozinho | Reduzir risco de forma decisiva | Reduzir risco de forma decisiva (posição mais defensiva do framework) |

Esta tabela 4×3 é a versão completa; os quatro casos que você já tinha descrito (Expansão+risk-on, Expansão+risk-off temporário, Contração+risk-off, Contração+risk-on) são as células mais informativas dela e podem ser o foco da narrativa no dashboard, com as demais como preenchimento lógico.

---

## 5. Ferramentas (Python)

| Tarefa | Biblioteca | Observação |
|---|---|---|
| Puxar séries do FRED | `fredapi` (ou `pandas_datareader.data.DataReader(..., 'fred')`) | Precisa de uma API key gratuita em fredaccount.stlouisfed.org |
| Puxar câmbio/commodities fora do FRED | `yfinance` | Tickers: `AUDJPY=X`, `GC=F`, `^VIX` (como cross-check de `VIXCLS`) |
| Cálculo de z-score, agregação | `pandas` / `numpy` | Usar `.rolling(window, min_periods=...)` para evitar look-ahead |
| Exportação para Excel | `openpyxl` ou `pandas.ExcelWriter` | Gera a tabela de scores que alimenta o dashboard final no Excel |

---

## 6. Próximos passos sugeridos

1. Criar conta gratuita no FRED e gerar API key.
2. Escrever script Python que puxa as ~14 séries listadas acima e salva em CSV/Excel local.
3. Implementar as funções de z-score, agregação e classificação de regime (Módulo A e B separadamente) — validar visualmente contra recessões conhecidas (2001, 2008, 2020) antes de seguir em frente.
4. Exportar a série histórica de scores para Excel e montar o dashboard (tabela dinâmica + gráfico de regime ao longo do tempo + matriz 2x2 com o estado atual destacado).
5. Documentar decisões de design (as da Seção 1 acima) no README do GitHub — é o que diferencia o projeto de um dashboard genérico copiado de tutorial.
6. Só depois disso, seguir para a Fase 2 (regra de alocação sistemática + backtest).

---

## Fontes consultadas

- [Institute for Supply Management Data To Be Removed from FRED — St. Louis Fed](https://news.research.stlouisfed.org/2016/06/institute-for-supply-management-data-to-be-removed-from-fred/)
- [Chicago Fed National Activity Index: About the CFNAI](https://www.chicagofed.org/research/data/cfnai/about)
- [ICE BofA US High Yield Index Option-Adjusted Spread (BAMLH0A0HYM2) — FRED](https://fred.stlouisfed.org/series/BAMLH0A0HYM2)
- [CBOE Volatility Index: VIX (VIXCLS) — FRED](https://fred.stlouisfed.org/series/VIXCLS)
- [Nominal Broad U.S. Dollar Index (DTWEXBGS) — FRED](https://fred.stlouisfed.org/series/DTWEXBGS)
- [Japanese Yen to U.S. Dollar Spot Exchange Rate (DEXJPUS) — FRED](https://fred.stlouisfed.org/series/DEXJPUS)
- [Swiss Francs to U.S. Dollar Spot Exchange Rate (DEXSZUS) — FRED](https://fred.stlouisfed.org/series/DEXSZUS)
- [Current General Activity; Diffusion Index for Federal Reserve District 3: Philadelphia (GACDFSA066MSFRBPHI) — FRED](https://fred.stlouisfed.org/series/GACDFSA066MSFRBPHI)
