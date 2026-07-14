"""
Action matrix — Section 4 of the technical scope document.

Crosses Module A's regime (monthly, strategic) with Module B's filtered
score (daily, tactical) to produce a single actionable reading — this is
the "final product" of Phase 1, the piece that ties both modules into
the same story.
"""

import pandas as pd

# Action table — the 4x3 matrix from Section 4 of the document. The key
# is a (regime, risk) tuple; the value is the recommended action. Keeping
# this as a dict, rather than a chain of `if/elif`, makes the table
# "visually match" the document's table — easier to check one against
# the other than a sequence of conditionals.
ACTION_MATRIX = {
    ("Expansion", "Risk-on"): "Increase exposure to cyclicals / high beta",
    ("Expansion", "Neutral"): "Maintain target exposure",
    ("Expansion", "Risk-off"): "Temporary risk-off → hold position, treat as noise",
    ("Recovery", "Risk-on"): "Increase exposure gradually, start rotating into cyclicals",
    ("Recovery", "Neutral"): "Neutral stance, wait for confirmation",
    ("Recovery", "Risk-off"): "Caution — may be a false recovery; reduce position size",
    ("Slowdown", "Risk-on"): "Reduce gradually, rotate into quality/defensives",
    ("Slowdown", "Neutral"): "Reduce target exposure",
    ("Slowdown", "Risk-off"): "Cut risk decisively",
    ("Contraction", "Risk-on"): 'Alert — possible "bear market rally"; don\'t trust the tactical signal alone',
    ("Contraction", "Neutral"): "Cut risk decisively",
    ("Contraction", "Risk-off"): "Cut risk decisively (the framework's most defensive stance)",
}


def classify_risk(filtered_score: float):
    """
    Groups Module B's filtered score (-2 to +2) into 3 buckets — Risk-on,
    Neutral, Risk-off — to fit the columns of the document's matrix.
    """
    if pd.isna(filtered_score):
        return None
    if filtered_score >= 1:
        return "Risk-on"
    elif filtered_score <= -1:
        return "Risk-off"
    else:
        return "Neutral"


def generate_action(regime: str, risk: str):
    """Looks up the action table with the (regime, risk) pair."""
    if regime is None or risk is None:
        return None
    return ACTION_MATRIX.get((regime, risk))


def combine_modules(monthly_regime: pd.Series, daily_filtered_score: pd.Series) -> pd.DataFrame:
    """
    Merges Module A's monthly regime with Module B's daily filtered
    score, into a single daily table with regime + risk + action.

    The key step here: Module A is monthly (one reading per month), but
    Module B is daily. To combine the two, we "spread" the monthly
    regime across every day — each day inherits the last known monthly
    regime, until a new one appears.

    Bug I found testing with synthetic data before sending: my first
    attempt used `.resample("D").ffill()`, but that only fills forward
    up to the LAST date that already exists in the original monthly
    series — days after that (e.g. the days of a month still in
    progress, before the next monthly data point comes out) were left
    empty. The fix is to use `.reindex(..., method="ffill")`, which keeps
    filling forward indefinitely with the last known value, instead of
    stopping at the original series' boundary.
    """
    daily_regime = monthly_regime.reindex(daily_filtered_score.index, method="ffill")

    result = pd.DataFrame({
        "regime": daily_regime,
        "filtered_score": daily_filtered_score,
    })
    # Only keep days where Module B has data — days before Module B
    # starts, or after the point Module A already covers, don't have a
    # useful combined reading.
    result = result.dropna(subset=["filtered_score"])

    result["risk"] = result["filtered_score"].apply(classify_risk)
    result["action"] = result.apply(
        lambda row: generate_action(row["regime"], row["risk"]), axis=1
    )
    return result
