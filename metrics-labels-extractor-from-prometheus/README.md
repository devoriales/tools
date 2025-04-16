# PromQL Query Extractor and Cardinality Analyzer

## Overview

This tool extracts PromQL queries from Grafana dashboards and AlertManager alerts, then analyzes high-cardinality metrics and labels in Prometheus. It helps identify which metrics and labels are actively used, allowing you to clean up unused data without affecting dashboards or alerts.

## Author
**Aleksandro Matejic, 2025**

## Blog Post
**[Prometheus: How We Slashed Memory Usage](https://devoriales.com/post/384/prometheus-how-we-slashed-memory-usage)**


## Purpose

In large Prometheus environments, excessive high-cardinality metrics and labels can lead to high memory usage, slow queries, and degraded performance. This toolset helps you:

- Audit PromQL queries in dashboards and alerting rules
- Analyze which metrics and labels are truly used
- Safely reduce cardinality by removing or limiting unused metrics and labels

## Usage Instructions

### Step 1: Extract Dashboard and Alert Queries

First, extract all relevant PromQL queries:

```bash
export GRAFANA_URL="http://localhost:3000"
export GRAFANA_SESSION_COOKIE="your_grafana_cookie"
export ALERTMANAGER_URL="http://localhost:9093"
export ALERTMANAGER_SESSION_COOKIE="your_alertmanager_cookie"
python get_all_dashboards.py
```

You will be prompted:
- Whether to extract queries for a **specific metric**
- Whether to fetch alerts from **AlertManager**

Example output:
```
✅ Extracted 340 PromQL queries.
💾 Saved to grafana_promql_queries.txt
Found 26 queries with metric 'nginx':
💾 Saved to grafana_specific_metric.txt
✅ Full PromQL expressions written to alertmanager_promql_expressions.txt
```

### Step 2: Analyze Metric and Label Cardinality

Now that queries have been extracted, analyze the top metrics and labels by cardinality:

```bash
export PROMETHEUS_URL="http://localhost:9090"
python cardinality_analysis_script.py
```

This will fetch the top 10 metrics by number of active series and:
- Compare them to the PromQL queries you extracted
- Fetch their labels and count unique values
- Determine if metrics/labels are used by dashboards or alerts

Example output:
```
High-cardinality metrics in use:
nginx_ingress_controller_request_duration_seconds_bucket: 438900 series - ✅ USED (specific, grafana)
nginx_ingress_controller_request_size_bucket: 402325 series - ❌ UNUSED (not used)
...
💾 Saved metric summary to results/metric_cardinality_summary.json
```

## How to Interpret the Results

Open `results/metric_cardinality_summary.json`. Each entry looks like this:

```json
{
  "metric": "nginx_ingress_controller_request_duration_seconds_bucket",
  "series_count": 438900,
  "in_use": true,
  "used_in": ["grafana"],
  "labels": {
    "ingress": {
      "cardinality": 1105,
      "in_use": true
    },
    "host": {
      "cardinality": 1104,
      "in_use": false
    }
  }
}
```

### Fields Explained:
- `metric`: Name of the metric
- `series_count`: Number of unique series (total cardinality)
- `in_use`: Whether the metric is used in any query (dashboard or alert)
- `used_in`: Which component(s) use this metric (`grafana`, `alertmanager`, `specific`)
- `labels`: A breakdown of each label:
  - `cardinality`: Number of unique values for the label
  - `in_use`: Whether this label is referenced in any query expression

## Suggestions for Cleanup

1. **Drop metrics not in use:** If `in_use` is `false` and `series_count` is high, consider removing the metric from exporters or scrape configs.

2. **Drop labels not in use:** Labels with high cardinality and `in_use: false` are costly and unused. Remove them using relabeling or exporter config.

3. **Keep used metrics/labels safe:** Do not drop anything marked as `in_use: true` unless you are sure it’s no longer needed.


## Output Files

- `results/grafana_promql_queries.txt`: All PromQL queries from Grafana
- `results/alertmanager_promql_expressions.txt`: All PromQL expressions from AlertManager
- `results/grafana_specific_metric.txt`: Optional file for filtered metric
- `results/metric_cardinality_summary.json`: Final report showing metric and label cardinality with usage info

## Security

- Use environment variables to manage sensitive cookies
- Output files may contain internal metric names — treat them as confidential

## License

MIT or as defined by the author
