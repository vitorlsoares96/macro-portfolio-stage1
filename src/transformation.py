"""
Transformation of Module A raw data into an economic-cycle regime score —
implements Section 2.2 of the technical scope document.

This module assumes data_ingestion.py has already solved "fetch raw
data". Here the responsibility is different: take that raw data and
apply the formulas (% change, z-score, aggregation, classification) all
the way to the final regime (Expansion / Slowdown / Contraction /
Recovery).
"""

import pandas as pd

from config import MODULE_A_SERIES, START_DATE, MODULE_A_ZSCORE_WINDOW_MONTHS
from data_ingestion import fetch_fred_series


def transform_series(series: pd.Series, kind: str) -> pd.Series:
    """
    Applies the indicated transformation (see the "Suggested
    transformation" column of the Module A table in the scope document)
    to a raw series.

    Each `if` below matches one row of that table — the idea is that,
    reading this function, you can go back to the document and find
    exactly where each formula came from.
    """
    if kind == "yoy":
        # Percentage change relative to 12 months ago. pandas'
        # `.pct_change(12)` does exactly that: (value_today /
        # value_12_months_ago) - 1. We multiply by 100 to express it in
        # percentage points (e.g. 3.2 instead of 0.032).
        return series.pct_change(12) * 100

    elif kind == "monthly_diff":
        # Simple difference versus the prior month (not percentage).
        # For payrolls, this gives "how many more or fewer jobs" in the
        # month.
        return series.diff()

    elif kind == "inverted_level":
        # Just flips the sign. An unemployment rate that rises should
        # push the activity score down — multiplying by -1 does that
        # without needing to rewrite the aggregation logic to special-
        # case it later on.
        return -series

    elif kind == "inverted_level_ma4":
        # Moving average of 4 observations (in this series, 4 weeks),
        # then inverted. `.rolling(4)` looks at the observation itself
        # and the 3 before it — never the future, so it doesn't
        # introduce look-ahead bias.
        return -series.rolling(4).mean()

    elif kind == "level":
        # Already ready to use (e.g. Philly Fed is already a diffusion
        # index centered on zero) — no transformation needed.
        return series

    else:
        raise ValueError(f"Unknown transformation: '{kind}'. Check config.py.")


def build_monthly_series(readable_name: str, meta: dict, start_date: str) -> pd.Series:
    """
    Fetches a series (from Module A or the context layer), applies its
    transformation, and always returns it at MONTHLY frequency — even if
    the original source is weekly (unemployment claims) or daily (yield
    curve).

    Why do this: if we merged series of different frequencies straight
    into one DataFrame, every "extra" row (weekly or daily) would end up
    NaN in the monthly columns (you saw this happen in the ingestion
    test). Reducing everything to monthly here, BEFORE merging, avoids
    that problem at the root instead of patching it afterward.

    This function doesn't know (and doesn't need to know) which module a
    series belongs to — it only looks at the `meta` dict (fred_id,
    transformation, frequency). That's why the context layer (Section
    2.3) can reuse this very same function, with no code duplication.
    """
    raw = fetch_fred_series(meta["fred_id"], start_date=start_date)
    transformed = transform_series(raw, meta["transformation"])

    if meta["frequency"] != "monthly":
        # .resample("MS") groups the observations by month (MS = Month
        # Start, just a way of labeling each group by the first day of
        # the month) and .mean() averages the (weekly or daily)
        # observations that fall inside each month. It works the same
        # way no matter whether the original source was weekly or daily
        # — so we don't need a separate `if` for each case, just "if not
        # monthly, resample".
        transformed = transformed.resample("MS").mean()

    return transformed


def calculate_trailing_zscore(
    series: pd.Series, window: int = MODULE_A_ZSCORE_WINDOW_MONTHS, min_periods: int = 24
) -> pd.Series:
    """
    Standardizes a series into a z-score, using only data available up
    to that point (never from the future) — see Design Principle #3 in
    the scope document.

    `series.rolling(window=window, min_periods=min_periods)` creates a
    "sliding window": to compute the value at row N, it only looks at
    rows N-window+1 through N (never N+1 onward). That's what guarantees
    there's no look-ahead bias.

    `min_periods=24` means: in the first years of the series, before 120
    months of history exist yet, compute it anyway using whatever is
    available (starting from 24 months) — instead of returning NaN until
    a full 10 years accumulate. This is what the document calls an
    "expanding window in the early years of the series".
    """
    rolling_mean = series.rolling(window=window, min_periods=min_periods).mean()
    rolling_std = series.rolling(window=window, min_periods=min_periods).std()
    return (series - rolling_mean) / rolling_std


def classify_regime(level: float, momentum: float) -> str | None:
    """
    Implements the 2x2 table from Section 2.2 of the document: crosses
    the *level* of the score (above or below its historical average)
    with its *momentum* (rising or falling) to decide the regime.

    Returns None when there isn't enough data yet to classify (common in
    the first years of the series, before the z-score window has
    "warmed up").
    """
    if pd.isna(level) or pd.isna(momentum):
        return None
    if level > 0 and momentum > 0:
        return "Expansion"
    elif level > 0 and momentum <= 0:
        return "Slowdown"
    elif level <= 0 and momentum > 0:
        return "Recovery"
    else:
        return "Contraction"


def calculate_module_a(start_date: str = START_DATE) -> pd.DataFrame:
    """
    Runs the complete Module A pipeline, from raw data to classified
    regime. This is the "main" function of this file — the ones above
    are the internal steps it orchestrates, in the same order they
    appear in Section 2.2 of the document:

    1. Fetch + transform each indicator (already at monthly frequency)
    2. Compute each indicator's individual z-score
    3. Aggregate the z-scores by category (production, employment, consumption)
    4. Level score = average of the categories
    5. Smooth with a 3-month moving average
    6. Momentum = change of the smoothed score over the last 3 months
    7. Classify into a regime (Expansion / Slowdown / Contraction / Recovery)

    Returns
    -------
    pandas.DataFrame
        One row per month, with the columns: level_score, smoothed_score,
        momentum, regime.
    """
    # Step 1: fetch and transform each series (one column per indicator)
    transformed_series = {
        name: build_monthly_series(name, meta, start_date)
        for name, meta in MODULE_A_SERIES.items()
    }
    transformed_df = pd.DataFrame(transformed_series)

    # Step 2: z-score of each indicator, column by column.
    # `.apply(function)` on a DataFrame runs `function` on each column
    # separately and joins the results back into a DataFrame of the same
    # shape.
    zscore_df = transformed_df.apply(calculate_trailing_zscore)

    # Step 3: aggregate by category. For each category (production,
    # employment, consumption), we take the average of the columns that
    # belong to it.
    category_by_indicator = {name: meta["category"] for name, meta in MODULE_A_SERIES.items()}
    unique_categories = sorted(set(category_by_indicator.values()))

    category_df = pd.DataFrame({
        category: zscore_df[
            [name for name, cat in category_by_indicator.items() if cat == category]
        ].mean(axis=1)
        for category in unique_categories
    })

    # Step 4: level score = simple average of the categories
    level_score = category_df.mean(axis=1)

    # Step 5: smoothing with a 3-month moving average
    smoothed_score = level_score.rolling(window=3, min_periods=3).mean()

    # Step 6: momentum = change of the smoothed score over the last 3 months
    momentum = smoothed_score.diff(3)

    # Step 7: classify regime, row by row
    result = pd.DataFrame({
        "level_score": level_score,
        "smoothed_score": smoothed_score,
        "momentum": momentum,
    })
    result["regime"] = result.apply(
        lambda row: classify_regime(row["smoothed_score"], row["momentum"]), axis=1
    )

    return result
