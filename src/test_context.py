"""
Test script: runs the context layer (inflation + yield curve) and joins
it with Module A's regime, showing the recent months and a sanity check
for 2022-2023 (the Fed's monetary tightening cycle, when the yield curve
stayed inverted for a long, well-known period).

How to run:
    cd src
    python test_context.py
"""

import pandas as pd

from transformation import calculate_module_a
from context import calculate_full_context
from config import START_DATE

pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 10)
pd.set_option("display.max_colwidth", 70)


if __name__ == "__main__":
    print("Calculating Module A...")
    module_a = calculate_module_a(start_date=START_DATE)

    print("Calculating the context layer (inflation + yield curve)...\n")
    context = calculate_full_context(module_a["regime"], start_date=START_DATE)

    print("Last 6 months — regime + narrative:")
    print(context[["regime", "inflation_trend", "narrative"]].tail(6))
    print()

    print("Last 6 months — curve alert:")
    print(context[["curve_inverted", "months_inverted", "uninversion", "curve_alert"]].tail(6))
    print()

    print("Sanity check — 2022 to 2023 (Fed monetary tightening cycle, "
          "the curve should show up inverted for most of this period):")
    print(context.loc["2022-07-01":"2023-06-01", ["curve_inverted", "months_inverted", "curve_alert"]])
