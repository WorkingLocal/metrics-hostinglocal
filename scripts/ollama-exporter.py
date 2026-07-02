#!/usr/bin/env python3
"""
Ollama Prometheus exporter — schrijft metrics naar textfile_collector.
Bevraagt Ollama REST API op beide AI nodes (geen /metrics endpoint beschikbaar).
Cron: */5 * * * * /usr/bin/python3 /opt/metrics-hostinglocal/scripts/ollama-exporter.py >> /tmp/ollama-exporter.log 2>&1
"""
import json, time, urllib.request, urllib.error, os

NODES = {
    "VM-AI-NODE-I9": "http://100.64.1.25:11434",
    "VM-AI-NODE-I5": "http://100.101.48.4:11434",
}
OUTPUT_FILE = "/var/lib/node_exporter/textfile_collector/ollama.prom"

def fetch_json(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read()), None
    except Exception as e:
        return None, str(e)

def main():
    start = time.time()
    lines = []

    lines += [
        "# HELP ollama_up 1 if Ollama API is reachable",
        "# TYPE ollama_up gauge",
        "# HELP ollama_loaded_models Number of models currently loaded in VRAM",
        "# TYPE ollama_loaded_models gauge",
        "# HELP ollama_available_models Total number of models available on disk",
        "# TYPE ollama_available_models gauge",
        "# HELP ollama_model_loaded 1 if this model is currently loaded in VRAM",
        "# TYPE ollama_model_loaded gauge",
        "# HELP ollama_model_size_bytes Size of model on disk in bytes",
        "# TYPE ollama_model_size_bytes gauge",
        "# HELP ollama_model_vram_bytes VRAM used by loaded model in bytes",
        "# TYPE ollama_model_vram_bytes gauge",
    ]

    for node, base_url in NODES.items():
        n = f'node="{node}"'

        # Check liveness via /api/tags (lightweight)
        tags_data, tags_err = fetch_json(f"{base_url}/api/tags")
        if tags_err or tags_data is None:
            lines.append(f'ollama_up{{{n}}} 0')
            lines.append(f'ollama_loaded_models{{{n}}} 0')
            lines.append(f'ollama_available_models{{{n}}} 0')
            print(f"WARN {node}: {tags_err}")
            continue

        lines.append(f'ollama_up{{{n}}} 1')

        # Available models
        available = tags_data.get("models", [])
        lines.append(f'ollama_available_models{{{n}}} {len(available)}')
        for m in available:
            model_name = m.get("name", "unknown")
            size_bytes = m.get("size", 0)
            mn = f'node="{node}",model="{model_name}"'
            lines.append(f'ollama_model_size_bytes{{{mn}}} {size_bytes}')

        # Loaded models in VRAM via /api/ps
        ps_data, ps_err = fetch_json(f"{base_url}/api/ps")
        loaded_models = ps_data.get("models", []) if ps_data else []
        loaded_names = set()

        for m in loaded_models:
            model_name = m.get("name", "unknown")
            loaded_names.add(model_name)
            vram_bytes = m.get("size_vram", m.get("size", 0))
            mn = f'node="{node}",model="{model_name}"'
            lines.append(f'ollama_model_loaded{{{mn}}} 1')
            lines.append(f'ollama_model_vram_bytes{{{mn}}} {vram_bytes}')

        # Mark unloaded models
        for m in available:
            model_name = m.get("name", "unknown")
            if model_name not in loaded_names:
                mn = f'node="{node}",model="{model_name}"'
                lines.append(f'ollama_model_loaded{{{mn}}} 0')
                lines.append(f'ollama_model_vram_bytes{{{mn}}} 0')

        lines.append(f'ollama_loaded_models{{{n}}} {len(loaded_models)}')

    duration = time.time() - start
    lines += [
        "# HELP ollama_scrape_duration_seconds Duration of last Ollama scrape",
        "# TYPE ollama_scrape_duration_seconds gauge",
        f"ollama_scrape_duration_seconds {duration:.3f}",
    ]

    tmp = OUTPUT_FILE + ".tmp"
    with open(tmp, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(tmp, OUTPUT_FILE)
    print(f"OK — {duration:.2f}s, {len(lines)} lines")

if __name__ == "__main__":
    main()
