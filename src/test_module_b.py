"""
Test script: runs Module B (risk-on/risk-off) and does a sanity check
against March 2020 (COVID market panic) — one of the most extreme and
well-documented risk-off events in recent history. Also shows a calmer
period for contrast.

How to run:
    cd src
    python test_module_b.py
"""

import pandas as pd

from module_b import calculate_module_b
from config import START_DATE

pd.set_option("display.width", 120)
pd.set_option("display.max_columns", 10)


if __name__ == "__main__":
    print("Calculating Module B (fetches 4 series from FRED + 2 from Yahoo Finance, may take a bit)...\n")
    result = calculate_module_b(start_date=START_DATE)

    print("Last 10 business days:")
    print(result.tail(10))
    print()

    print("Sanity check — March 2020 (COVID panic), "
          "expected: z_score strongly negative, discrete_score near -2:")
    print(result.loc["2020-03-01":"2020-03-31"])
    print()

    print("Contrast — a calmer period (second half of 2019), "
          "expected: scores close to 0, no extremes:")
    print(result.loc["2019-07-01":"2019-08-31"].iloc[::5])  # every 5 days, to avoid clutter
