"""
Phase 1 final test script: runs the three modules (A, B, and the
combination matrix) end to end and shows the current reading, plus a
sanity check for March 2020 (should show Contraction + Risk-off, the
framework's most defensive action).

How to run:
    cd src
    python test_matrix.py
"""

import pandas as pd

from transformation import calculate_module_a
from module_b import calculate_module_b
from matrix import combine_modules
from config import START_DATE

pd.set_option("display.width", 160)
pd.set_option("display.max_columns", 10)
pd.set_option("display.max_colwidth", 70)


if __name__ == "__main__":
    print("Calculating Module A...")
    module_a = calculate_module_a(start_date=START_DATE)

    print("Calculating Module B...")
    module_b = calculate_module_b(start_date=START_DATE)

    print("Combining both modules...\n")
    combined = combine_modules(module_a["regime"], module_b["filtered_score"])

    print("Current reading (last 5 days):")
    print(combined[["regime", "risk", "action"]].tail(5))
    print()

    print("Sanity check — March 2020, expected: Contraction + Risk-off:")
    print(combined.loc["2020-03-15":"2020-03-25", ["regime", "risk", "action"]])
