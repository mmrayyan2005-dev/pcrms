"""First look at run1.csv: data quality checks and an overview chart."""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

df = pd.read_csv("data/raw/run1.csv", parse_dates=["timestamp"], index_col="timestamp")
print("rows:", len(df), "| from", df.index.min(), "to", df.index.max())

print("\nMissing values per column:")
print(df.isna().sum().to_string())

print("\nImpossible or suspicious values:")
print("node_cpu_util < 0:", int((df["node_cpu_util"] < 0).sum()), "| > 1:", int((df["node_cpu_util"] > 1).sum()))
print("app_cpu_cores > 1.0:", int((df["app_cpu_cores"] > 1.0).sum()))
print("req_rate > 55 (peak target is 50):", int((df["req_rate"] > 55).sum()))

gaps = df.index.to_series().diff().dropna()
print("\nTimestamp steps that are not 5s:", int((gaps != pd.Timedelta(seconds=5)).sum()))

active = df[df["req_rate"] > 0.5]
print("\nActive rows (req_rate > 0.5):", len(active), "= about", round(len(active) * 5 / 60, 1), "minutes")
print(active.describe().T[["mean", "min", "50%", "max"]].round(3).to_string())

fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)
df["req_rate"].plot(ax=axes[0], title="Requests per second")
df[["latency_mean_s", "latency_p95_s"]].plot(ax=axes[1], logy=True, title="Latency in seconds (log scale)")
df[["app_cpu_cores", "node_cpu_util"]].plot(ax=axes[2], title="CPU")
df["app_rss_mb"].plot(ax=axes[3], title="App memory (MB)")
plt.tight_layout()
os.makedirs("docs", exist_ok=True)
plt.savefig("docs/eda_run1.png", dpi=110)
os.makedirs("/mnt/d/PCRMS_plots", exist_ok=True)
plt.savefig("/mnt/d/PCRMS_plots/eda_run1.png", dpi=110)
print("\nSaved chart to docs/eda_run1.png and D:\\PCRMS_plots\\eda_run1.png")
