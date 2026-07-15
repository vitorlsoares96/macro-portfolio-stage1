# Phase 1 — Technical Scope
## Economic Cycle Nowcasting + Risk-on/Risk-off (US)

**Project:** Macro & Quant Portfolio
**Geographic scope:** United States (single source: FRED + Yahoo Finance)
**Date:** July/2026

---

## 1. Design principles

Before the data sources, three methodological decisions worth stating explicitly — including in an interview, because they show the project was actually thought through, not just copied:

1. **Module A (nowcasting) measures activity, not price.** Following the design of the Chicago Fed National Activity Index (CFNAI), the cycle index is built from production, employment, and consumption indicators — inflation and the yield curve enter as a **context layer**, not inside the same average. Mixing everything into a single z-score reduces interpretability (a high CPI and a strong payroll print push the index in the same direction for opposite reasons). This separation is a design discussion point, not a technical detail.
2. **Regime = level × direction, not just level.** The four regimes (Expansion, Slowdown, Contraction, Recovery) only exist if the model has two axes: the score's *level* (above or below the historical average) and its *momentum* (rising or falling). It's the same principle behind the "growth cycle clock" the OECD uses in its Composite Leading Indicators (CLI level vs. 6-month rate of change).
3. **No look-ahead bias.** Every standardization (z-score) uses only data available up to that point in time (a *trailing* rolling window, never centered). This is mandatory because Phase 2 will backtest on top of these scores — if the z-score "looks into the future" when computed, the backtest is invalid before it even starts.

---

## 2. Module A — Economic Cycle (Nowcasting)

### 2.1 Data sources

Structure inspired by the CFNAI's 4 categories (production/income, employment, consumption, sales/orders), with all series freely available via the **FRED API**.

| Category | Indicator | Series ID (FRED) | Frequency | Suggested transformation |
|---|---|---|---|---|
| Production | Industrial Production | `INDPRO` | Monthly | YoY % change |
| Employment | Nonfarm Payrolls | `PAYEMS` | Monthly | Monthly change (thousands) |
| Employment | Unemployment Rate | `UNRATE` | Monthly | Level, inverted sign (decrease = positive) |
| Employment (high freq.) | Unemployment Insurance Claims | `ICSA` | Weekly | 4-week moving average, inverted sign |
| Consumption | Retail Sales | `RSAFS` | Monthly | YoY % change |
| Sales/orders (manufacturing proxy) | Philly Fed Business Outlook (Current General Activity) | `GACDFSA066MSFRBPHI` | Monthly | Level (already a diffusion index centered on 0) |

**Context layer (doesn't enter the average, but qualifies the regime):**

| Indicator | Series ID (FRED) | Use |
|---|---|---|
| Headline CPI | `CPIAUCSL` | YoY % change — distinguishes "disinflationary contraction" from "stagflation" |
| Core PCE (the Fed's preferred measure) | `PCEPILFE` | YoY % change — same use, it's the metric the FOMC watches |
| 10y-2y spread | `T10Y2Y` | Level — classic leading recession indicator (12-18 months ahead) |
| 10y-3m spread | `T10Y3M` | Level — the version preferred by the NY Fed for its recession-probability model |

**Note on the ISM Manufacturing PMI:** it's the most "recognizable" manufacturing sentiment indicator, but ISM [removed its historical data from FRED in 2016](https://news.research.stlouisfed.org/2016/06/institute-for-supply-management-data-to-be-removed-from-fred/) over licensing — today it's only available via paid subscription or as a free, standalone monthly number on the [ISM website](https://www.ismworld.org/supply-management-news-and-reports/reports/ism-pmi-reports/). Two options, without needing to pay for a subscription:
- **Option A (recommended for the MVP):** use the Philly Fed Business Outlook as a manufacturing sentiment proxy — it's free, has a long FRED series, and is historically correlated with the ISM.
- **Option B (optional enrichment):** manually enter the monthly ISM PMI value (takes 2 minutes a month, the number is published for free) to give the dashboard more credibility in interviews, without depending on it for the automated calculation.

### 2.2 Transformation into a numeric score

1. **Standardization (z-score):** for each indicator, compute `z = (value_t − trailing_rolling_mean) / trailing_rolling_std_dev`, with a 10-year (120-month) window when enough history exists, or an expanding window in the series' early years. This replicates the CFNAI's logic, which also standardizes each component before aggregating.
2. **Aggregation by category:** simple average of the z-scores within each category (Production, Employment, Consumption/Sales).
3. **Level composite:** average of the 3 categories → `Level_Score` (equivalent to the monthly CFNAI, but with 3 blocks instead of 4).
4. **Smoothing:** 3-month moving average of the composite (`Smoothed_Score`) — same logic as the CFNAI-MA3, to reduce month-to-month noise.
5. **Momentum:** change in `Smoothed_Score` over the last 3 months → `Momentum_Score`.
6. **Quadrant classification:**

| | Momentum > 0 (rising) | Momentum ≤ 0 (falling) |
|---|---|---|
| **Level > 0** (above historical average) | **Expansion** | **Slowdown** |
| **Level ≤ 0** (below historical average) | **Recovery** | **Contraction** |

As a calibration reference, the Chicago Fed itself uses `CFNAI-MA3 > −0.70` as the boundary between expansion and contraction — a defensible starting point for the "Level" axis threshold before calibrating with our own data.

### 2.3 Context layer: formal rules (inflation and yield curve)

These two variables don't enter the `Level_Score`/`Momentum_Score` calculation (Section 2.2) — they're computed separately and then attached to the already-classified regime, as a label. Below is the exact rule for each.

**a) Inflation trend**

1. Compute the 3-month change of each inflation series (already in % YoY, see Section 2.1):
   `ΔCPI = CPI_YoY_t − CPI_YoY_{t−3}`
   `ΔPCE = PCE_YoY_t − PCE_YoY_{t−3}`
2. Classify:
   - **Accelerating**, if `ΔCPI > 0` **and** `ΔPCE > 0` (both series confirm the same direction)
   - **Decelerating**, if `ΔCPI < 0` **and** `ΔPCE < 0`
   - **Mixed**, if the two series disagree (treated as an undefined signal — doesn't force a label when the data isn't clear)

Requiring CPI and Core PCE to agree is deliberate: they're two inflation measures with different methodologies, and using both as cross-confirmation prevents a single noisy month in one series from triggering a label on its own.

3. Cross `Inflation_Trend` with Module A's regime to generate the context narrative:

| Regime \ Inflation | Accelerating | Decelerating | Mixed |
|---|---|---|---|
| **Expansion** | Overheating alert — the Fed tends to tighten; the expansion may last less than the score suggests | Healthy expansion — growth without inflationary pressure, the most favorable scenario in the framework | Neutral expansion, no clear inflation signal |
| **Recovery** | Recovery with inflation still high — the Fed may keep rates restrictive and stall the rebound | Clean recovery — the Fed has room to cut rates and support the cycle | Neutral recovery |
| **Slowdown** | Slowdown with rising inflation — risk that the Fed can't act in time | Textbook slowdown — the Fed gains room to cut rates preemptively | Neutral slowdown |
| **Contraction** | **Stagflation** — the most dangerous scenario in the framework, the Fed has no room to maneuver | Disinflationary contraction — the "standard" recession scenario, the Fed has room to act | Neutral contraction |

**b) Yield curve alert**

1. Define month-to-month inversion: `Curve_Inverted_t = 1` if `T10Y2Y_t < 0` **or** `T10Y3M_t < 0`; otherwise, `0`. (The two series often diverge by weeks — report both on the dashboard, not just one, since `T10Y3M` is the one preferred by the NY Fed's recession-probability model and `T10Y2Y` is the one most cited by the market.)
2. Count consecutive inverted months: `Months_Inverted` (resets to zero whenever `Curve_Inverted` goes back to `0`).
3. Flag the **uninversion** event: `Uninversion_t = 1` when `Curve_Inverted_{t−1} = 1` and `Curve_Inverted_t = 0` — i.e., the spread just went back to positive after a negative period. This event, not the inversion itself, is historically the signal closest to the actual recession.
4. Automatically generated alert text:
   - If `Curve_Inverted = 1` and `Months_Inverted < 6`: *"Curve inverted for N months — monitor."*
   - If `Curve_Inverted = 1` and `Months_Inverted ≥ 6`: *"Curve inverted for N months — elevated recession alert in 12 to 18 months."*
   - If `Uninversion = 1`: *"Curve just uninverted after N months inverted — historically the signal closest to the actual recession."*

This flag appears on the dashboard **alongside** Module A's regime, never replacing it — the goal is to allow a reading like "the model is classifying Expansion today, but there's been an active curve alert for N months", which is a richer reading than either signal alone.

---

## 3. Module B — Risk-on / Risk-off

If Module A answers "what phase of the cycle is the economy in" — a fundamentals-based signal, updated monthly, that changes slowly — Module B answers a different, complementary question: "is the market, right now, hungry for risk or scared?" It's a behavioral, short-term signal, updated daily, that frequently moves before (or independently of) real economic data showing up. That's why the standardization uses a shorter window (2 years instead of 10) and daily instead of monthly frequency: market sentiment changes week to week, the economic cycle changes quarter to quarter.

### 3.1 Data sources

Daily indicators, combining FRED (official data) and Yahoo Finance (via `yfinance`, for cross-currency pairs and commodities not on FRED).

| Dimension | Indicator | Source | Series ID / Ticker | Risk-on signal |
|---|---|---|---|---|
| Volatility | VIX | FRED (or Yahoo) | `VIXCLS` / `^VIX` | VIX **low** → invert signal |
| Credit | Baa spread (Moody's) vs. Treasuries | FRED | `BAA10Y` | Spread **narrow** → invert signal |
| FX (risk vs. haven) | AUD/JPY | Yahoo Finance | `AUDJPY=X` | Pair **rising** → direct signal (don't invert) |
| FX (haven) | JPY/USD | FRED | `DEXJPUS` | Yen **depreciating** (`DEXJPUS` rising) → direct signal (don't invert) |
| Risk-free rate | 10-year Treasury | FRED | `DGS10` | Yields **rising** → direct signal (don't invert) |
| Gold (optional, lower weight) | Spot gold | Yahoo Finance | `GC=F` | Ambiguous — also correlates with real rates and USD strength; use with reduced weight or as a Gold/S&P500 ratio |

**Note on the credit spread change (found while testing with real data):** the original choice was `BAMLH0A0HYM2` (ICE BofA high-yield spread), but that series has a licensing restriction on FRED — the API only returns the last 3 years of history, even when requesting data back to 1990 (the website shows the full history, the API doesn't, due to a commercial agreement between FRED and the provider, ICE Data Indices). This only showed up when testing with real data, and wouldn't have been visible just from reading the series documentation. We switched to `BAA10Y` (Moody's Baa credit spread, without this restriction, history back to 1986) — it measures the same idea (credit risk premium), with a slightly higher rating universe (Baa is the lowest rung of "investment grade", not "high yield" proper, but still sensitive to credit stress). Worth mentioning this kind of finding in an interview: it's evidence of actually having tested the pipeline against real data, not just designed it on paper.

**Note on the JPY/USD and 10-year Treasury sign correction (found while validating the pipeline against real historical crises):** both rows above originally read "invert signal", inherited from an earlier draft of this table that (inconsistently with the AUD/JPY row) described the *risk-off* condition — "yen appreciating", "yields falling fast" — in the "risk-on signal" column, which reversed the intended direction once implemented in code. Diagnosed by isolating each indicator's individual z-score against March 2020 and the Sept-Dec 2008 Lehman Brothers collapse: `treasury_10y` was unambiguous in both windows (DGS10 fell steadily and consistently in both crises — the cleanest signal of all six indicators). `jpy_usd` needed the second window to resolve — March 2020 alone was ambiguous because of the "dash for cash" (Mar 9-24, 2020, a global USD funding squeeze that made the dollar spike against nearly everything, including JPY, temporarily breaking the usual haven relationship), but 2008 (with no such funding squeeze distorting the currency) showed the textbook relationship holding cleanly for the full ~4-month window. Full writeup in the README's "Real technical challenges" section.

**Rationale for each indicator — why this one and not another:**

**VIX** is the default indicator of any market-sentiment model: it measures how much investors pay for protection via S&P 500 options, a price that spikes along with uncertainty. It's the fastest and most-watched panic signal — hard to justify leaving out.

**Credit spread (`BAA10Y`)** measures how much extra interest Baa-rated companies pay to borrow, relative to Treasuries. It's the thermometer for how much premium investors demand to accept credit risk — and tends to "feel" financial stress before the stock market does, because it reflects the debt market, not just equities.

**AUD/JPY** is the classic risk-appetite "thermometer" on FX desks — AUD is a risk currency (tied to commodities and carry trade), JPY is a funding/haven currency. When the pair rises, the market is buying risk; when it falls, there's a flight to safety. It's a cleaner proxy than looking at the USD alone, because the dollar can rise both in risk-off (sought as a haven) and in risk-on (strong US economy) — an ambiguous signal, which is why it wasn't included as a primary indicator.

**JPY/USD (`DEXJPUS`)** is included separately from AUD/JPY to isolate the yen's "haven" side from the Australian dollar's "commodity" side — when the yen appreciates more broadly (not just against the AUD), it's an additional and "purer" flight-to-safety signal.

**10-year Treasury (`DGS10`)** captures classic *flight-to-quality* behavior: in a panic, the market buys US government bonds (the world's safest asset), pushing the price up and the yield down. A sharp, abrupt drop in yield, outside the context of a specific economic data release, tends to signal fear.

**Gold** carries a lower weight because its signal is "dirtier" — it reacts to risk sentiment as well as real rates, dollar strength, and central bank demand. It works as optional reinforcement, not as a pillar of the model.

### 3.2 Transformation into a numeric score (-2 to +2)

1. **Daily standardization:** z-score of each indicator with a shorter *trailing* rolling window than Module A (2 years / ~500 business days), because market regimes change faster than the economic cycle.
2. **Sign inversion** where applicable (see table above), so that a positive z-score always means "more risk-on" across every indicator.
3. **Composite:** weighted average of the inverted z-scores → `Z_Score` (equal weight for most, reduced weight for gold). **Important implementation note:** the composite needs to tolerate indicators with shorter history than the others (AUD/JPY and gold only have Yahoo Finance data starting in the 2000s) — if a single missing indicator "contaminated" the whole day with an empty value, all history before that date would become unusable. The fix is to recompute the average using only the indicators available on that specific day (with a minimum number of indicators required, so the composite isn't computed from a single isolated signal).
4. **Discretization into a -2 to +2 scale:**

| Z_Score (composite z-score) | Final score | Interpretation |
|---|---|---|
| > 1.5 | **+2** | Strong risk-on |
| 0.5 to 1.5 | **+1** | Moderate risk-on |
| −0.5 to 0.5 | **0** | Neutral |
| −1.5 to −0.5 | **−1** | Moderate risk-off |
| < −1.5 | **−2** | Strong risk-off |

Five levels instead of a simple binary risk-on/risk-off because the binary scale would lose intensity information — a day of slightly elevated VIX isn't the same thing as VIX spiking like it did in March 2020, and the right allocation response (reduce a bit vs. reduce decisively) depends on that difference.

5. **Persistence filter (avoid noise):** to tell a real risk-off signal apart from a one-day "scare", require `Z_Score` to stay on the same side of zero for at least **5 to 10 consecutive business days** before considering a tactical regime change to have occurred. This is what gives technical meaning to the "temporary risk-off = noise" idea baked into the matrix definition — without this rule, the model would flip state constantly and Phase 2 (backtest) would show unrealistic portfolio turnover.

---

## 4. Combination matrix

Crossing Module A's 4 regimes with Module B's 3 bands (grouping −2/−1 = Risk-off, 0 = Neutral, +1/+2 = Risk-on, already after the persistence filter):

| Cycle \ Risk | Risk-on | Neutral | Risk-off |
|---|---|---|---|
| **Expansion** | Increase exposure to cyclicals/high beta | Maintain target exposure | Temporary risk-off → hold position, treat as noise (respecting the persistence filter) |
| **Recovery** | Increase exposure gradually, start rotating into cyclicals | Neutral stance, wait for confirmation | Caution — may be a false recovery; reduce position size |
| **Slowdown** | Reduce gradually, rotate into quality/defensives | Reduce target exposure | Cut risk decisively |
| **Contraction** | **Alert** — possible "bear market rally"; don't trust the tactical signal alone | Cut risk decisively | Cut risk decisively (the framework's most defensive stance) |

This 4×3 table is the complete version; the four cases already described (Expansion+risk-on, Expansion+temporary risk-off, Contraction+risk-off, Contraction+risk-on) are its most informative cells and can be the focus of the dashboard narrative, with the rest as logical filler.

---

## 5. Tools (Python)

| Task | Library | Note |
|---|---|---|
| Pull FRED series | `fredapi` (or `pandas_datareader.data.DataReader(..., 'fred')`) | Needs a free API key from fredaccount.stlouisfed.org |
| Pull FX/commodities outside FRED | `yfinance` | Tickers: `AUDJPY=X`, `GC=F`, `^VIX` (as a cross-check against `VIXCLS`) |
| z-score calculation, aggregation | `pandas` / `numpy` | Use `.rolling(window, min_periods=...)` to avoid look-ahead |
| Export to Excel | `openpyxl` or `pandas.ExcelWriter` | Generates the scores table that feeds the final Excel dashboard |

---

## 6. Suggested next steps

1. Create a free FRED account and generate an API key.
2. Write a Python script that pulls the ~14 series listed above and saves them to a local CSV/Excel file.
3. Implement the z-score, aggregation, and regime classification functions (Module A and B separately) — validate visually against known recessions (2001, 2008, 2020) before moving on.
4. Export the historical score series to Excel and build the dashboard (pivot table + regime-over-time chart + 2x2 matrix with the current state highlighted).
5. Document the design decisions (the ones in Section 1 above) in the GitHub README — that's what sets the project apart from a generic dashboard copied from a tutorial.
6. Only after that, move on to Phase 2 (systematic allocation rule + backtest).

---

## Sources consulted

- [Institute for Supply Management Data To Be Removed from FRED — St. Louis Fed](https://news.research.stlouisfed.org/2016/06/institute-for-supply-management-data-to-be-removed-from-fred/)
- [Chicago Fed National Activity Index: About the CFNAI](https://www.chicagofed.org/research/data/cfnai/about)
- [ICE BofA US High Yield Index Option-Adjusted Spread (BAMLH0A0HYM2) — FRED](https://fred.stlouisfed.org/series/BAMLH0A0HYM2)
- [CBOE Volatility Index: VIX (VIXCLS) — FRED](https://fred.stlouisfed.org/series/VIXCLS)
- [Nominal Broad U.S. Dollar Index (DTWEXBGS) — FRED](https://fred.stlouisfed.org/series/DTWEXBGS)
- [Japanese Yen to U.S. Dollar Spot Exchange Rate (DEXJPUS) — FRED](https://fred.stlouisfed.org/series/DEXJPUS)
- [Swiss Francs to U.S. Dollar Spot Exchange Rate (DEXSZUS) — FRED](https://fred.stlouisfed.org/series/DEXSZUS)
- [Current General Activity; Diffusion Index for Federal Reserve District 3: Philadelphia (GACDFSA066MSFRBPHI) — FRED](https://fred.stlouisfed.org/series/GACDFSA066MSFRBPHI)
