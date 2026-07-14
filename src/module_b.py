"""
Module B calculation — risk-on/risk-off, implements Section 3.2 of the
technical scope document.

Just like transformation.py handles Module A, this file handles Module B
end to end: fetches the daily indicators, standardizes them, combines
them, discretizes into -2 to +2, and applies the persistence filter.
"""

import pandas as pd

from config import (
    MODULE_B_FRED_SERIES,
    MODULE_B_YAHOO_TICKERS,
    START_DATE,
    MODULE_B_ZSCORE_WINDOW_DAYS,
)
from data_ingestion import fetch_fred_series, fetch_multiple_yahoo_tickers
from transformation import calculate_trailing_zscore  # reused from Module A


def fetch_module_b(start_date: str = START_DATE) -> pd.DataFrame:
    """
    Fetches Module B's 6 daily indicators (4 from FRED + 2 from Yahoo
    Finance) and merges everything into a single daily DataFrame.
    """
    fred_columns = {
        name: fetch_fred_series(meta["fred_id"], start_date=start_date)
        for name, meta in MODULE_B_FRED_SERIES.items()
    }
    fred_df = pd.DataFrame(fred_columns)

    yahoo_df = fetch_multiple_yahoo_tickers(MODULE_B_YAHOO_TICKERS, start_date=start_date)

    # .join merges the two DataFrames by date (the index). how="outer"
    # keeps any date that shows up in EITHER of the two sets of series —
    # different exchanges have different holidays (e.g. a US holiday
    # isn't a holiday in Japan), so not every day has an observation for
    # everything at once.
    df = fred_df.join(yahoo_df, how="outer")
    df = df.sort_index()

    # .ffill() ("forward fill") carries the last known value forward,
    # covering those holiday gaps — we assume that if a market didn't
    # open, yesterday's value "still holds" until the next real
    # observation.
    df = df.ffill()
    return df


def discretize_score(z: float):
    """
    Section 3.2, step 4 of the document: turns the composite z-score (a
    continuous number, typically between -3 and +3) into an integer from
    -2 to +2, using the bands defined in the document's table.
    """
    if pd.isna(z):
        return None
    if z > 1.5:
        return 2
    elif z > 0.5:
        return 1
    elif z >= -0.5:
        return 0
    elif z >= -1.5:
        return -1
    else:
        return -2


def apply_persistence_filter(score_series: pd.Series, min_days: int = 5) -> pd.Series:
    """
    Section 3.2, step 5 of the document: only "confirms" a side change
    (risk-on vs risk-off) after the score's SIGN (positive, negative, or
    zero) has held for `min_days` consecutive business days. Until
    confirmed, the filtered value stays equal to the last confirmed
    value — this is what prevents a single-day scare (a bad data point
    that fades the next day) from moving the tactical reading.

    Note on the implementation: here we use an explicit loop instead of
    the groupby+cumsum trick we used for counting inverted-curve months
    in context.py. Both approaches solve similar problems ("look back
    in time"); a loop is easier to read step by step, groupby+cumsum is
    faster and more "pandas-idiomatic". Worth knowing both.
    """
    sign = score_series.apply(
        lambda x: None if pd.isna(x) else (1 if x > 0 else (-1 if x < 0 else 0))
    )

    result = []
    last_confirmed = None
    for i in range(len(sign)):
        # Take the last `min_days` days up to today (inclusive).
        window = sign.iloc[max(0, i - min_days + 1): i + 1]
        valid_signs = window.dropna()
        same_sign_for_full_period = (
            len(valid_signs) == min_days and valid_signs.nunique() == 1
        )
        if same_sign_for_full_period:
            last_confirmed = score_series.iloc[i]
        result.append(last_confirmed)

    return pd.Series(result, index=score_series.index, name="filtered_score")


def calculate_module_b(
    start_date: str = START_DATE, persistence_days: int = 5, min_indicators: int = 2
) -> pd.DataFrame:
    """
    Complete Module B pipeline, from data fetching to the final filtered
    score. The "main" function of this file, following the same logic as
    transformation.calculate_module_a.

    New parameter, `min_indicators`: minimum number of indicators with
    valid data on a given day for that day to get a composite computed
    (see explanation below, in Step 3) — protection for when some
    indicator has a shorter history than the others (this happened with
    AUD/JPY and gold, which only have Yahoo Finance data starting in the
    2000s, well after 1990).
    """
    raw_df = fetch_module_b(start_date)

    # Merges the metadata from both groups (FRED + Yahoo) into a single
    # dict, since from here on the pipeline treats everyone the same way.
    metadata = {**MODULE_B_FRED_SERIES, **MODULE_B_YAHOO_TICKERS}

    # Step 1: daily z-score of each indicator (~2 trading-year window).
    zscore_df = pd.DataFrame({
        name: calculate_trailing_zscore(
            raw_df[name], window=MODULE_B_ZSCORE_WINDOW_DAYS, min_periods=60
        )
        for name in metadata
    })

    # Step 2: flip the sign where needed (see config.py), so that a
    # positive value always means "more risk-on" in every column.
    for name, meta in metadata.items():
        if meta.get("invert_sign"):
            zscore_df[name] = -zscore_df[name]

    # Step 3: weighted composite, tolerant to indicators missing on a
    # given day.
    #
    # The previous version did `sum(column * weight for ...)`, adding
    # up the pandas Series one by one with Python's `+` operator — and
    # pandas' default sum propagates NaN: if ANY column has NaN on a
    # date, that date's result becomes NaN, even if the other 5 columns
    # have valid data. That's exactly what "contaminated" almost the
    # entire history when we discovered one series had much less data
    # than the others.
    #
    # The fix: use a DataFrame's `.sum(axis=1)` instead of adding Series
    # one at a time. `DataFrame.sum(axis=1)` IGNORES NaN by default
    # (treats it as if the column didn't exist on that row) instead of
    # propagating it. At the same time, for the average to be correct,
    # we also only sum the WEIGHTS of the indicators that actually had
    # data that day — otherwise a day with only 2 out of 6 indicators
    # would end up on the wrong scale (dividing by a fixed
    # "total_weight" that doesn't match what was actually summed).
    weights = pd.Series({name: meta.get("weight", 1.0) for name, meta in metadata.items()})

    contributions = zscore_df.mul(weights, axis=1)
    available_weights = zscore_df.notna().mul(weights, axis=1)
    available_indicator_count = zscore_df.notna().sum(axis=1)

    total_available_weight = available_weights.sum(axis=1)
    z_score = contributions.sum(axis=1) / total_available_weight

    # Requires a minimum number of valid indicators on that day; below
    # that, the composite stays undefined (NaN) instead of leaning on a
    # single isolated indicator, which would give a false sense of
    # precision.
    z_score[available_indicator_count < min_indicators] = float("nan")
    z_score.name = "z_score"

    # Step 4: discretization into -2 to +2.
    discrete_score = z_score.apply(discretize_score)
    discrete_score.name = "discrete_score"

    # Step 5: persistence filter.
    filtered_score = apply_persistence_filter(discrete_score, min_days=persistence_days)

    return pd.DataFrame({
        "z_score": z_score,
        "discrete_score": discrete_score,
        "filtered_score": filtered_score,
    })
