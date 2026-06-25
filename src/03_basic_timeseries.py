"""
=============================================================================
STEP 3 — BASIC TIME-SERIES ANALYSIS  (DESCRIPTIVE ONLY, NO CLUSTERING)
=============================================================================
Project : Time Series Analysis of Air Raid Alerts in Ukraine
Question: "How clustered in time are air raid alerts in Kyiv, and how did the
           degree of clustering vary across different periods of the war?"

Goal of this step:
    Get a first, honest look at the cleaned Kyiv City data:
      - how many alerts per day / per week,
      - how big the gaps between consecutive alerts are.
    This is GROUNDWORK. We do NOT detect clusters, do NOT run change point
    detection, and do NOT draw conclusions. We just describe and plot.

Input (from Step 2):
    data/processed/kyiv_city_alerts_clean.csv
    Known: 1,795 distinct Kyiv City alerts, 2022-03-15 .. 2025-11-29,
           no missing/zero/negative/over-24h/exact-30 durations.

Rules followed:
    - Use ONLY the cleaned file. No fake data, no assumed results.
    - Print real computed values. Stop loudly if the file won't load.
=============================================================================
"""

import os
import sys
import pandas as pd
import matplotlib.pyplot as plt

# -----------------------------------------------------------------------------
# 0. CONFIG
# -----------------------------------------------------------------------------
IN_PATH = "data/processed/kyiv_city_alerts_clean.csv"
FIG_DIR = "outputs/figures"


# -----------------------------------------------------------------------------
# 1. LOAD CLEANED DATA  (strict)
# -----------------------------------------------------------------------------
print("=" * 70)
print("STEP 3 — BASIC TIME-SERIES ANALYSIS (Kyiv City)")
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
# 2. PARSE TIMESTAMPS AS UTC
# -----------------------------------------------------------------------------
for col in ["started_at", "finished_at"]:
    if col not in df.columns:
        sys.exit(f"STOP: expected column '{col}' not found. "
                 f"Found: {list(df.columns)}")
    df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")

n_bad = df["started_at"].isna().sum()
if n_bad > 0:
    sys.exit(f"STOP: {n_bad} started_at value(s) failed to parse. "
             f"The cleaned file should have none - re-check Step 2.")


# -----------------------------------------------------------------------------
# 3. SORT BY START TIME
# -----------------------------------------------------------------------------
df = df.sort_values("started_at").reset_index(drop=True)


# -----------------------------------------------------------------------------
# 4. DAILY & WEEKLY ALERT COUNTS
# -----------------------------------------------------------------------------
# We index by start time, then resample. "D" = calendar day, "W" = week.
# resample fills empty days/weeks with 0, which is what we want for a timeline.
ts = df.set_index("started_at")

daily_counts = ts.resample("D").size()
weekly_counts = ts.resample("W").size()


# -----------------------------------------------------------------------------
# 5. INTER-EVENT GAPS  (start-to-start, in hours)
# -----------------------------------------------------------------------------
# gap[i] = start[i] - start[i-1]. The first row has no previous alert,
# so its gap is undefined and we drop it before computing statistics.
df["gap_hours"] = df["started_at"].diff().dt.total_seconds() / 3600.0
gaps = df["gap_hours"].dropna()   # drops the first row (NaT diff)


# -----------------------------------------------------------------------------
# 6. DESCRIPTIVE STATISTICS  (all real, computed values)
# -----------------------------------------------------------------------------
n_alerts = len(df)
date_min = df["started_at"].min()
date_max = df["started_at"].max()

# Average alerts per week: use the actual span, not the resampled mean,
# then also show the resample-based mean for cross-check.
span_days = (date_max - date_min).total_seconds() / 86400.0
span_weeks = span_days / 7.0
avg_per_week_span = n_alerts / span_weeks if span_weeks > 0 else float("nan")
avg_per_week_resample = weekly_counts.mean()

print("\n" + "-" * 70)
print("6. DESCRIPTIVE STATISTICS")
print("-" * 70)
print(f"  Number of alerts:            {n_alerts:,}")
print(f"  Date range:                  {date_min}  ..  {date_max}")
print(f"  Span:                        {span_days:.1f} days "
      f"(~{span_weeks:.1f} weeks)")
print(f"  Avg alerts/week (span-based):    {avg_per_week_span:.2f}")
print(f"  Avg alerts/week (weekly mean):   {avg_per_week_resample:.2f}")
print()
print(f"  Gaps between alert starts (hours), n = {len(gaps):,}")
print(f"    median gap:   {gaps.median():.2f} h")
print(f"    mean gap:     {gaps.mean():.2f} h")
print(f"    shortest gap: {gaps.min():.2f} h")
print(f"    longest gap:  {gaps.max():.2f} h")
print()
print("  Note: median vs mean gap differing a lot is just a description of")
print("  spread here - we are NOT interpreting it as clustering yet.")


# -----------------------------------------------------------------------------
# 7 & 8. CHARTS  (save to outputs/figures)
# -----------------------------------------------------------------------------
os.makedirs(FIG_DIR, exist_ok=True)

# Chart 1: weekly alert counts over time
plt.figure(figsize=(12, 4))
plt.plot(weekly_counts.index, weekly_counts.values, linewidth=1)
plt.title("Kyiv City — weekly air raid alert counts")
plt.xlabel("Week")
plt.ylabel("Alerts per week")
plt.tight_layout()
p1 = os.path.join(FIG_DIR, "weekly_alert_counts.png")
plt.savefig(p1, dpi=150)
plt.close()

# Chart 2: histogram of gaps between alert starts
# We cap the x-axis view at a sensible upper percentile so a few very long
# gaps don't squash the bulk of the distribution. We are NOT removing data,
# only adjusting what the axis shows.
plt.figure(figsize=(10, 4))
upper = gaps.quantile(0.99)
plt.hist(gaps[gaps <= upper], bins=60)
plt.title("Kyiv City — gaps between consecutive alert starts (<= 99th pct)")
plt.xlabel("Gap to previous alert (hours)")
plt.ylabel("Number of alerts")
plt.tight_layout()
p2 = os.path.join(FIG_DIR, "gap_histogram.png")
plt.savefig(p2, dpi=150)
plt.close()

# Chart 3: 30-day rolling alert count
# Sum of alerts in a trailing 30-day window, evaluated on the daily series.
rolling_30d = daily_counts.rolling(window=30, min_periods=1).sum()
plt.figure(figsize=(12, 4))
plt.plot(rolling_30d.index, rolling_30d.values, linewidth=1)
plt.title("Kyiv City — 30-day rolling alert count")
plt.xlabel("Date")
plt.ylabel("Alerts in trailing 30 days")
plt.tight_layout()
p3 = os.path.join(FIG_DIR, "rolling_30d_count.png")
plt.savefig(p3, dpi=150)
plt.close()

print("\n" + "-" * 70)
print("7-8. CHARTS SAVED")
print("-" * 70)
for p in (p1, p2, p3):
    print(f"  {p}")


# -----------------------------------------------------------------------------
# 9. END  (no clustering, no change points, no conclusions)
# -----------------------------------------------------------------------------
print("\n" + "=" * 70)
print("STEP 3 COMPLETE — descriptive groundwork only.")
print("Next decisions (do BEFORE clustering): see the explanation below.")
print("=" * 70)
