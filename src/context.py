"""
Module A context layer — inflation and yield curve.

Implements Section 2.3 of the technical scope document: rules that do
NOT enter the regime calculation (that's in transformation.py), but that
qualify that regime with an extra risk/context label.
"""

import pandas as pd

from config import CONTEXT_SERIES, START_DATE
from transformation import build_monthly_series


def fetch_context(start_date: str = START_DATE) -> pd.DataFrame:
    """
    Fetches the 4 context series (CPI, core PCE, 10y-2y spread, 10y-3m
    spread), already transformed and aligned at monthly frequency.

    Reuses `build_monthly_series` from the transformation module — the
    same function we use for Module A works here with no changes at all,
    because it only depends on the metadata dict (fred_id,
    transformation, frequency), not on which "module" the series belongs
    to. This is the payoff of having separated responsibilities well
    from the start: write once, reuse later.
    """
    columns = {
        name: build_monthly_series(name, meta, start_date)
        for name, meta in CONTEXT_SERIES.items()
    }
    return pd.DataFrame(columns)


def calculate_inflation_trend(context_df: pd.DataFrame) -> pd.Series:
    """
    Classifies the inflation trend (Section 2.3-a of the document):
    compares today's value with the value 3 months ago — the "speed of
    inflation", not its level — requiring CPI and Core PCE to agree on
    direction before labeling. If they disagree, the result is "Mixed"
    (undefined signal), on purpose, so as not to force a clear reading
    when the data isn't clear.
    """
    cpi_delta = context_df["cpi"] - context_df["cpi"].shift(3)
    pce_delta = context_df["core_pce"] - context_df["core_pce"].shift(3)

    def classify(d_cpi, d_pce):
        if pd.isna(d_cpi) or pd.isna(d_pce):
            return None
        if d_cpi > 0 and d_pce > 0:
            return "Accelerating"
        elif d_cpi < 0 and d_pce < 0:
            return "Decelerating"
        else:
            return "Mixed"

    return pd.Series(
        [classify(c, p) for c, p in zip(cpi_delta, pce_delta)],
        index=context_df.index,
        name="inflation_trend",
    )


def calculate_curve_alert(context_df: pd.DataFrame) -> pd.DataFrame:
    """
    Implements the yield-curve alert rule (Section 2.3-b of the
    document): detects inversion (T10Y2Y or T10Y3M negative), counts
    consecutive inverted months, and flags the uninversion event —
    historically the signal closest to the actual recession, more so
    than the inversion itself.
    """
    inverted = (context_df["yield_curve_10y2y"] < 0) | (context_df["yield_curve_10y3m"] < 0)

    # Classic pandas trick for "count consecutive runs of True": every
    # time `inverted` is False, we start a new "group" (via cumsum of
    # the opposite); within each group, we sum up the accumulated True
    # values. The result: a counter that resets to zero every time the
    # curve stops being inverted, and starts climbing 1, 2, 3... again
    # for as long as it stays inverted.
    group = (~inverted).cumsum()
    months_inverted = inverted.groupby(group).cumsum()

    # Uninversion: it was inverted last month (shift(1)) and is no
    # longer inverted this month.
    uninversion = inverted.shift(1, fill_value=False) & (~inverted)

    # Bug found testing with synthetic data: in the month the curve
    # uninverts, `months_inverted` has already reset to zero (because the
    # counter resets in the same month `inverted` turns False) — so the
    # message said "after 0 months inverted", which is wrong. What we
    # want to show is how many months it WAS inverted before uninverting,
    # i.e. the counter's value in the PREVIOUS month (`.shift(1)`).
    months_before_uninversion = months_inverted.shift(1, fill_value=0)

    def alert_text(inv, months, uninv, months_before):
        if uninv:
            return (
                f"Curve just uninverted after {int(months_before)} months inverted — "
                "historically the signal closest to the actual recession."
            )
        if inv and months >= 6:
            return f"Curve inverted for {int(months)} months — elevated recession alert in 12 to 18 months."
        if inv:
            return f"Curve inverted for {int(months)} months — monitor."
        return "Curve normal (not inverted)."

    alert = [
        alert_text(inv, months, uninv, months_before)
        for inv, months, uninv, months_before in zip(
            inverted, months_inverted, uninversion, months_before_uninversion
        )
    ]

    return pd.DataFrame(
        {
            "curve_inverted": inverted,
            "months_inverted": months_inverted,
            "uninversion": uninversion,
            "curve_alert": alert,
        },
        index=context_df.index,
    )


# Regime x inflation-trend narrative table — the same 4x3 table from
# Section 2.3-a of the document, now as a Python dict. The key is a
# (regime, inflation_trend) tuple; the value is the explanatory sentence.
INFLATION_NARRATIVE = {
    ("Expansion", "Accelerating"): "Overheating alert — the Fed tends to tighten; the expansion may last less than the score suggests.",
    ("Expansion", "Decelerating"): "Healthy expansion — growth without inflationary pressure, the most favorable scenario in the framework.",
    ("Expansion", "Mixed"): "Neutral expansion, no clear inflation signal.",
    ("Recovery", "Accelerating"): "Recovery with inflation still high — the Fed may keep rates restrictive and stall the rebound.",
    ("Recovery", "Decelerating"): "Clean recovery — the Fed has room to cut rates and support the cycle.",
    ("Recovery", "Mixed"): "Neutral recovery.",
    ("Slowdown", "Accelerating"): "Slowdown with rising inflation — risk that the Fed can't act in time.",
    ("Slowdown", "Decelerating"): 'Textbook slowdown — the Fed gains room to cut rates preemptively.',
    ("Slowdown", "Mixed"): "Neutral slowdown.",
    ("Contraction", "Accelerating"): "Stagflation — the most dangerous scenario in the framework, the Fed has no room to maneuver.",
    ("Contraction", "Decelerating"): 'Disinflationary contraction — the "standard" recession scenario, the Fed has room to act.',
    ("Contraction", "Mixed"): "Neutral contraction.",
}


def generate_narrative(regime, inflation_trend):
    """Combines regime (Module A) + inflation trend into a single sentence."""
    if regime is None or inflation_trend is None:
        return None
    return INFLATION_NARRATIVE.get((regime, inflation_trend))


def calculate_full_context(regime: pd.Series, start_date: str = START_DATE) -> pd.DataFrame:
    """
    The "main" function of this file: brings everything together —
    fetches the context series, computes the inflation trend and the
    curve alert, and generates the narrative by combining them with the
    Module A regime (received as a parameter, already computed by
    transformation.calculate_module_a — this file doesn't recompute the
    regime, it only uses it).
    """
    context_df = fetch_context(start_date)
    inflation_trend = calculate_inflation_trend(context_df)
    curve_alert = calculate_curve_alert(context_df)

    result = pd.DataFrame({
        "regime": regime,
        "inflation_trend": inflation_trend,
    })
    result = result.join(curve_alert)
    result["narrative"] = result.apply(
        lambda row: generate_narrative(row["regime"], row["inflation_trend"]), axis=1
    )
    return result
