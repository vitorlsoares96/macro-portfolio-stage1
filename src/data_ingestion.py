"""
Data ingestion functions — Phase 1.

This module doesn't do any score calculation. It knows how to do only one
thing: fetch raw data from the sources (FRED and Yahoo Finance) and
return it as pandas Series/DataFrames, ready for the modules that still
need to use it (z-score transformation, regime classification, etc.).

Why separate "fetch data" from "calculate something with the data" into
different files: this is called separation of concerns — a core software
engineering principle. In practice it means you can swap a data source
(e.g. use a different API instead of FRED) without touching a single
line of calculation logic, and you can test each part in isolation.
"""

import os
from fredapi import Fred
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

# load_dotenv() reads the .env file (if it exists) and "injects" its
# variables into the process environment — it's as if you had run
# `export FRED_API_KEY=...` in the terminal before calling Python.
load_dotenv()


def _get_fred_client() -> Fred:
    """
    Creates and returns an authenticated FRED API client.

    The leading underscore in the name (_get_fred_client) is a Python
    convention: it signals "this is for internal use in this file", not
    meant to be called directly by other parts of the code. Anyone using
    this module from outside should call the fetch_* functions below,
    not this one.
    """
    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        raise RuntimeError(
            "FRED_API_KEY not found in environment variables. "
            "Copy .env.example to .env and paste your free key in "
            "(instructions in README.md)."
        )
    return Fred(api_key=api_key)


def fetch_fred_series(series_id: str, start_date: str = "1990-01-01") -> pd.Series:
    """
    Fetches a single data series from FRED.

    Parameters
    ----------
    series_id : str
        The series identifier on FRED (e.g. "INDPRO"). The IDs used in
        this project are documented in src/config.py and in the Phase 1
        technical scope document.
    start_date : str
        Minimum date to consider, "YYYY-MM-DD" format.

    Returns
    -------
    pandas.Series
        A series indexed by date (the index already comes as a pandas
        DatetimeIndex — a "date-aware" index type, which lets you later
        do things like series.rolling("365D")).
    """
    fred = _get_fred_client()
    series = fred.get_series(series_id, observation_start=start_date)
    series.name = series_id  # names the series — useful when we merge several into a DataFrame
    return series


def fetch_multiple_fred_series(series_dict: dict, start_date: str = "1990-01-01") -> pd.DataFrame:
    """
    Fetches several FRED series at once and merges everything into a
    single DataFrame.

    Parameters
    ----------
    series_dict : dict
        A dict in the format of MODULE_A_SERIES, CONTEXT_SERIES or
        MODULE_B_FRED_SERIES (see src/config.py) — the key is a readable
        name (e.g. "industrial_production"), the value is a dict with at
        least the "fred_id" key.

    Returns
    -------
    pandas.DataFrame
        A DataFrame with one column per indicator, using the readable
        name as the column name. Series with different frequencies (e.g.
        one monthly and another weekly) end up aligned on the same date
        index automatically — pandas fills the days a given series has
        no observation with NaN (empty). This is expected and handled in
        the transformation step, not here.
    """
    columns = {}
    for readable_name, meta in series_dict.items():
        columns[readable_name] = fetch_fred_series(meta["fred_id"], start_date)
    return pd.DataFrame(columns)


def fetch_multiple_yahoo_tickers(tickers_dict: dict, start_date: str = "1990-01-01") -> pd.DataFrame:
    """
    Fetches several Yahoo Finance tickers at once (FX, commodities).

    Parameters
    ----------
    tickers_dict : dict
        A dict in the format of MODULE_B_YAHOO_TICKERS (see
        src/config.py) — the key is a readable name, the value has a
        "ticker" key with the real Yahoo Finance symbol (e.g.
        "AUDJPY=X").

    Returns
    -------
    pandas.DataFrame
        A DataFrame with one column per ticker, using the adjusted
        closing price ("Close"). Unlike FRED, yfinance returns several
        columns per ticker (Open, High, Low, Close, Volume) — that's why
        the function extracts only the "Close" column from each before
        merging.
    """
    columns = {}
    for readable_name, meta in tickers_dict.items():
        data = yf.download(meta["ticker"], start=start_date, progress=False)
        close = data["Close"]

        # Recent yfinance versions sometimes return columns with two
        # levels (MultiIndex: price x ticker) even when requesting a
        # single ticker — in that case data["Close"] comes back as a
        # one-column DataFrame instead of a Series. `.squeeze("columns")`
        # "flattens" this to a Series when there's exactly one column,
        # without changing anything if it already came as a Series (old
        # behavior).
        if isinstance(close, pd.DataFrame):
            close = close.squeeze("columns")

        columns[readable_name] = close
    return pd.DataFrame(columns)
