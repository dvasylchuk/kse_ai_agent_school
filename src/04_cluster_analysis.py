"""
=============================================================================
STEP 4 — DEFINE & MEASURE ALERT CLUSTERS  (NO CHANGE POINT DETECTION)
=============================================================================
Project : Time Series Analysis of Air Raid Alerts in Ukraine
Question: "How clustered in time are air raid alerts in Kyiv, and how did the
           degree of clustering vary across different periods of the war?"

Goal of this step:
    Turn the vague idea of "alerts in a series" into a concrete, measurable
    definition, then describe how much of the data falls into such series.
    We do NOT run change point detection, do NOT draw final conclusions,
    and make NO prediction or causal claims.

Cluster definition (gap-threshold rule):
    Walk through alerts in time order. If the gap from the previous alert
    start to the current alert start is <= N hours, the current alert joins
    the same cluster. If the gap is > N hours, a NEW cluster begins.
    A "cluster" can therefore be a single isolated alert (size 1) or a run
    of several alerts close together (size >= 2).

Main threshold: N = 6 hours.
Sensitivity check: N = 3, 6, 12 hours (to see if conclusions are fragile).

Input (from Step 2/3):
    data/processed/kyiv_city_alerts_clean.csv
    Known: 1,795 alerts, 2022-03-15 .. 2025-11-29.

Rules followed:
    - Use ONLY the cleaned file. No fake data, no assumed results.
    - Print real computed values. Stop loudly on any problem.
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
TABLE_DIR = "outputs/tables"
FIG_DIR = "outputs/figures"

MAIN_THRESHOLD = 6                 # hours - main cluster definition
THRESHOLDS = [3, 6, 12]            # hours - sensitivity sweep


# -----------------------------------------------------------------------------
# 1. LOAD CLEANED DATA  (strict)
# -----------------------------------------------------------------------------
print("=" * 70)
print("STEP 4 — ALERT CLUSTER DEFINITION & MEASUREMENT (Kyiv City)")
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
# Row 0 has gap_hours = NaN (no previous alert) - handled in step 4.


# -----------------------------------------------------------------------------
# 4. ASSIGN CLUSTER IDS FOR A GIVEN THRESHOLD
# -----------------------------------------------------------------------------
def assign_clusters(frame, threshold_hours):
    """Return a cluster id per row for the given gap threshold (hours).

    A new cluster starts when the gap to the previous alert exceeds the
    threshold. The first alert always starts cluster 0. The result is a
    simple integer label (0, 1, 2, ...) in time order.
    """
    gaps = frame["gap_hours"].to_numpy()
    cluster_ids = []
    current = 0
    for i, g in enumerate(gaps):
        if i == 0:
            cluster_ids.append(current)        # first alert -> cluster 0
            continue
        if g > threshold_hours:                 # gap too big -> new cluster
            current += 1
        cluster_ids.append(current)
    return cluster_ids


# -----------------------------------------------------------------------------
# 5. SUMMARISE CLUSTERS FOR A GIVEN THRESHOLD
# -----------------------------------------------------------------------------
def summarise(frame, threshold_hours):
    """Compute cluster metrics for one threshold. Returns (summary_dict,
    labelled_frame) so the caller can reuse the labels for the main run."""
    f = frame.copy()
    f["cluster_id"] = assign_clusters(f, threshold_hours)

    # Size of each cluster = number of alerts sharing that cluster_id.
    sizes = f.groupby("cluster_id").size()

    # Cluster "duration" = first start to last start within the cluster.
    starts = f.groupby("cluster_id")["started_at"]
    span_hours = ((starts.max() - starts.min()).dt.total_seconds() / 3600.0)

    total_clusters = len(sizes)
    single = int((sizes == 1).sum())
    multi = int((sizes >= 2).sum())
    n_alerts = len(f)
    alerts_in_multi = int(sizes[sizes >= 2].sum())
    share_multi = alerts_in_multi / n_alerts if n_alerts else float("nan")

    summary = {
        "threshold_hours": threshold_hours,
        "total_clusters": total_clusters,
        "single_alert_clusters": single,
        "multi_alert_clusters": multi,
        "alerts_in_multi_clusters": alerts_in_multi,
        "share_alerts_in_multi": round(share_multi, 4),
        "avg_cluster_size": round(sizes.mean(), 3),
        "max_cluster_size": int(sizes.max()),
        # median span across MULTI-alert clusters only (single alerts span 0h
        # by definition, which would drag the median to 0 and hide signal).
        "median_multi_cluster_span_h": round(
            span_hours[sizes >= 2].median(), 3) if multi else 0.0,
    }
    return summary, f


# -----------------------------------------------------------------------------
# 6. RUN THE SENSITIVITY SWEEP (3, 6, 12 h)
# -----------------------------------------------------------------------------
print("\n" + "-" * 70)
print("6. SENSITIVITY SWEEP — cluster metrics at 3h / 6h / 12h")
print("-" * 70)

rows = []
labelled_main = None
for t in THRESHOLDS:
    summary, labelled = summarise(df, t)
    rows.append(summary)
    if t == MAIN_THRESHOLD:
        labelled_main = labelled

summary_df = pd.DataFrame(rows)
print(summary_df.to_string(index=False))

os.makedirs(TABLE_DIR, exist_ok=True)
summary_path = os.path.join(TABLE_DIR, "cluster_summary_thresholds.csv")
summary_df.to_csv(summary_path, index=False)
print(f"\n  Saved: {summary_path}")

if labelled_main is None:
    sys.exit(f"STOP: main threshold {MAIN_THRESHOLD}h was not in {THRESHOLDS}.")


# -----------------------------------------------------------------------------
# 7. MAIN-THRESHOLD DETAIL (6 h)
# -----------------------------------------------------------------------------
print("\n" + "-" * 70)
print(f"7. DETAIL FOR MAIN THRESHOLD = {MAIN_THRESHOLD}h")
print("-" * 70)

f = labelled_main

# --- 7a. Top 10 largest clusters ---
sizes = f.groupby("cluster_id").size()
grp = f.groupby("cluster_id")["started_at"]
cluster_table = pd.DataFrame({
    "cluster_id": sizes.index,
    "n_alerts": sizes.values,
    "first_start": grp.min().values,
    "last_start": grp.max().values,
})
cluster_table["span_hours"] = (
    (pd.to_datetime(cluster_table["last_start"], utc=True)
     - pd.to_datetime(cluster_table["first_start"], utc=True))
    .dt.total_seconds() / 3600.0
).round(2)

top10 = cluster_table.sort_values("n_alerts", ascending=False).head(10)
print("\n  Top 10 largest alert clusters (6h rule):")
print(top10.to_string(index=False))

top10_path = os.path.join(TABLE_DIR, "top_10_clusters_6h.csv")
top10.to_csv(top10_path, index=False)
print(f"\n  Saved: {top10_path}")

# --- 7b. War-phase comparison of cluster share ---
# Phases are analytical conveniences, NOT objective facts. Stated plainly.
def war_phase(ts):
    y = ts.year
    if y == 2022:
        return "2022"
    if y == 2023:
        return "2023"
    if y == 2024:
        return "2024"
    return "2025"

# An alert is "in a multi-alert cluster" if its cluster has size >= 2.
f = f.copy()
f["in_multi"] = f["cluster_id"].map(sizes >= 2).astype(int)
f["phase"] = f["started_at"].apply(war_phase)

phase_share = f.groupby("phase")["in_multi"].mean().round(4)
phase_counts = f.groupby("phase").size()
print("\n  Share of alerts in multi-alert clusters, by phase (6h):")
for ph in sorted(phase_share.index):
    print(f"    {ph}: {phase_share[ph]:.1%}  (n = {phase_counts[ph]:,} alerts)")

plt.figure(figsize=(8, 4))
plt.bar(phase_share.index.astype(str), phase_share.values)
plt.title(f"Kyiv City — share of alerts in multi-alert clusters by phase "
          f"({MAIN_THRESHOLD}h rule)")
plt.xlabel("War phase (year)")
plt.ylabel("Share of alerts in multi-alert clusters")
plt.ylim(0, 1)
plt.tight_layout()
os.makedirs(FIG_DIR, exist_ok=True)
p_phase = os.path.join(FIG_DIR, "cluster_share_by_phase_6h.png")
plt.savefig(p_phase, dpi=150)
plt.close()
print(f"\n  Saved: {p_phase}")

# --- 7c. Monthly time series of cluster share ---
monthly_share = (f.set_index("started_at")["in_multi"]
                 .resample("ME").mean())
plt.figure(figsize=(12, 4))
plt.plot(monthly_share.index, monthly_share.values, linewidth=1, marker="o",
         markersize=3)
plt.title(f"Kyiv City — monthly share of alerts in multi-alert clusters "
          f"({MAIN_THRESHOLD}h rule)")
plt.xlabel("Month")
plt.ylabel("Share in multi-alert clusters")
plt.ylim(0, 1)
plt.tight_layout()
p_month = os.path.join(FIG_DIR, "cluster_share_by_month_6h.png")
plt.savefig(p_month, dpi=150)
plt.close()
print(f"  Saved: {p_month}")


# -----------------------------------------------------------------------------
# 8. END  (no change point detection, no conclusions)
# -----------------------------------------------------------------------------
print("\n" + "=" * 70)
print("STEP 4 COMPLETE — clusters defined and measured (descriptive only).")
print("No change point detection, no conclusions drawn. See notes below.")
print("=" * 70)
