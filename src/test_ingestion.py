"""
Test script: validates that data ingestion is working end to end, before
we move on to the next steps of the pipeline (z-score transformation,
regime classification).

How to run (after configuring .env with your FRED key — see README.md at
the project root):

    cd src
    python test_ingestion.py

If something goes wrong, copy the full error message and send it to me —
that's how we'll debug it together.
"""

from data_ingestion import fetch_fred_series, fetch_multiple_fred_series
from config import MODULE_A_SERIES, START_DATE


if __name__ == "__main__":
    # The `if __name__ == "__main__":` block is a Python convention that
    # means "only run this code if this file is executed directly
    # (python test_ingestion.py), not if it's imported by another file".
    # This matters because this file also defines (indirectly, by
    # importing data_ingestion) reusable functions — we don't want the
    # test to run every time another script just wants to use a function
    # from here.

    print("Test 1: fetching a single series (Industrial Production, INDPRO)...")
    industrial = fetch_fred_series("INDPRO", start_date=START_DATE)
    print(industrial.tail())  # .tail() shows the last rows = the most recent data
    print(f"Total observations: {len(industrial)}")
    print()

    print("Test 2: fetching all Module A series at once...")
    module_a = fetch_multiple_fred_series(MODULE_A_SERIES, start_date=START_DATE)
    print(module_a.tail())
    print(f"\nDataFrame shape (rows, columns): {module_a.shape}")
    print("\nIf you're seeing real numbers above (not errors), FRED ingestion is working.")
