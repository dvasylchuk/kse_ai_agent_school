"""
=============================================================================
STEP 1 — DATASET AUDIT / VALIDATION  (NO ANALYSIS YET)
=============================================================================
Project : Time Series Analysis of Air Raid Alerts in Ukraine
Question: "How clustered in time are air raid alerts in Kyiv, and how did the
           degree of clustering vary across different periods of the war?"

Purpose of this file:
    Verify whether the dataset is SUITABLE for the research question above.
    We are NOT analysing clustering here. We only check that the data is
    clean, well-understood, and that "Kyiv" can be isolated reliably.

Dataset:
    Vadimkin / ukrainian-air-raid-sirens-dataset (GitHub)
    File used: official_data_en.csv  (authoritative, English column names)

Key facts from the dataset README (verified) that drive these checks:
    - All timestamps are in UTC.
    - Official data starts 15 March 2022.
    - Granularity CHANGED: oblast-level before ~Dec 2025, raion-level after.
      -> we must be aware of this when choosing an analysis window.
    - Estimated end times are flagged: when no "all-clear" was recorded,
      the row has naive=True and finished_at = started_at + 30 minutes.
=============================================================================
"""

import pandas as pd

# Display settings so printed output is readable during the audit.
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 120)


# -----------------------------------------------------------------------------
# 1. LOAD THE DATA
# -----------------------------------------------------------------------------
# Two ways to load. For a reproducible GitHub project, DOWNLOAD the CSV once,
# commit it into your repo (e.g. data/official_data_en.csv), and load locally.
# That way your results never drift if the live dataset updates.
#
# Option A — local file (recommended for reproducibility):
# DATA_PATH = "data/official_data_en.csv"
#
# Option B — load directly from GitHub raw (handy for a first look):
DATA_PATH = (
    "https://raw.githubusercontent.com/Vadimkin/"
    "ukrainian-air-raid-sirens-dataset/main/datasets/official_data_en.csv"
)

# We read timestamps as plain strings first, then parse them ourselves in
# step 8. Parsing manually lets us SEE failures instead of silently
# coercing bad rows to NaT.
#
# STRICT LOADING: if the file cannot be loaded, STOP and report exactly what
# failed. We never fall back to sample/synthetic data and never guess.
import sys

print("=" * 70)
print("DATASET AUDIT")
print("=" * 70)
print(f"\nAttempting to load:\n{DATA_PATH}\n")

try:
    df = pd.read_csv(DATA_PATH)
except FileNotFoundError:
    sys.exit(f"STOP: file not found at {DATA_PATH}\n"
             f"      If using a local path, download the CSV first.")
except UnicodeDecodeError as e:
    sys.exit(f"STOP: could not decode the file as text ({e}).\n"
             f"      Check you pointed at the CSV, not a binary/HTML page.")
except pd.errors.EmptyDataError:
    sys.exit(f"STOP: the file at {DATA_PATH} is empty.")
except pd.errors.ParserError as e:
    sys.exit(f"STOP: CSV parsing failed ({e}).\n"
             f"      The delimiter or quoting may differ from expectation.")
except Exception as e:
    # Covers network errors (URLError/HTTPError) when reading from a URL.
    sys.exit(f"STOP: could not load the dataset.\n"
             f"      Reason: {type(e).__name__}: {e}")

# Guard against loading an HTML error page instead of the real CSV
# (a common failure when a raw URL is wrong - you get a 1-column frame).
if df.shape[1] < 2:
    sys.exit(f"STOP: loaded only {df.shape[1]} column(s). This is usually a\n"
             f"      wrong URL returning an HTML/error page, not the CSV.\n"
             f"      First bytes seen: {list(df.columns)[:3]}")

if len(df) == 0:
    sys.exit("STOP: file loaded but contains 0 rows.")

print(f"OK: loaded {len(df):,} rows, {df.shape[1]} columns.\n")


# -----------------------------------------------------------------------------
# 2. COLUMN NAMES
# -----------------------------------------------------------------------------
# Confirm the columns match what we expect before relying on any of them.
print("-" * 70)
print("2. COLUMN NAMES")
print("-" * 70)
print(list(df.columns))
print("\nDtypes:")
print(df.dtypes)


# -----------------------------------------------------------------------------
# 3. FIRST ROWS
# -----------------------------------------------------------------------------
# A quick eyeball of real values: timestamp format, region naming, any flags.
print("\n" + "-" * 70)
print("3. FIRST ROWS")
print("-" * 70)
print(df.head(10))


# -----------------------------------------------------------------------------
# 4. UNIQUE REGION NAMES
# -----------------------------------------------------------------------------
# We must know exactly how regions are labelled before we can isolate Kyiv.
# The exact column name may be "region" or "region_title" - detect it.
print("\n" + "-" * 70)
print("4. UNIQUE REGION NAMES")
print("-" * 70)

region_col = None
for candidate in ["region", "region_title", "oblast", "region_en"]:
    if candidate in df.columns:
        region_col = candidate
        break

if region_col is None:
    print("!! Could not auto-detect a region column. Inspect columns above.")
else:
    print(f"Region column detected: '{region_col}'")
    regions = sorted(df[region_col].dropna().unique())
    print(f"Number of unique regions: {len(regions)}\n")
    for r in regions:
        print("  -", r)


# -----------------------------------------------------------------------------
# 5. KYIV CITY vs KYIV OBLAST  (THE MOST IMPORTANT CHECK)
# -----------------------------------------------------------------------------
# The research question is about KYIV. If "Kyiv city" and "Kyiv oblast" are
# separate entries, we choose ONE (city is the cleaner unit). If they are
# merged into a single label, we must document that as a limitation.
print("\n" + "-" * 70)
print("5. KYIV CITY vs KYIV OBLAST")
print("-" * 70)

if region_col is not None:
    kyiv_matches = [r for r in regions if "kyiv" in str(r).lower()
                    or "kiev" in str(r).lower()]
    print("Region labels containing 'Kyiv':")
    for r in kyiv_matches:
        count = (df[region_col] == r).sum()
        print(f"  - {r!r:35s}  ({count:,} alerts)")

    if len(kyiv_matches) >= 2:
        print("\n=> City and oblast appear SEPARATE. Decide which to use")
        print("   (recommended: the city-level label) and state it explicitly.")
    elif len(kyiv_matches) == 1:
        print("\n=> Only ONE Kyiv label found. Check whether it represents the")
        print("   city, the oblast, or a mix - note this as a limitation.")
    else:
        print("\n!! No 'Kyiv' label found - inspect the region list in step 4.")


# -----------------------------------------------------------------------------
# 6. MISSING VALUES IN started_at / finished_at
# -----------------------------------------------------------------------------
# started_at is our PRIMARY signal for clustering (gaps between starts).
# finished_at feeds duration only, so missing ends are less damaging.
print("\n" + "-" * 70)
print("6. MISSING VALUES")
print("-" * 70)

for col in ["started_at", "finished_at"]:
    if col in df.columns:
        n_missing = df[col].isna().sum()
        pct = 100 * n_missing / len(df)
        print(f"  {col:14s}: {n_missing:,} missing ({pct:.2f}%)")
    else:
        print(f"  !! Column '{col}' not found.")

# Note any 'naive' / estimated-end flag the README described.
flag_cols = [c for c in df.columns if c.lower() in ("naive", "is_naive", "estimated")]
if flag_cols:
    fc = flag_cols[0]
    print(f"\n  Estimated-end flag column found: '{fc}'")
    print(df[fc].value_counts(dropna=False).to_string())
    print("  (True = end time was assumed as start + 30 min, not observed.)")
else:
    print("\n  No explicit 'naive' flag column detected - if durations cluster")
    print("  suspiciously at exactly 30 min, treat those ends as estimated.")


# -----------------------------------------------------------------------------
# 7. DUPLICATES
# -----------------------------------------------------------------------------
# Exact duplicate rows would inflate alert counts and distort gaps.
print("\n" + "-" * 70)
print("7. DUPLICATES")
print("-" * 70)
n_exact = df.duplicated().sum()
print(f"  Exact duplicate rows: {n_exact:,}")

if region_col and "started_at" in df.columns:
    n_key_dupes = df.duplicated(subset=[region_col, "started_at"]).sum()
    print(f"  Same region + same start time: {n_key_dupes:,}")
    print("  (These may be genuine re-issues or recording artefacts - inspect.)")


# -----------------------------------------------------------------------------
# 8. PARSE TIMESTAMPS
# -----------------------------------------------------------------------------
# Parse to real datetimes (UTC). errors='coerce' turns unparseable values into
# NaT so we can count failures rather than crash.
print("\n" + "-" * 70)
print("8. PARSE TIMESTAMPS (UTC)")
print("-" * 70)

for col in ["started_at", "finished_at"]:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")
        n_failed = df[col].isna().sum()
        print(f"  {col:14s}: parsed, {n_failed:,} unparseable -> NaT")


# -----------------------------------------------------------------------------
# 9. DATE RANGE
# -----------------------------------------------------------------------------
# Confirm coverage and watch for the Dec-2025 granularity change.
print("\n" + "-" * 70)
print("9. DATE RANGE")
print("-" * 70)
if "started_at" in df.columns:
    print(f"  Earliest start: {df['started_at'].min()}")
    print(f"  Latest start:   {df['started_at'].max()}")
    print("\n  Reminder: granularity changed to raion-level ~Dec 2025.")
    print("  For a consistent oblast-level study, cap the window before then.")


# -----------------------------------------------------------------------------
# 10. COMPUTE DURATION
# -----------------------------------------------------------------------------
# Duration is a SECONDARY signal. We compute it to audit quality, not to
# build the analysis yet.
print("\n" + "-" * 70)
print("10. DURATION")
print("-" * 70)
if {"started_at", "finished_at"}.issubset(df.columns):
    df["duration_min"] = (
        df["finished_at"] - df["started_at"]
    ).dt.total_seconds() / 60.0
    print(df["duration_min"].describe().to_string())


# -----------------------------------------------------------------------------
# 11. ZERO / NEGATIVE / UNREALISTIC DURATIONS
# -----------------------------------------------------------------------------
# Negative   -> end before start (data error).
# Zero       -> instantaneous, likely artefact.
# Exactly 30 -> likely the estimated 'naive' ends from the README.
# Very long  -> rare for Kyiv city; inspect (frontline regions can be long).
print("\n" + "-" * 70)
print("11. SUSPICIOUS DURATIONS")
print("-" * 70)
if "duration_min" in df.columns:
    n_negative = (df["duration_min"] < 0).sum()
    n_zero = (df["duration_min"] == 0).sum()
    n_exactly_30 = (df["duration_min"] == 30).sum()
    n_over_24h = (df["duration_min"] > 24 * 60).sum()

    print(f"  Negative duration (end < start): {n_negative:,}")
    print(f"  Zero duration:                   {n_zero:,}")
    print(f"  Exactly 30 min (likely estimated): {n_exactly_30:,}")
    print(f"  Longer than 24 hours:            {n_over_24h:,}")
    print("\n  Use these counts to decide what to exclude from DURATION work.")
    print("  None of this affects start-time clustering, which stays robust.")


# -----------------------------------------------------------------------------
# 12. AUDIT VERDICT (manual)
# -----------------------------------------------------------------------------
# After reading the printout above, answer these in your notebook in prose:
#   1) Is a clean Kyiv (city) subset available?            yes / no
#   2) Are start times reliable and fully parseable?       yes / no
#   3) Can estimated end times be identified & excluded?   yes / no
#   4) Is there a consistent oblast-era window to study?   yes / no
# If 1-4 are "yes", the dataset is suitable for the research question and
# you can proceed to Step 2 (gaps / clustering analysis).
print("\n" + "=" * 70)
print("AUDIT COMPLETE - fill in the verdict (step 12) before any analysis.")
print("=" * 70)
