"""
Author: Aleksandro Matejic, 2025
Description:
This script fetches high-cardinality metrics from a Prometheus instance and checks if they are in use in Grafana dashboards or AlertManager alerts.
It saves the results in a JSON file and prints a summary to the console.

Depending on the amount of data, this script may take a while to run. It fetches the top N high-cardinality metrics and analyzes their labels.

Requirements:
- PROMETHEUS_URL: The URL of your Prometheus instance (e.g., http://localhost:9090)
- Results from get_all_dashboards.py should be in the "results" directory.
"""

import json
import os
import re
from collections import defaultdict

import requests

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL")  # e.g., http://localhost:9090
QUERIES_PATHS = [
    "results/grafana_promql_queries.txt",
    "results/grafana_specific_metric.txt",
    "results/alertmanager_promql_expressions.txt",
]
METRICS_SUMMARY_PATH = "results/metric_cardinality_summary.json"

NUMBER_TOP_METRICS = 10  # Enter the number of top metrics you want to fetch


def is_prometheus_healthy():
    try:
        response = requests.get(f"{PROMETHEUS_URL}/-/healthy")
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"Error connecting to Prometheus: {e}")
        return False


def fetch_top_cardinality_metrics(limit=NUMBER_TOP_METRICS):
    print(f"Fetching top {limit} high-cardinality metrics via PromQL...")
    try:
        query = f'topk({limit}, count by (__name__)({{__name__!=""}}))'
        response = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
        response.raise_for_status()
        results = response.json()["data"]["result"]
        return [
            {"metric": item["metric"]["__name__"], "series_count": int(item["value"][1])}
            for item in results
        ]
    except requests.RequestException as e:
        print(f"Error fetching top metrics: {e}")
        return []


def fetch_series_for_metric(metric_name):
    try:
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/series",
            params={"match[]": metric_name}
        )
        response.raise_for_status()
        return response.json()["data"]
    except requests.RequestException as e:
        print(f"Warning: Could not fetch series for metric {metric_name}: {e}")
        return []


def analyze_labels(series_data):

    print(f"Analyzing labels for {len(series_data)} series...")
    try:
        label_counter = defaultdict(set)
        for series in series_data:
            for label, value in series.items():
                if label != "__name__":
                    label_counter[label].add(value)
        print(f"Found {len(label_counter)} unique labels.")
        return {label: len(values) for label, values in label_counter.items()}
    except Exception as e:
        print(f"Error analyzing labels: {e}")
        return {}

def extract_metrics_and_labels_from_queries(paths):
    try:
        metric_pattern = re.compile(r"([a-zA-Z_:][a-zA-Z0-9_:]*)")
        label_pattern = re.compile(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*=")
        used_metrics = defaultdict(set)
        used_labels = set()

        for path in paths:
            if not os.path.exists(path):
                print(f"⚠️ Skipping missing query file: {path}")
                continue

            source = ""
            if "grafana_promql_queries.txt" in path:
                source = "grafana"
            elif "alertmanager_promql_expressions.txt" in path:
                source = "alertmanager"
            elif "specific_metric.txt" in path:
                source = "specific"

            try:
                with open(path) as f:
                    for line in f:
                        matches = metric_pattern.findall(line)
                        for match in matches:
                            used_metrics[match].add(source)

                        labels = label_pattern.findall(line)
                        used_labels.update(labels)
            except Exception as e:
                print(f"❌ Error reading {path}: {e}")

        return {k: list(v) for k, v in used_metrics.items()}, used_labels
    except Exception as e:
        print(f"Error extracting metrics and labels: {e}")
        return {}, set()


def main():
    if not PROMETHEUS_URL:
        raise EnvironmentError("PROMETHEUS_URL must be set")

    if not is_prometheus_healthy():
        print("Prometheus is not healthy. Exiting...")
        return
    print("Prometheus is healthy. Proceeding with cardinality analysis...")

    top_metrics = fetch_top_cardinality_metrics()
    used_metrics, used_labels = extract_metrics_and_labels_from_queries(QUERIES_PATHS)

    summary = []
    for item in top_metrics:
        metric = item["metric"]
        series_data = fetch_series_for_metric(metric)
        label_cardinality = analyze_labels(series_data)

        label_usage = {
            label: {
                "cardinality": count,
                "in_use": label in used_labels
            }
            for label, count in label_cardinality.items()
        }

        summary.append({
            "metric": metric,
            "series_count": item["series_count"],
            "in_use": metric in used_metrics,
            "used_in": used_metrics.get(metric, []),
            "labels": label_usage
        })

    print("\nHigh-cardinality metrics in use:")
    for item in sorted(summary, key=lambda x: -x["series_count"]):
        status = "✅ USED" if item["in_use"] else "❌ UNUSED"
        print(
            f"{item['metric']}: {item['series_count']} series - {status} ("
            f"{', '.join(item['used_in']) if item['used_in'] else 'not used'})"
        )

    os.makedirs(os.path.dirname(METRICS_SUMMARY_PATH), exist_ok=True)

    with open(METRICS_SUMMARY_PATH, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n💾 Saved metric summary to {METRICS_SUMMARY_PATH}")


if __name__ == "__main__":
    main()
