"""
=============================================================================
STEP 5 — ROLLING BURSTINESS  (NO CHANGE POINT DETECTION)
=============================================================================
Project : Time Series Analysis of Air Raid Alerts in Ukraine
Question: "How clustered in time are air raid alerts in Kyiv, and how did the
           degree of clustering vary across different periods of the war?"

Goal of this step:
    Measure how "bursty" the TIMING of Kyiv alerts was, using a simple,
    threshold-free indicator (the burstiness parameter B), and track how it
    moved over time in rolling windows. This complements Step 4's cluster
    share, which used a chosen gap threshold.

The burstiness parameter (Goh & Barabasi, 2008):
    B = (std_gap - mean_gap) / (std_gap + mean_gap)
    where the gaps are the times between consecutive alert starts.
      B near 0   -> spacing close to random/even (Poisson-like)
      B  > 0     -> more bursty / clustered timing (many short gaps, some long)
      B  < 0     -> more regular / evenly-spaced timing
    B is bounded between -1 and +1.

Input (from Step 2/3/4):
    data/processed/kyiv_city_alerts_clean.csv
    Known: 1,795 alerts, 2022-03-15 .. 2025-11-29.

Rules followed:
    - Use ONLY the cleaned file. No fake data, no assumed results.
    - Print real computed values. Stop loudly on any problem.
    - No change point detection, no causal claims, no military interpretation.
=============================================================================
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# -----------------------------------------------------------------------------
# 0. CONFIG
# -----------------------------------------------------------------------------
IN_PATH = "data/processed/kyiv_city_alerts_clean.csv"
TABLE_DIR = "outputs/tables"
FIG_DIR = "outputs/figures"

MAIN_WINDOW_DAYS = 30        # main rolling window
ROBUST_WINDOW_DAYS = 60      # robustness rolling window
MIN_GAPS = 5                 # require >= this many gaps per window for a valid B


# -----------------------------------------------------------------------------
# 1. LOAD CLEANED DATA  (strict)
# -----------------------------------------------------------------------------
print("=" * 70)
print("STEP 5 — ROLLING BURSTINESS (Kyiv City)")
print("=" * 70)

try:
    df = pd.read_csv(IN_PATH)
except Exception as e:
    sys.exit(f"STOP: could not load {IN_PATH}\n"
             f"      Reason: {type(e).__name__}: {e}\n"
             f"      Run Step 2 first to create the cleaned file.")

if len(df) == 0:
    sys.exit("STOP: cleaned file loaded but has 0 rows.")
print(f"\nLoaded cleaned dataset: {len(df):,} rows.")


# -----------------------------------------------------------------------------
# 2. PARSE & SORT
# -----------------------------------------------------------------------------
if "started_at" not in df.columns:
    sys.exit(f"STOP: 'started_at' not found. Found: {list(df.columns)}")

df["started_at"] = pd.to_datetime(df["started_at"], utc=True, errors="coerce")
if df["started_at"].isna().any():
    sys.exit("STOP: some started_at values failed to parse. Re-check Step 2.")

df = df.sort_values("started_at").reset_index(drop=True)


# -----------------------------------------------------------------------------
# 3. GAPS BETWEEN CONSECUTIVE STARTS (hours)
# -----------------------------------------------------------------------------
df["gap_hours"] = df["started_at"].diff().dt.total_seconds() / 3600.0
# Row 0 has NaN gap. We attach each gap to the time of the CURRENT alert,
# so a rolling window "as of date D" uses gaps from alerts that occurred
# up to D. Drop the first row (no gap).
gaps_df = df.dropna(subset=["gap_hours"]).copy()
gaps_df = gaps_df[["started_at", "gap_hours"]].reset_index(drop=True)


# -----------------------------------------------------------------------------
# 4. BURSTINESS HELPER
# -----------------------------------------------------------------------------
def burstiness(gap_values):
    """B = (std - mean) / (std + mean) for a set of gaps.
    Returns NaN if there are too few values or the denominator is ~0."""
    g = np.asarray(gap_values, dtype=float)
    if len(g) < MIN_GAPS:
        return np.nan
    mean = g.mean()
    std = g.std(ddof=1)          # sample std; needs >= 2 points (MIN_GAPS >= 5)
    denom = std + mean
    if denom == 0:
        return np.nan
    return (std - mean) / denom


# -----------------------------------------------------------------------------
# 5. OVERALL B FOR THE WHOLE PERIOD
# -----------------------------------------------------------------------------
overall_B = burstiness(gaps_df["gap_hours"].to_numpy())
print("\n" + "-" * 70)
print("5. OVERALL BURSTINESS (full period)")
print("-" * 70)
print(f"  B (all {len(gaps_df):,} gaps) = {overall_B:.4f}")
print("  Reading: B>0 = bursty, B~0 = random/even, B<0 = regular.")


# -----------------------------------------------------------------------------
# 6. ROLLING B OVER A TIME WINDOW
# -----------------------------------------------------------------------------
def rolling_burstiness(gframe, window_days):
    """Compute B as of each alert time, using gaps within the trailing
    `window_days`. Returns a DataFrame: date, n_gaps, B.

    This is a TIME-based window (not a fixed number of alerts), so quiet
    periods naturally contain fewer gaps - we require MIN_GAPS for validity.
    """
    times = gframe["started_at"].to_numpy()
    vals = gframe["gap_hours"].to_numpy()
    window = pd.Timedelta(days=window_days)

    out_dates, out_n, out_B = [], [], []
    for i in range(len(gframe)):
        end_t = times[i]
        start_t = end_t - window
        # gaps whose alert time is within (start_t, end_t]
        mask = (times > start_t) & (times <= end_t)
        w = vals[mask]
        out_dates.append(end_t)
        out_n.append(len(w))
        out_B.append(burstiness(w))

    return pd.DataFrame({"date": out_dates, "n_gaps": out_n, "B": out_B})


def save_rolling(window_days, table_name, fig_name):
    roll = rolling_burstiness(gaps_df, window_days)
    valid = roll.dropna(subset=["B"])

    os.makedirs(TABLE_DIR, exist_ok=True)
    tpath = os.path.join(TABLE_DIR, table_name)
    roll.to_csv(tpath, index=False)

    # Plot only valid points; reference line at B=0 (random/even baseline).
    os.makedirs(FIG_DIR, exist_ok=True)
    plt.figure(figsize=(12, 4))
    plt.plot(valid["date"], valid["B"], linewidth=1)
    plt.axhline(0, color="gray", linewidth=0.8, linestyle="--")
    plt.title(f"Kyiv City — rolling burstiness B ({window_days}-day window, "
              f">= {MIN_GAPS} gaps)")
    plt.xlabel("Date")
    plt.ylabel("Burstiness B")
    plt.ylim(-1, 1)
    plt.tight_layout()
    fpath = os.path.join(FIG_DIR, fig_name)
    plt.savefig(fpath, dpi=150)
    plt.close()

    return roll, valid, tpath, fpath


print("\n" + "-" * 70)
print(f"6. ROLLING B — main {MAIN_WINDOW_DAYS}d and robustness "
      f"{ROBUST_WINDOW_DAYS}d windows")
print("-" * 70)

roll30, valid30, t30, f30 = save_rolling(
    MAIN_WINDOW_DAYS, "rolling_burstiness_30d.csv", "rolling_burstiness_30d.png")
roll60, valid60, t60, f60 = save_rolling(
    ROBUST_WINDOW_DAYS, "rolling_burstiness_60d.csv", "rolling_burstiness_60d.png")

print(f"  Saved: {t30}")
print(f"  Saved: {f30}")
print(f"  Saved: {t60}")
print(f"  Saved: {f60}")


# -----------------------------------------------------------------------------
# 7. SUMMARY PRINTS  (main 30-day window)
# -----------------------------------------------------------------------------
print("\n" + "-" * 70)
print(f"7. ROLLING B SUMMARY (main {MAIN_WINDOW_DAYS}-day window)")
print("-" * 70)

n_total = len(roll30)
n_valid = len(valid30)
print(f"  Rolling windows evaluated:        {n_total:,}")
print(f"  Valid windows (>= {MIN_GAPS} gaps):       {n_valid:,}")
print(f"  Invalid (too few gaps):           {n_total - n_valid:,}")

if n_valid > 0:
    print(f"  Min rolling B:  {valid30['B'].min():.4f}")
    print(f"  Max rolling B:  {valid30['B'].max():.4f}")

    # Average rolling B by year (valid windows only).
    by_year = valid30.copy()
    by_year["year"] = pd.to_datetime(by_year["date"], utc=True).dt.year
    yearly = by_year.groupby("year")["B"].agg(["mean", "count"]).round(4)
    print("\n  Average rolling B by year (valid 30d windows only):")
    for yr, row in yearly.iterrows():
        print(f"    {yr}: mean B = {row['mean']:.4f}  "
              f"(n = {int(row['count'])} windows)")
else:
    print("  No valid windows - check MIN_GAPS or the data span.")


# -----------------------------------------------------------------------------
# 8. END
# -----------------------------------------------------------------------------
print("\n" + "=" * 70)
print("STEP 5 COMPLETE — rolling burstiness measured (descriptive only).")
print("No change point detection, no causal/military claims. See notes below.")
print("=" * 70)
