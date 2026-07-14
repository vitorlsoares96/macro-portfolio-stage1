# Macro & Quant Portfolio — Phase 1

**US economic cycle nowcasting + market risk-on/risk-off score, combined into a single action matrix.**

This is the first of three modules of a portfolio project (Phase 1 —
nowcasting; Phase 2 — systematic allocation + backtest; Phase 3 —
VaR/stress test), built for a career transition into finance/macro. The
full rationale behind every design decision is formalized in
[`Phase1_Technical_Scope_Nowcasting_RiskOnOff.md`](Phase1_Technical_Scope_Nowcasting_RiskOnOff.md);
this README summarizes the "why" of each piece and documents the real
problems found while building the pipeline — the part that usually
doesn't show up in a tutorial.

## Just want to see the result, without installing anything?

The file [`src/phase1_dashboard.xlsx`](src/phase1_dashboard.xlsx) is a
ready-made snapshot of the pipeline — you can download it and open it
directly in Excel, with no need for Python, an API key, or any
installation. It's updated manually every once in a while (not in real
time), so the data may be a few days or weeks stale — to know exactly
when it was last updated, click "History" on the file's page on GitHub,
which shows the date of the most recent commit that changed it. If you
want today's actual data, see "How to run" below.

## What the project does

Two independent modules, each answering a different question:

- **Module A — what phase of the economic cycle is the US in?**
  Classifies the current moment into 4 regimes (Expansion / Recovery /
  Slowdown / Contraction), using monthly activity indicators (production,
  employment, consumption), with an extra context layer (inflation and
  the yield curve) that qualifies — but doesn't alter — that
  classification.
- **Module B — is the market risk-hungry or defensive, right now?** A
  daily score from -2 to +2, combining 6 market risk indicators
  (volatility, credit, FX, rates, gold).

The two are crossed into a **4×3 matrix of 12 recommended actions** — the
regime gives the strategic view (where we are in the cycle), the tactical
risk gives the timing (is the market already pricing this in?).

## Methodology — summary of design decisions

Full coverage is in Sections 1–4 of the scope document; here's the
summary of each "why":

**Why separate economic activity (Module A) from market pricing (Module
B) instead of a single score?** Because they answer different questions
and can disagree on purpose — e.g. cycle in Contraction but the market
already Risk-on, pricing in a recovery (the "bear market rally" cell of
the matrix). Mixing the two into a single number would hide exactly this
kind of signal.

**Why level × momentum instead of just level?** Level alone (score above
or below the historical average) doesn't distinguish "expansion losing
steam" from "contraction gaining steam" — two moments with opposite
outlooks that would have the same level score. Crossing level with
momentum (direction of the smoothed score over the last 3 months) solves
this with a 2×2 table.

**Why does the context layer (inflation, yield curve) stay outside the
regime average?** Inflation and the yield curve are useful to *qualify*
the regime (e.g. "expansion with accelerating inflation" is more fragile
than "expansion with falling inflation"), but they aren't activity
measures — throwing them into the same average as the production/
employment/consumption indicators would mix "how much the economy is
growing" with "how sustainable that is", two different questions.

**Why a trailing rolling-window z-score, never centered?** Any
standardization that "looks into the future" (a centered window, or one
computed from the full history at once) introduces look-ahead bias — the
model would have information in 2015 that only existed because we know
what happened in 2020. The entire pipeline deliberately uses a trailing
`.rolling()`.

**Why does Module B use a persistence filter (5 days)?** Without it, a
single day of noisy data (not a real shock) could make the tactical
reading "flicker" between risk-on and risk-off, generating noise nobody
would actually follow. The filter only confirms a side change after the
signal has held in the same direction for 5 consecutive business days.

**Why different weights in Module B (gold weighted at 0.5)?** Gold reacts
both to risk-off and to inflation — it's a "noisier" signal for this
specific purpose than the other 5 indicators, so it carries less weight
in the average instead of being excluded.

## Real technical challenges (not theory — things that broke and how they were fixed)

This section exists on purpose: it shows the building process, not just
the final result.

- **Data licensing restriction discovered in production.** The original
  high-yield spread series (`BAMLH0A0HYM2`, ICE BofA) only returns the
  last 3 years through the FRED API, even when requesting history back
  to 1990 — a real licensing restriction from the provider, visible only
  when actually pulling the data (the FRED website shows the full
  history, the API doesn't). Fixed by switching to `BAA10Y` (Moody's Baa
  credit spread, without this restriction) and making the composite
  calculation tolerant to indicators with histories of different
  lengths.
- **NaN-propagation bug in the weighted composite.** The first version
  summed the indicator series one at a time with pandas' `+` operator,
  which propagates `NaN`: a single indicator missing data on a given date
  "contaminated" the entire composite for that date, even with the other
  5 indicators valid. Fixed by using `DataFrame.sum(axis=1)` (which
  ignores `NaN` by default) and renormalizing the weights per row, using
  only the indicators available on that day.
- **`.resample("D").ffill()` vs. `.reindex(..., method="ffill")`.** When
  spreading Module A's monthly regime onto Module B's daily index,
  `.resample().ffill()` only fills forward up to the last date already
  present in the monthly series — days in the current month (before the
  next monthly data point comes out) were left `NaN`. `.reindex()` keeps
  filling forward indefinitely.
- **Curve-inversion month counter "resetting" in the wrong month.** The
  consecutive-months-inverted counter (via `groupby().cumsum()`) resets
  in the same month the curve uninverts — the alert message used that
  already-zeroed value, saying "uninverted after 0 months". Fixed by
  using the counter's value from the *previous* month (`.shift(1)`)
  specifically for that message.
- **`yfinance` returning a `MultiIndex` even for 1 ticker.** Recent
  versions sometimes return two-level columns (price × ticker) even when
  requesting a single symbol, breaking the conversion to `Series`. Fixed
  with `.squeeze("columns")`.
- **A chart axis bug only found visually.** A scatter chart (level ×
  momentum) was reading the date column as the X axis instead of the
  score — the Excel file was generated with no errors, only the chart
  came out wrong. It was only found by rendering the file and comparing
  it visually (not a test caught by numeric asserts). Reinforces the
  lesson: a code-generated chart also needs visual inspection, not just
  "ran without an exception".

## Project structure

```
macro_portfolio/
├── Phase1_Technical_Scope_Nowcasting_RiskOnOff.md   # full rationale behind every decision
├── README.md                                         # this file
├── requirements.txt
├── .env.example            # credentials file template (copy to .env)
├── .gitignore               # ensures .env never goes to GitHub
├── src/
│   ├── config.py             # every series/ticker used, in one place
│   ├── data_ingestion.py     # fetches raw data from FRED and Yahoo Finance
│   ├── transformation.py     # Module A: z-score, aggregation, regime
│   ├── context.py            # inflation + yield curve layer
│   ├── module_b.py           # Module B: composite, discretization, persistence
│   ├── matrix.py              # crosses both modules into the action matrix
│   ├── export_excel.py       # exports the 3 results to a .xlsx
│   ├── dashboard.py          # extra Excel tab with charts/heatmap (optional)
│   └── test_*.py             # one test script per module, each with a
│                              # sanity check against a real historical event
└── diagram/
    └── generate_diagram.py   # generates diagram_phase1.html — a visual map
                                # of the full pipeline (indicator → action)
```

## How to run

### 1. Prerequisites

- Python 3.10+
- Free FRED API key: https://fredaccount.stlouisfed.org/apikeys

### 2. Virtual environment

```bash
python -m venv venv
```

Activate it — the exact command depends on which terminal you're using:

```bash
# Git Bash on Windows (what this project's instructions assume):
source venv/Scripts/activate

# PowerShell or Command Prompt (cmd.exe) on Windows:
venv\Scripts\activate

# Mac/Linux (any terminal):
source venv/bin/activate
```

Note the difference between the first two: Git Bash simulates a Linux-style
shell even on Windows, so it uses forward slashes and needs `source` in
front (the script needs to be "loaded into" the current terminal, not run
as a separate program). PowerShell/cmd.exe use Windows' native backslash
paths and don't need `source`. Mixing the two (e.g. running
`venv\Scripts\activate` inside Git Bash) will fail, since Git Bash reads
backslashes as an escape character, not a path separator.

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure the key

```bash
cp .env.example .env
```

Then edit `.env` and paste in the key you generated in step 1.

### 5. Validate the pipeline, module by module

```bash
cd src
python test_ingestion.py       # confirms the raw data comes through
python test_transformation.py  # Module A — checks against Covid and 2021
python test_context.py         # checks against the 2022-23 rate-hike cycle
python test_module_b.py        # Module B — checks against Covid
python test_matrix.py          # combined matrix — current reading + Covid
```

### 6. Generate the Excel file and the diagram

```bash
python export_excel.py                 # generates phase1_dashboard.xlsx (3 data tabs)
cd ../diagram
python generate_diagram.py               # generates diagram_phase1.html
```

`diagram_phase1.html` is self-contained — it opens in any browser, no
need to run anything. It's the easiest material to show in an interview:
it visually maps the 12 raw indicators all the way to the 12 final
actions of the matrix.

### 7. Update the snapshot published on GitHub

The repository's `src/phase1_dashboard.xlsx` (see section above) only
updates when someone generates a new one and pushes it manually. After
running step 6 again, to publish the new version:

```bash
git add src/phase1_dashboard.xlsx
git commit -m "Update Excel snapshot"
git push
```

## Common issues

- `RuntimeError: FRED_API_KEY not found` → check that the file is named
  exactly `.env` (not `.env.txt` — some editors add that extension
  without warning) and that it's at the project root (not inside `src/`).
- `ModuleNotFoundError` → the virtual environment wasn't activated before
  running the script, or `pip install -r requirements.txt` didn't finish
  without errors — scroll up in the terminal and check whether any
  install failed.
- Error coming from `yfinance` (`Close` not found, or empty data) →
  sometimes Yahoo Finance rate-limits repeated requests in a short
  period; wait a minute and try again.

## Known limitations

- The context layer (inflation) has no reading for the most recent
  months due to real publication lag of CPI/Core PCE (~1 month delay) —
  it's not a bug, it's the nature of the data.
- The pipeline fetches live data from the API on every run (no local disk
  cache yet) — every run depends on FRED and Yahoo Finance being up.
- The weight of each indicator (Module A and B) was set by documented
  qualitative judgment in the technical scope, not statistically
  optimized — a deliberate choice for Phase 1 (avoiding overfitting a
  framework that doesn't yet have return data to validate against).

## Next steps

Phase 2: turn the matrix reading (regime + risk) into a systematic
asset-class allocation rule, and run a historical backtest to measure
whether these 12 actions would actually have added value since 1990.
Phase 3: VaR / stress-test framework on the resulting portfolio.
