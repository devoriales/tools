"""
Author: Aleksandro Matejic, 2025
Description:
This script fetches all dashboards from a specified Grafana instance and extracts any PromQL queries found within them.
It saves the raw dashboards as JSON files and writes all PromQL queries to a separate text file. You can optionally filter queries by a specific metric name.
It also allows you to fetch alerts from an AlertManager instance and extract PromQL expressions from them.

Requirements:

The following environment variables must be set:
        •	GRAFANA_URL: The URL of your Grafana instance (e.g., http://localhost:3000)
        •	GRAFANA_SESSION_COOKIE: The Grafana session cookie used for authentication
        •	ALERTMANAGER_URL: The URL of your AlertManager instance (e.g., http://localhost:9093)
        •	ALERTMANAGER_SESSION_COOKIE: The AlertManager session cookie used for authentication

Output:
The results are saved in the following folder:
        •	results/
        •	dashboards.json: All dashboards metadata
        •	grafana_promql_queries.txt: All PromQL queries extracted from the dashboards
        •	grafana_specific_metric.txt: PromQL queries filtered by a specific metric name
        •	alertmanager_alerts.json: Raw alerts from AlertManager
        •	alertmanager_promql_expressions.txt: Unique PromQL expressions extracted from AlertManager alerts

Depending on the amount of data, this script may take a while to run. It fetches the top N high-cardinality metrics and analyzes their labels.

Why use this?

You might wonder why you’d want to extract all queries from Grafana. In my case, I needed to compare the PromQL queries used in dashboards with the results from the Prometheus promtool CLI.
The goal was to remove high-cardinality metrics and labels to reduce memory usage — but without breaking anything used in dashboards.
Also it helps to get expressions in AlertManager, which is not possible to get from Prometheus.

usage: python get_all_dashboards.py
"""

import json
import os
import re
import urllib.parse

import requests

GRAFANA_URL = os.getenv("GRAFANA_URL")  # example http://localhost:3000/
GRAFANA_SESSION_COOKIE = os.getenv("GRAFANA_SESSION_COOKIE")  # this is optional
ALERTMANAGER_URL = os.getenv("ALERTMANAGER_URL")  # example http://localhost:9093/
ALERTMANAGER_SESSION_COOKIE = os.getenv(
    "ALERTMANAGER_SESSION_COOKIE"
)  # this is optional


FOLDER_FOR_RESULTS = "results"
DASHBOARDS_FILE = "dashboards.json"
SPECIFIC_METRIC = "grafana_specific_metric.txt"  # this is optional
OUTPUT_DIR = "grafana_dashboards"
QUERY_FILE = "grafana_promql_queries.txt"
ALERT_MANAGER_FILE = "alertmanager_promql_expressions.txt"

headers = {}
if GRAFANA_SESSION_COOKIE:
    headers["Cookie"] = f"grafana_session={GRAFANA_SESSION_COOKIE}"


def load_dashboard_metadata():
    #  gets all dashboards
    url = f"{GRAFANA_URL.rstrip('/')}/api/search"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    dashboards = response.json()

    # saves dashboards metadata
    with open(FOLDER_FOR_RESULTS + "/" + DASHBOARDS_FILE, "w") as f:
        json.dump(dashboards, f, indent=2)
    print(f"✅ Saved dashboards metadata to {DASHBOARDS_FILE}")
    return dashboards


def fetch_specific_dashboard(uid):
    url = f"{GRAFANA_URL.rstrip('/')}/api/dashboards/uid/{uid}"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def extract_queries(dashboard_json):
    queries = []
    panels = dashboard_json.get("dashboard", {}).get("panels", [])
    for panel in panels:
        targets = panel.get("targets", [])
        for target in targets:
            expr = target.get("expr")
            if expr:
                title = dashboard_json["dashboard"]["title"]
                queries.append(f"{title}: {expr}")
    return queries


def extract_metric_from_generator_url(generator_url):
    parsed_url = urllib.parse.urlparse(generator_url)
    query_params = urllib.parse.parse_qs(parsed_url.query)
    promql_expr_encoded = query_params.get("g0.expr", [None])[0]

    if not promql_expr_encoded:
        return None

    promql_expr = urllib.parse.unquote(promql_expr_encoded)

    # Extract the first metric name from the expression
    match = re.match(r"([a-zA-Z_:][a-zA-Z0-9_:]*)", promql_expr)
    return match.group(1) if match else None


def extract_promql_expression(generator_url):
    parsed_url = urllib.parse.urlparse(generator_url)
    query_params = urllib.parse.parse_qs(parsed_url.query)
    promql_expr_encoded = query_params.get("g0.expr", [None])[0]

    if not promql_expr_encoded:
        return None

    return urllib.parse.unquote(promql_expr_encoded)


def get_alertmanager_metrics(alertmanager_url):
    headers = {}
    if ALERTMANAGER_SESSION_COOKIE:
        headers["Cookie"] = f"alertmanager_session={ALERTMANAGER_SESSION_COOKIE}"

    url = f"{alertmanager_url.rstrip('/')}/api/v2/alerts"
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    alerts = response.json()

    # Save raw alerts JSON
    with open("alertmanager_alerts.json", "w") as f:
        json.dump(alerts, f, indent=2)
    print("✅ Saved raw AlertManager alerts to alertmanager_alerts.json")

    # Extract and deduplicate metrics only
    expressions_set = set()
    for alert in alerts:
        expr = extract_promql_expression(alert.get("generatorURL", ""))
        if expr:
            expressions_set.add(expr)

    if expressions_set:
        # Save the unique PromQL expressions to a file in FOLDER_FOR_RESULTS
        with open(FOLDER_FOR_RESULTS + "/" + ALERT_MANAGER_FILE, "w") as f:
            f.write("\n\n".join(sorted(expressions_set)))
        print(
            "✅ Full PromQL expressions written to alertmanager_promql_expressions.txt"
        )
    else:
        print("⚠️ No PromQL expressions found in alerts.")


def clean_up_temp_files():
    # Clean up the dashboards folder
    if os.path.exists(OUTPUT_DIR):
        for filename in os.listdir(OUTPUT_DIR):
            file_path = os.path.join(OUTPUT_DIR, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
        print(f"✅ Cleaned up folder: {OUTPUT_DIR}")
    else:
        print(f"⚠️ Folder does not exist: {OUTPUT_DIR}")

    # if alertmanager alerts file exists, remove it
    if os.path.exists("alertmanager_alerts.json"):
        os.remove("alertmanager_alerts.json")
        print("✅ Cleaned up file: alertmanager_alerts.json")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(FOLDER_FOR_RESULTS, exist_ok=True)
    all_queries = []
    dashboards = load_dashboard_metadata()

    for dash in dashboards:
        uid = dash["uid"]
        title = dash["title"]
        print(f"Fetching dashboard: {title} (UID: {uid})")

        try:
            dashboard_json = fetch_specific_dashboard(uid)
            with open(f"{OUTPUT_DIR}/{uid}.json", "w") as f:
                json.dump(dashboard_json, f, indent=2)

            queries = extract_queries(dashboard_json)
            all_queries.extend(queries)

        except requests.RequestException as e:
            print(f"❌ Failed to fetch {title}: {e}")

    with open(FOLDER_FOR_RESULTS + "/" + QUERY_FILE, "w") as f:
        f.write("\n".join(all_queries))

    print(f"\n✅ Extracted {len(all_queries)} PromQL queries.")
    print(f"💾 Saved to {QUERY_FILE}")

    specific_metric = input(
        "Do you want to get a specific metric from the queries? (y/n): "
    )
    if specific_metric.lower() == "y":
        metric_name = input("Enter the metric name: ")
        filtered_queries = [query for query in all_queries if metric_name in query]
        if filtered_queries:
            print(f"Found {len(filtered_queries)} queries with metric '{metric_name}':")
            with open(FOLDER_FOR_RESULTS + "/" + SPECIFIC_METRIC, "w") as f:
                f.write("\n".join(filtered_queries))
            print(f"💾 Saved to {SPECIFIC_METRIC}")

        else:
            print(f"No queries found with metric '{metric_name}'.")

    alert_manager = input("Do you want to get alerts from AlertManager? (y/n): ")
    if alert_manager.lower() == "y":
        if not ALERTMANAGER_URL:
            raise EnvironmentError("ALERTMANAGER_URL must be set")
        get_alertmanager_metrics(ALERTMANAGER_URL)

    clean_up_temp_files()


if __name__ == "__main__":
    if not GRAFANA_URL or not GRAFANA_SESSION_COOKIE:
        raise EnvironmentError("GRAFANA_URL and GRAFANA_SESSION_COOKIE must be set")
    main()
