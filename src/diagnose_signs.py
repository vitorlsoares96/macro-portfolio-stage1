"""
Diagnostic script — checks whether Module B's sign inversion (invert_sign
in config.py) is pointing the right direction for each indicator, using
two well-documented, extreme risk-off events as reference points:

1. March 2020 (COVID panic) — already checked once; treasury_10y's
   invert_sign was found backwards and has been fixed in config.py.
   Re-running it here confirms the fix actually improves things.
2. 2008 (Lehman Brothers collapse, Sept 15, 2008) — a second, independent
   crisis, used specifically to check jpy_usd. March 2020 had an unusual
   "dash for cash" phase (global USD funding squeeze) that temporarily
   broke the classic "yen strengthens in risk-off" relationship — 2008
   also had real USD funding stress (the TED spread blew out, LIBOR-OIS
   spread spiked), so it won't perfectly isolate the "clean" yen-haven
   story either, but comparing the two episodes side by side should show
   whether jpy_usd's behavior is at least directionally consistent, or
   just as unstable as in 2020.

Reuses the real pipeline functions (fetch_module_b, calculate_trailing_zscore)
instead of reimplementing the logic separately, so this reflects exactly
what module_b.py actually does — no risk of the diagnostic itself having a
different bug than production code.

How to run:
    cd src
    python diagnose_signs.py
"""

import pandas as pd

from config import MODULE_B_FRED_SERIES, MODULE_B_YAHOO_TICKERS, START_DATE, MODULE_B_ZSCORE_WINDOW_DAYS
from module_b import fetch_module_b, calculate_module_b
from transformation import calculate_trailing_zscore

pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 10)
pd.set_option("display.float_format", "{:+.2f}".format)

# Add or edit windows here freely — each is (label, start, end).
WINDOWS = [
    ("Março 2020 (pânico do COVID)", "2020-02-15", "2020-04-15"),
    ("2008 (colapso do Lehman Brothers, 15/set)", "2008-08-01", "2008-12-01"),
]

print("Fetching Module B raw data (FRED + Yahoo Finance) — covers both windows in one pull...\n")
raw_df = fetch_module_b(START_DATE)
metadata = {**MODULE_B_FRED_SERIES, **MODULE_B_YAHOO_TICKERS}

# Step 1: individual z-score of each indicator, BEFORE any sign inversion —
# this is the raw statistical reading, exactly as the data naturally moves.
zscore_raw = pd.DataFrame({
    name: calculate_trailing_zscore(raw_df[name], window=MODULE_B_ZSCORE_WINDOW_DAYS, min_periods=60)
    for name in metadata
})

# Step 2: apply the sign inversion exactly as configured in config.py
# (invert_sign=True/False per indicator) — this is what the real pipeline
# uses to build the composite.
zscore_inverted = zscore_raw.copy()
for name, meta in metadata.items():
    if meta.get("invert_sign"):
        zscore_inverted[name] = -zscore_inverted[name]

print("invert_sign configurado atualmente, por indicador:")
for name, meta in metadata.items():
    print(f"  {name:15s} invert_sign={meta.get('invert_sign')}")
print()

module_b_result = calculate_module_b(start_date=START_DATE)

for label, window_start, window_end in WINDOWS:
    print("#" * 100)
    print(f"# JANELA: {label}  ({window_start} a {window_end})")
    print("#" * 100)

    print("\n--- Z-SCORE SEM INVERSÃO (dado bruto, direção natural da série) ---")
    print(zscore_raw.loc[window_start:window_end])

    print("\n--- Z-SCORE COM INVERSÃO (o que o pipeline usa hoje) ---")
    print(zscore_inverted.loc[window_start:window_end])

    print("\n--- Composite final (o que calculate_module_b devolve) ---")
    print(module_b_result.loc[window_start:window_end, ["z_score", "discrete_score", "filtered_score"]])
    print("\n")

print("=" * 100)
print("COMO LER O RESULTADO")
print("=" * 100)
print(
    "Nas duas janelas, esperamos que a maioria dos indicadores, já com a\n"
    "inversão aplicada, fique bem NEGATIVA (negativo = risk-off) — os dois\n"
    "períodos são crises de risk-off extremo e bem documentadas.\n"
    "\n"
    "O que queremos comparar especificamente é 'jpy_usd': se ele ficar\n"
    "negativo (após inversão) nas DUAS janelas de forma consistente, é um\n"
    "bom sinal de que a inversão está certa (o comportamento de 2020 foi só\n"
    "uma exceção pontual). Se ele continuar instável/positivo em 2008\n"
    "também, isso sugere que a relação em si é mais fraca/inconsistente do\n"
    "que o documento assume, e vale considerar dar menos peso a esse\n"
    "indicador (ou aceitar a inconsistência como limitação conhecida) em\n"
    "vez de simplesmente inverter o sinal.\n"
    "\n"
    "'treasury_10y' já foi corrigido (invert_sign=False agora) — deve\n"
    "aparecer negativo nas duas janelas sem exceção, já que os yields caem\n"
    "de forma bem mais consistente em crise do que o câmbio.\n"
)
