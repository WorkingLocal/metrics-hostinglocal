#!/usr/bin/env python3
"""
LiteLLM Prometheus exporter — schrijft spend data naar textfile_collector.
Cron: */5 * * * * /usr/bin/python3 /opt/metrics-hostinglocal/scripts/litellm-exporter.py >> /tmp/litellm-exporter.log 2>&1
"""
import json
import time
import urllib.request
import os
import re

LITELLM_URL = "http://100.80.180.55:4000"  # directe Tailscale — Cloudflare blokkeert admin endpoints
LITELLM_TOKEN = "HostingLocal2024"
OUTPUT_FILE = "/var/lib/node_exporter/textfile_collector/litellm_spend.prom"

def fetch(path):
    req = urllib.request.Request(
        LITELLM_URL + path,
        headers={"Authorization": f"Bearer {LITELLM_TOKEN}", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())

def label_safe(name):
    return re.sub(r"[^a-zA-Z0-9_]", "_", str(name)).strip("_")

def main():
    start = time.time()
    lines = []
    success = 1

    # Total spend + budget
    total_spend = 0.0
    max_budget = 0.0
    try:
        data = fetch("/global/spend")
        total_spend = float(data.get("spend") or 0)
        max_budget = float(data.get("max_budget") or 0)
    except Exception as e:
        print(f"ERROR /global/spend: {e}")
        success = 0

    lines += [
        "# HELP litellm_spend_total_dollars Total LLM API spend in USD",
        "# TYPE litellm_spend_total_dollars gauge",
        f"litellm_spend_total_dollars {total_spend:.6f}",
        "# HELP litellm_budget_dollars Configured budget limit in USD (0 = unlimited)",
        "# TYPE litellm_budget_dollars gauge",
        f"litellm_budget_dollars {max_budget:.6f}",
    ]

    # Spend per model
    try:
        model_data = fetch("/global/spend/models")
        lines += [
            "# HELP litellm_model_spend_dollars Cumulative spend per model in USD",
            "# TYPE litellm_model_spend_dollars gauge",
        ]
        for item in model_data:
            model = label_safe(item.get("model", "unknown"))
            spend = float(item.get("total_spend") or 0)
            lines.append(f'litellm_model_spend_dollars{{model="{model}"}} {spend:.6f}')

        has_tokens = any("total_tokens" in item for item in model_data)
        if has_tokens:
            lines += [
                "# HELP litellm_model_tokens_total Cumulative token count per model",
                "# TYPE litellm_model_tokens_total gauge",
            ]
            for item in model_data:
                model = label_safe(item.get("model", "unknown"))
                tokens = int(item.get("total_tokens") or 0)
                lines.append(f'litellm_model_tokens_total{{model="{model}"}} {tokens}')
    except Exception as e:
        print(f"ERROR /global/spend/models: {e}")
        success = 0

    # Spend per API key
    try:
        key_data = fetch("/global/spend/keys")
        lines += [
            "# HELP litellm_key_spend_dollars Cumulative spend per API key in USD",
            "# TYPE litellm_key_spend_dollars gauge",
        ]
        for item in key_data:
            key = label_safe(item.get("api_key") or item.get("key_alias") or "unknown")
            spend = float(item.get("total_spend") or 0)
            alias = label_safe(item.get("key_alias") or item.get("api_key") or "unknown")
            lines.append(f'litellm_key_spend_dollars{{key="{key}",alias="{alias}"}} {spend:.6f}')
    except Exception as e:
        print(f"ERROR /global/spend/keys: {e}")
        success = 0

    # Health: DB connected + version
    try:
        health = fetch("/health/readiness")
        db_ok = 1 if health.get("db") == "connected" else 0
        version = label_safe(health.get("litellm_version", "unknown"))
        lines += [
            "# HELP litellm_db_connected 1 if PostgreSQL DB is connected",
            "# TYPE litellm_db_connected gauge",
            f"litellm_db_connected {db_ok}",
            "# HELP litellm_up 1 if LiteLLM is healthy",
            "# TYPE litellm_up gauge",
            f'litellm_up{{version="{version}"}} 1',
        ]
    except Exception as e:
        print(f"ERROR /health/readiness: {e}")
        lines += [
            "# HELP litellm_db_connected 1 if PostgreSQL DB is connected",
            "# TYPE litellm_db_connected gauge",
            "litellm_db_connected 0",
            "# HELP litellm_up 1 if LiteLLM is healthy",
            "# TYPE litellm_up gauge",
            "litellm_up 0",
        ]
        success = 0

    # Model latency metrics (leeg totdat er traffic is)
    try:
        metrics = fetch("/model/metrics")
        model_list = metrics.get("data", [])
        if model_list:
            lines += [
                "# HELP litellm_model_latency_p50_seconds Median request latency per model",
                "# TYPE litellm_model_latency_p50_seconds gauge",
            ]
            for m in model_list:
                name = label_safe(m.get("model_name", "unknown"))
                p50 = float(m.get("p50_latency") or m.get("median_latency") or 0)
                lines.append(f'litellm_model_latency_p50_seconds{{model="{name}"}} {p50:.3f}')

            lines += [
                "# HELP litellm_model_latency_p99_seconds P99 request latency per model",
                "# TYPE litellm_model_latency_p99_seconds gauge",
            ]
            for m in model_list:
                name = label_safe(m.get("model_name", "unknown"))
                p99 = float(m.get("p99_latency") or 0)
                lines.append(f'litellm_model_latency_p99_seconds{{model="{name}"}} {p99:.3f}')

            lines += [
                "# HELP litellm_model_requests_total Total request count per model",
                "# TYPE litellm_model_requests_total gauge",
            ]
            for m in model_list:
                name = label_safe(m.get("model_name", "unknown"))
                reqs = int(m.get("total_requests") or m.get("num_requests") or 0)
                lines.append(f'litellm_model_requests_total{{model="{name}"}} {reqs}')
    except Exception as e:
        print(f"ERROR /model/metrics: {e}")
        success = 0

    duration = time.time() - start
    lines += [
        "# HELP litellm_scrape_success 1 if last LiteLLM scrape was successful",
        "# TYPE litellm_scrape_success gauge",
        f"litellm_scrape_success {success}",
        "# HELP litellm_scrape_duration_seconds Duration of last LiteLLM scrape in seconds",
        "# TYPE litellm_scrape_duration_seconds gauge",
        f"litellm_scrape_duration_seconds {duration:.3f}",
    ]

    tmp = OUTPUT_FILE + ".tmp"
    with open(tmp, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(tmp, OUTPUT_FILE)
    print(f"OK — {duration:.2f}s, spend=${total_spend:.4f}, success={success}")

if __name__ == "__main__":
    main()
