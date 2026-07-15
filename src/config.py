"""
Central project configuration — Phase 1 (Nowcasting + Risk-on/Risk-off).

Why this file exists, and why it only holds "data", no logic:
This file doesn't CALCULATE anything. It only stores constants — fixed
values that several parts of the code will need (which series to pull,
from which source, with which transformation). The idea of centralizing
this in ONE place is: if you ever want to change the z-score window from
10 to 8 years, or add a new series, you change it in ONE place. Without
this, that kind of number would end up scattered (and forgotten) across
several different files.

This is also why this file matches the tables in the technical scope
document (Phase1_Technical_Scope...md) 1:1 — the code doesn't
"reinvent" the choices, it just implements what was already decided and
justified there. If a recruiter asks "why did you use this series", the
answer is in the document, not buried inside the code.
"""

# ---------------------------------------------------------------------------
# Module A — economic cycle indicators (monthly / weekly)
# Structure: a dict of dicts. The outer key ("industrial_production") is a
# readable name we'll use throughout the rest of the code; the inner dict
# holds each series' metadata (the real FRED ID, the CFNAI category it
# belongs to, and which mathematical transformation to apply).
# ---------------------------------------------------------------------------
MODULE_A_SERIES = {
    "industrial_production": {
        "fred_id": "INDPRO",
        "category": "production",
        "transformation": "yoy",  # year-over-year % change
        "frequency": "monthly",
    },
    "payrolls": {
        "fred_id": "PAYEMS",
        "category": "employment",
        "transformation": "monthly_diff",  # absolute month-over-month change (thousands of jobs)
        "frequency": "monthly",
    },
    "unemployment_rate": {
        "fred_id": "UNRATE",
        "category": "employment",
        "transformation": "inverted_level",  # level, sign inverted (a drop = positive)
        "frequency": "monthly",
    },
    "unemployment_claims": {
        "fred_id": "ICSA",
        "category": "employment",
        "transformation": "inverted_level_ma4",  # 4-week moving average, then inverted
        "frequency": "weekly",  # needs to be downsampled to monthly before merging with the others
    },
    "retail_sales": {
        "fred_id": "RSAFS",
        "category": "consumption",
        "transformation": "yoy",
        "frequency": "monthly",
    },
    "philly_fed": {
        "fred_id": "GACDFSA066MSFRBPHI",
        "category": "consumption",  # see doc note: manufacturing-sentiment proxy
        "transformation": "level",  # already a diffusion index centered on 0
        "frequency": "monthly",
    },
}

# ---------------------------------------------------------------------------
# Context layer — inflation and yield curve (do NOT enter the Module A
# average; see Section 2.3 of the scope document for the full rule)
# ---------------------------------------------------------------------------
CONTEXT_SERIES = {
    "cpi": {"fred_id": "CPIAUCSL", "transformation": "yoy", "frequency": "monthly"},
    "core_pce": {"fred_id": "PCEPILFE", "transformation": "yoy", "frequency": "monthly"},
    "yield_curve_10y2y": {"fred_id": "T10Y2Y", "transformation": "level", "frequency": "daily"},
    "yield_curve_10y3m": {"fred_id": "T10Y3M", "transformation": "level", "frequency": "daily"},
}

# ---------------------------------------------------------------------------
# Module B — risk-on / risk-off (daily)
# Split into two sources because they come from different Python libraries:
# FRED uses the `fredapi` library; the FX/commodity tickers use `yfinance`,
# since they don't exist on FRED.
# ---------------------------------------------------------------------------
MODULE_B_FRED_SERIES = {
    "vix": {"fred_id": "VIXCLS", "invert_sign": True},
    # UPDATE (found while testing with real data): the series originally in
    # the document, BAMLH0A0HYM2 (ICE BofA high-yield spread), has a
    # licensing restriction on FRED — the API only returns the last 3
    # years, even when requesting history back to 1990 (the website shows
    # everything, the API doesn't). Swapped for BAA10Y (Moody's Baa credit
    # spread, public data with no such restriction, history back to 1986)
    # — it measures the same idea (credit risk premium), just over a
    # slightly higher-rated universe (Baa is low investment-grade, not
    # properly "high yield"). Worth mentioning in an interview: it's a
    # real example of a discovered and worked-around data-source
    # limitation, not just theory.
    "credit_spread": {"fred_id": "BAA10Y", "invert_sign": True},
    # FIXED (found the same way as treasury_10y below): this was previously
    # invert_sign=True, which is backwards. Checked against two independent
    # crises before concluding this — March 2020 alone was ambiguous, because
    # DEXJPUS had a real, well-documented anomaly during the "dash for cash"
    # (Mar 9-24, 2020: a global USD funding squeeze made the dollar spike
    # against nearly everything, including JPY, temporarily flipping the
    # classic haven-currency relationship). But checked against 2008 (Aug-Dec,
    # the Lehman Brothers collapse), the raw (uninverted) series behaved
    # exactly as the textbook story predicts — consistently negative
    # (yen strengthening = risk-off) for the entire ~4-month window, no
    # reversal. Two independent crises agreeing (one of them cleanly, with
    # no exception) was enough evidence to fix this one too.
    "jpy_usd": {"fred_id": "DEXJPUS", "invert_sign": False},
    # FIXED (found while diagnosing individual indicator signs against
    # March 2020): this was previously invert_sign=True, which is backwards.
    # DGS10 fell steadily and unambiguously throughout March 2020 (the
    # cleanest flight-to-quality signal of all 6 indicators, bottoming at
    # an all-time low on March 9) — its raw (uninverted) z-score is already
    # negative during risk-off, exactly matching this project's convention
    # (positive z-score = risk-on). Inverting it made the pipeline read
    # "risk-on" throughout the most extreme risk-off event in the sample
    # period. The composite still classified March 2020 correctly as
    # extreme risk-off despite this, because the other 5 indicators
    # (especially VIX and the credit spread) outweighed the error — but
    # that's not guaranteed in every period, hence the fix.
    "treasury_10y": {"fred_id": "DGS10", "invert_sign": False},
}

MODULE_B_YAHOO_TICKERS = {
    "aud_jpy": {"ticker": "AUDJPY=X", "invert_sign": False},
    "gold": {"ticker": "GC=F", "invert_sign": False, "weight": 0.5},
}

# ---------------------------------------------------------------------------
# General parameters
# ---------------------------------------------------------------------------
START_DATE = "1990-01-01"  # wide enough to cover 2001, 2008 and 2020
MODULE_A_ZSCORE_WINDOW_MONTHS = 120  # 10 years — see Section 2.2 of the document
MODULE_B_ZSCORE_WINDOW_DAYS = 504  # ~2 trading years — see Section 3.2 of the document
