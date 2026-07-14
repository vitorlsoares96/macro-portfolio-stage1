"""
Excel export — the final piece of Phase 1.

This file doesn't calculate anything new. It just calls the pipelines
that already exist (Module A + context, Module B, action matrix) and
writes the result to a single .xlsx file, one sheet per piece. From
there, the work of building a manual dashboard (pivot tables, charts,
formatting) is up to you, directly in Excel — this script only delivers
the "clean data", it doesn't try to reproduce Excel inside Python.

Why merge Module A and context into a single sheet instead of two: the
two pieces are already monthly and already share the same date index
(context uses Module A's regime as an input), so it makes more sense for
whoever builds a pivot table to have one row per month with EVERYTHING
(score, regime, inflation, curve) than to have to cross-reference two
sheets.

How to run:
    cd src
    python export_excel.py
"""

import pandas as pd

from config import START_DATE
from transformation import calculate_module_a
from context import calculate_full_context
from module_b import calculate_module_b
from matrix import combine_modules
from dashboard import build_dashboard


def build_monthly_summary(start_date: str = START_DATE) -> pd.DataFrame:
    """
    Merges Module A (level_score, smoothed_score, momentum, regime) with
    the context layer (inflation trend, curve alert, narrative) into a
    single monthly table.

    Point worth understanding: `calculate_full_context` already receives
    Module A's regime as a parameter and returns it BACK as one of the
    result's columns (that's how the narrative manages to combine
    "regime + inflation trend" into a single sentence). This means that,
    if we merged the two DataFrames carelessly, we'd end up with two
    identical "regime" columns. `.drop(columns=["regime"])` removes that
    duplicate from the context side before the join, so only one is
    left.
    """
    module_a = calculate_module_a(start_date)
    context = calculate_full_context(module_a["regime"], start_date)

    context_without_duplicate_regime = context.drop(columns=["regime"])

    # .join() merges two DataFrames by their index (the date). Since
    # both already come with the same monthly index (context was
    # computed from module_a's regime), we don't need to pass any extra
    # parameter.
    summary = module_a.join(context_without_duplicate_regime)
    return summary


def export_to_excel(output_path: str = "phase1_dashboard.xlsx", start_date: str = START_DATE) -> None:
    """
    Runs the three pipelines (Module A+context, Module B, matrix) and
    writes everything into a single .xlsx file, one sheet per piece.

    `pd.ExcelWriter` works like an "open file for writing": each call to
    `.to_excel(writer, sheet_name=...)` writes to a different sheet of
    the SAME file, instead of overwriting it. The `with` block ensures
    the file is saved and closed correctly at the end, even if something
    goes wrong in the middle (the same pattern used for opening regular
    files in Python).

    `engine="openpyxl"` is the library pandas uses under the hood to
    generate the .xlsx — it needs to be installed in the environment
    (`pip install openpyxl`; already in requirements.txt).
    """
    print("Calculating Module A + context (monthly)...")
    monthly_summary = build_monthly_summary(start_date)

    print("Calculating Module B (daily)...")
    module_b = calculate_module_b(start_date)

    print("Combining both modules into the action matrix...")
    combined_matrix = combine_modules(monthly_summary["regime"], module_b["filtered_score"])

    print(f"Writing '{output_path}'...")
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        monthly_summary.to_excel(writer, sheet_name="Module_A_Monthly", index_label="date")
        module_b.to_excel(writer, sheet_name="Module_B_Daily", index_label="date")
        combined_matrix.to_excel(writer, sheet_name="Combined_Matrix", index_label="date")

        # freeze_panes = "B2" "freezes" the first row (header) and the
        # first column (the date) when scrolling the sheet — just a
        # comfort touch for anyone exploring the data manually in Excel.
        # writer.sheets is a dict {sheet_name: openpyxl worksheet
        # object}, available after .to_excel() has already written the
        # sheet.
        for sheet_name in ["Module_A_Monthly", "Module_B_Daily", "Combined_Matrix"]:
            writer.sheets[sheet_name].freeze_panes = "B2"

        print("Building the Dashboard sheet (charts, heatmap, status card)...")
        build_dashboard(writer, monthly_summary, combined_matrix)

    print("Done! Open the file in Excel to check it out.")


if __name__ == "__main__":
    export_to_excel()
