"""Export Prometheus metrics for a time window into a CSV file."""
import argparse
import os

import pandas as pd
import requests

PROM = "http://localhost:9090"

QUERIES = {
    "req_rate": 'sum(rate(app_requests_total[15s]))',
    "req_rate_cpu": 'sum(rate(app_requests_total{endpoint="/cpu"}[15s]))',
    "req_rate_memory": 'sum(rate(app_requests_total{endpoint="/memory"}[15s]))',
    "req_rate_io": 'sum(rate(app_requests_total{endpoint="/io"}[15s]))',
    "latency_mean_s": 'sum(rate(app_request_latency_seconds_sum[15s])) / sum(rate(app_request_latency_seconds_count[15s]))',
    "latency_p95_s": 'histogram_quantile(0.95, sum by (le) (rate(app_request_latency_seconds_bucket[30s])))',
    "app_cpu_cores": 'rate(process_cpu_seconds_total{job="app"}[15s])',
    "app_rss_mb": 'process_resident_memory_bytes{job="app"} / 1024 / 1024',
    "node_cpu_util": '1 - avg(rate(node_cpu_seconds_total{mode="idle"}[15s]))',
    "node_mem_util": '1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)',
    "net_rx_bytes_s": 'sum(rate(node_network_receive_bytes_total[15s]))',
    "net_tx_bytes_s": 'sum(rate(node_network_transmit_bytes_total[15s]))',
}


def query_range(expr, start, end, step):
    resp = requests.get(
        PROM + "/api/v1/query_range",
        params={"query": expr, "start": start, "end": end, "step": step},
        timeout=60,
    )
    resp.raise_for_status()
    result = resp.json()["data"]["result"]
    if not result:
        return None
    values = result[0]["values"]
    return pd.Series({pd.to_datetime(float(t), unit="s"): float(v) for t, v in values})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    parser.add_argument("--step", type=int, default=5)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    columns = {}
    for name, expr in QUERIES.items():
        series = query_range(expr, args.start, args.end, args.step)
        if series is None:
            print("WARNING: no data for", name)
        else:
            columns[name] = series

    df = pd.DataFrame(columns)
    df.index.name = "timestamp"
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    df.to_csv(args.out)

    print("Saved", args.out, "with", len(df), "rows and", len(df.columns), "columns")
    print(df.describe().T[["count", "mean", "min", "max"]].round(3).to_string())


if __name__ == "__main__":
    main()
