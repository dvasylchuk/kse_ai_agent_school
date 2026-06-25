"""
=============================================================================
STEP 2 — CLEAN & VALIDATE THE KYIV CITY SUBSET  (NO CLUSTERING YET)
=============================================================================
Project : Time Series Analysis of Air Raid Alerts in Ukraine
Question: "How clustered in time are air raid alerts in Kyiv, and how did the
           degree of clustering vary across different periods of the war?"

Goal of this step:
    Produce a clean, well-understood Kyiv City subset and SAVE it.
    We do NOT analyse clustering here. We only filter, de-duplicate
    transparently, and re-audit.

Confirmed facts from your Step-1 audit (used as inputs here):
    - Real columns: oblast, raion, hromada, level, started_at, finished_at, source
    - "Kyiv City" and "Kyivska oblast" are SEPARATE oblast values.
    - started_at / finished_at have 0 missing values and parse correctly.
    - Full date range: 2022-03-15 to 2026-06-24.
    - Granularity changed ~Dec 2025, so we cap the window at 2025-11-30.

Rules followed:
    - No fake/sample data. We read only the real file.
    - No silent dropping. Every removal is counted and explained.
    - Stop loudly if the expected structure is not present.
=============================================================================
"""

import os
import sys
import pandas as pd

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 120)

# -----------------------------------------------------------------------------
# 0. CONFIG  (edit DATA_PATH to wherever your real CSV lives)
# -----------------------------------------------------------------------------
DATA_PATH = "data/official_data_en.csv"      # the file you audited in Step 1
OUT_DIR = "data/processed"
OUT_PATH = os.path.join(OUT_DIR, "kyiv_city_alerts_clean.csv")

KYIV_CITY_LABEL = "Kyiv City"                 # exact oblast value from your audit
WINDOW_START = pd.Timestamp("2022-03-15", tz="UTC")
WINDOW_END = pd.Timestamp("2025-11-30 23:59:59", tz="UTC")

EXPECTED_COLS = {"oblast", "raion", "hromada", "level",
                 "started_at", "finished_at", "source"}


# -----------------------------------------------------------------------------
# 1. LOAD  (strict; stop loudly on any failure)
# -----------------------------------------------------------------------------
print("=" * 70)
print("STEP 2 — KYIV CITY CLEANING & VALIDATION")
print("=" * 70)

try:
    df = pd.read_csv(DATA_PATH)
except Exception as e:
    sys.exit(f"STOP: could not load {DATA_PATH}\n"
             f"      Reason: {type(e).__name__}: {e}")

missing_cols = EXPECTED_COLS - set(df.columns)
if missing_cols:
    sys.exit(f"STOP: expected columns are missing: {sorted(missing_cols)}\n"
             f"      Found: {list(df.columns)}\n"
             f"      The file structure differs from your Step-1 audit.")

print(f"\nLoaded full dataset: {len(df):,} rows, {df.shape[1]} columns.")

# Parse timestamps to real UTC datetimes (so the window filter is correct).
df["started_at"] = pd.to_datetime(df["started_at"], utc=True, errors="coerce")
df["finished_at"] = pd.to_datetime(df["finished_at"], utc=True, errors="coerce")

n_unparseable = df["started_at"].isna().sum() + df["finished_at"].isna().sum()
if n_unparseable > 0:
    print(f"  Note: {n_unparseable:,} timestamp value(s) failed to parse "
          f"(became NaT). They will be visible in the checks below.")


# -----------------------------------------------------------------------------
# 2. FILTER TO KYIV CITY ONLY
# -----------------------------------------------------------------------------
print("\n" + "-" * 70)
print("2. FILTER: oblast == 'Kyiv City'")
print("-" * 70)

if KYIV_CITY_LABEL not in df["oblast"].unique():
    # Show what IS there so you can fix the label rather than guess.
    kyivish = [v for v in df["oblast"].dropna().unique()
               if "kyiv" in str(v).lower()]
    sys.exit(f"STOP: '{KYIV_CITY_LABEL}' not found in the oblast column.\n"
             f"      Kyiv-like values present: {kyivish}\n"
             f"      Update KYIV_CITY_LABEL to match exactly.")

kyiv = df[df["oblast"] == KYIV_CITY_LABEL].copy()
n_kyiv_raw = len(kyiv)
print(f"  Kyiv City rows (before any cleaning): {n_kyiv_raw:,}")


# -----------------------------------------------------------------------------
# 3. LIMIT THE TIME WINDOW  (avoid post-Dec-2025 granularity change)
# -----------------------------------------------------------------------------
print("\n" + "-" * 70)
print("3. DATE WINDOW: 2022-03-15 .. 2025-11-30")
print("-" * 70)

kyiv = kyiv[(kyiv["started_at"] >= WINDOW_START) &
            (kyiv["started_at"] <= WINDOW_END)].copy()
n_after_window = len(kyiv)
print(f"  Kyiv City rows after date filtering: {n_after_window:,}")
print(f"  Removed by window filter:            {n_kyiv_raw - n_after_window:,}")


# -----------------------------------------------------------------------------
# 4. DUPLICATE CHECKS  (inside the Kyiv City subset)
# -----------------------------------------------------------------------------
# We measure duplicates AFTER filtering, because the full-dataset duplicate
# counts mix many regions and both granularity eras. Kyiv City may differ.
print("\n" + "-" * 70)
print("4. DUPLICATE CHECKS (Kyiv City subset)")
print("-" * 70)

n_exact = kyiv.duplicated().sum()
n_same_start = kyiv.duplicated(subset=["started_at"]).sum()
n_same_start_end = kyiv.duplicated(subset=["started_at", "finished_at"]).sum()

print(f"  (a) exact duplicate rows (all 7 columns identical): {n_exact:,}")
print(f"  (b) duplicate started_at values:                    {n_same_start:,}")
print(f"  (c) duplicate started_at + finished_at pairs:       {n_same_start_end:,}")


# -----------------------------------------------------------------------------
# 5. HANDLE DUPLICATES  (transparently, per category)
# -----------------------------------------------------------------------------
print("\n" + "-" * 70)
print("5. DUPLICATE HANDLING")
print("-" * 70)

# (a) Exact duplicates: safe to remove. An identical row in all 7 columns
#     carries no new information about a distinct alert.
before = len(kyiv)
kyiv = kyiv.drop_duplicates().copy()
removed_exact = before - len(kyiv)
print(f"  (a) Removed {removed_exact:,} exact duplicate row(s). "
      f"These are fully identical and add no information.")

# (b) Same started_at but DIFFERENT finished_at: do NOT auto-drop.
#     These are ambiguous (re-issued alert? differing end record?). We surface
#     them for your inspection and decision.
dup_start_mask = kyiv.duplicated(subset=["started_at"], keep=False)
conflicting = kyiv[dup_start_mask].sort_values("started_at")

# Among those sharing a start, how many also share the end vs. differ?
n_remaining_same_start = kyiv.duplicated(subset=["started_at"]).sum()
n_remaining_same_start_end = kyiv.duplicated(
    subset=["started_at", "finished_at"]).sum()
n_same_start_diff_end = n_remaining_same_start - n_remaining_same_start_end

print(f"\n  (b) After removing exact duplicates:")
print(f"      rows sharing a started_at with another row: {len(conflicting):,}")
print(f"      of those, same start & SAME end (still dup): {n_remaining_same_start_end:,}")
print(f"      of those, same start but DIFFERENT end:      {n_same_start_diff_end:,}")

if len(conflicting) > 0:
    print("\n      --- Inspection sample (first 20 rows sharing a start) ---")
    cols_to_show = ["oblast", "raion", "hromada", "level",
                    "started_at", "finished_at", "source"]
    print(conflicting[cols_to_show].head(20).to_string(index=False))
    print("\n      NOTE: these are shown, NOT dropped. Decide based on what you")
    print("      see: if 'source' differs, they may be the same alert recorded")
    print("      twice; if ends differ slightly, the alert may have been")
    print("      updated. Document your decision before removing any.")
else:
    print("\n      No remaining same-start rows to inspect.")

# We deliberately leave category (b) IN kyiv for now. Removing ambiguous
# records is a research decision, not an automatic cleaning step.


# -----------------------------------------------------------------------------
# 6. DURATION QUALITY  (Kyiv City only; audit, not analysis)
# -----------------------------------------------------------------------------
print("\n" + "-" * 70)
print("6. DURATION QUALITY (Kyiv City)")
print("-" * 70)

kyiv["duration_min"] = (
    kyiv["finished_at"] - kyiv["started_at"]
).dt.total_seconds() / 60.0

n_zero = (kyiv["duration_min"] == 0).sum()
n_negative = (kyiv["duration_min"] < 0).sum()
n_over_24h = (kyiv["duration_min"] > 24 * 60).sum()
n_exactly_30 = (kyiv["duration_min"] == 30).sum()

print(f"  zero-length durations:        {n_zero:,}")
print(f"  negative durations (end<start): {n_negative:,}")
print(f"  longer than 24 hours:         {n_over_24h:,}")
print(f"  exactly 30 minutes:           {n_exactly_30:,}")
print("\n  Reminder: 'exactly 30 min' may be estimated ends (per the dataset")
print("  README's naive=True convention). These affect DURATION work only.")
print("  Start-time clustering (the main analysis) does not depend on ends.")
print("\n  We are NOT removing duration outliers here - that is an analysis")
print("  decision for the relevant step, documented when made.")


# -----------------------------------------------------------------------------
# 7. FINALISE kyiv_clean
# -----------------------------------------------------------------------------
# kyiv_clean = Kyiv City, within the consistent window, with exact duplicates
# removed. Ambiguous same-start rows are retained and flagged above.
kyiv_clean = kyiv.sort_values("started_at").reset_index(drop=True)


# -----------------------------------------------------------------------------
# 8. SAVE
# -----------------------------------------------------------------------------
os.makedirs(OUT_DIR, exist_ok=True)
kyiv_clean.to_csv(OUT_PATH, index=False)
print("\n" + "-" * 70)
print("8. SAVED")
print("-" * 70)
print(f"  Wrote {len(kyiv_clean):,} rows to: {OUT_PATH}")


# -----------------------------------------------------------------------------
# 9. RECOUNTS + AUDIT VERDICT
# -----------------------------------------------------------------------------
print("\n" + "=" * 70)
print("ROW-COUNT TRAIL")
print("=" * 70)
print(f"  Kyiv City, raw:                {n_kyiv_raw:,}")
print(f"  after date window:             {n_after_window:,}")
print(f"  after exact-duplicate removal: {len(kyiv_clean):,}")
print(f"  cleaned date range:            "
      f"{kyiv_clean['started_at'].min()}  ..  {kyiv_clean['started_at'].max()}")

print("\n" + "=" * 70)
print("AUDIT VERDICT")
print("=" * 70)
print(f"  Is Kyiv City separable?      YES - distinct oblast value "
      f"('{KYIV_CITY_LABEL}'), {n_kyiv_raw:,} raw rows.")
print(f"  Are start times reliable?    "
      f"{'YES' if n_unparseable == 0 else 'CHECK'} - "
      f"0 missing in audit, parsed to UTC; "
      f"{n_unparseable} parse failures here.")
print(f"  Duplicates found & handled?  YES - removed {removed_exact:,} EXACT "
      f"duplicate(s); {n_same_start_diff_end:,} same-start/diff-end rows kept "
      f"and FLAGGED for manual review (not auto-dropped).")
print(f"  Suitable for the question?   "
      f"Start-time series is clean within the window, so the clustering")
print(f"                               question is answerable. Resolve the "
      f"flagged same-start rows before finalising.")
print("=" * 70)
print("\nDONE. Do NOT proceed to clustering until the flagged rows in")
print("section 5(b) have been reviewed and a documented decision made.")
