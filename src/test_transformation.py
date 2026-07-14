"""
Test script: runs the complete Module A pipeline (raw data through
classified regime) and shows the recent result + a quick check against
the 2020 (COVID) recession, which we already know happened, to validate
whether the model "makes sense" before we trust it.

How to run:
    cd src
    python test_transformation.py
"""

import pandas as pd

from transformation import calculate_module_a
from config import START_DATE

# Show all columns without truncation, and more decimal places — just to
# make this visual check easier to read in the terminal.
pd.set_option("display.width", 120)
pd.set_option("display.max_columns", 10)


if __name__ == "__main__":
    print("Calculating Module A (this fetches ~6 series from FRED, may take a few seconds)...\n")
    result = calculate_module_a(start_date=START_DATE)

    print("Last 6 classified months:")
    print(result.tail(6))
    print()

    print("Sanity check — March to June 2020 (COVID), should show up as Contraction:")
    print(result.loc["2020-03-01":"2020-06-01"])
    print()

    print("Sanity check — 2021, should show up as Recovery or Expansion:")
    print(result.loc["2021-01-01":"2021-06-01"])
