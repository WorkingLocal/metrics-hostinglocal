#!/usr/bin/env python3
"""
n8n workflow execution metrics exporter
Queriet de n8n PostgreSQL DB (via docker exec) en schrijft Prometheus textfile metrics.
Output: /var/lib/node_exporter/textfile_collector/n8n.prom
Cron: */5 * * * *
"""

import subprocess, json, time, os
from datetime import datetime, timezone

OUTFILE = "/var/lib/node_exporter/textfile_collector/n8n.prom"
CONTAINER = "autoba_postgres"
DB_USER = "n8n"
DB_NAME = "n8n"

QUERY = """
SELECT
    we.id AS workflow_id,
    we.name AS workflow_name,
    we.active,
    COUNT(*) FILTER (WHERE ee.status = 'success'
        AND ee."startedAt" > NOW() - INTERVAL '25 hours') AS success_25h,
    COUNT(*) FILTER (WHERE ee.status = 'error'
        AND ee."startedAt" > NOW() - INTERVAL '25 hours') AS error_25h,
    MAX(CASE WHEN ee.status = 'success' THEN
        EXTRACT(EPOCH FROM ee."startedAt") END) AS last_success_ts,
    MAX(CASE WHEN ee.status = 'error' THEN
        EXTRACT(EPOCH FROM ee."startedAt") END) AS last_error_ts,
    MAX(EXTRACT(EPOCH FROM ee."startedAt")) AS last_run_ts
FROM workflow_entity we
LEFT JOIN execution_entity ee ON ee."workflowId" = we.id
    AND ee."deletedAt" IS NULL
WHERE we.active = true
GROUP BY we.id, we.name, we.active
ORDER BY we.name;
"""

def run_query():
    result = subprocess.run(
        ["docker", "exec", CONTAINER, "psql", "-U", DB_USER, "-d", DB_NAME,
         "-t", "-A", "-F", "\t", "-c", QUERY],
        capture_output=True, text=True, timeout=15
    )
    if result.returncode != 0:
        raise RuntimeError(f"psql fout: {result.stderr}")
    return result.stdout.strip()

def escape_label(s):
    return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

def main():
    scrape_ts = int(time.time())
    lines = []
    lines.append("# HELP n8n_workflow_active Whether the workflow is active (1=yes)")
    lines.append("# TYPE n8n_workflow_active gauge")
    lines.append("# HELP n8n_workflow_success_25h Successful executions in last 25 hours")
    lines.append("# TYPE n8n_workflow_success_25h gauge")
    lines.append("# HELP n8n_workflow_error_25h Failed executions in last 25 hours")
    lines.append("# TYPE n8n_workflow_error_25h gauge")
    lines.append("# HELP n8n_workflow_last_success_timestamp Unix timestamp of last successful execution")
    lines.append("# TYPE n8n_workflow_last_success_timestamp gauge")
    lines.append("# HELP n8n_workflow_last_error_timestamp Unix timestamp of last failed execution")
    lines.append("# TYPE n8n_workflow_last_error_timestamp gauge")
    lines.append("# HELP n8n_workflow_last_run_timestamp Unix timestamp of last execution (any status)")
    lines.append("# TYPE n8n_workflow_last_run_timestamp gauge")
    lines.append(f"# HELP n8n_exporter_scrape_timestamp Unix timestamp of last exporter run")
    lines.append(f"# TYPE n8n_exporter_scrape_timestamp gauge")
    lines.append(f"n8n_exporter_scrape_timestamp {scrape_ts}")

    try:
        raw = run_query()
        for row in raw.splitlines():
            if not row.strip():
                continue
            parts = row.split('\t')
            if len(parts) < 8:
                continue
            wf_id, wf_name, active, ok_25h, err_25h, last_ok, last_err, last_run = parts
            label = f'workflow_id="{escape_label(wf_id)}",workflow_name="{escape_label(wf_name)}"'
            lines.append(f'n8n_workflow_active{{{label}}} {1 if active == "t" else 0}')
            lines.append(f'n8n_workflow_success_25h{{{label}}} {ok_25h or 0}')
            lines.append(f'n8n_workflow_error_25h{{{label}}} {err_25h or 0}')
            if last_ok and last_ok != '':
                lines.append(f'n8n_workflow_last_success_timestamp{{{label}}} {float(last_ok):.0f}')
            if last_err and last_err != '':
                lines.append(f'n8n_workflow_last_error_timestamp{{{label}}} {float(last_err):.0f}')
            if last_run and last_run != '':
                lines.append(f'n8n_workflow_last_run_timestamp{{{label}}} {float(last_run):.0f}')

        lines.append("# HELP n8n_exporter_up 1 if exporter ran successfully")
        lines.append("# TYPE n8n_exporter_up gauge")
        lines.append("n8n_exporter_up 1")

    except Exception as e:
        lines.append("# HELP n8n_exporter_up 1 if exporter ran successfully")
        lines.append("# TYPE n8n_exporter_up gauge")
        lines.append("n8n_exporter_up 0")
        lines.append(f"# ERROR: {e}")

    with open(OUTFILE, "w") as f:
        f.write("\n".join(lines) + "\n")

if __name__ == "__main__":
    main()
