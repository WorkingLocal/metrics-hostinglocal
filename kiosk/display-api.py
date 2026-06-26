#!/usr/bin/env python3
"""
display-api.py — HTTP API voor HDMI display control op METRICSSERVER
Draait als systemd service (metrics user) op poort 8081.

Endpoints:
  GET /        → control panel HTML (Homarr iFrame widget)
  GET /on      → display aan   → {"status":"ok","display":"on"}
  GET /off     → display uit   → {"status":"ok","display":"off"}
  GET /status  → {"display":"on"|"off"}
"""
import http.server
import subprocess
import json
import os
from pathlib import Path

PORT = 8081
DISPLAY_CTRL = str(Path(__file__).parent / "display-ctrl.sh")
ENV = {**os.environ, "DISPLAY": ":2", "XAUTHORITY": "/home/metrics/.Xauthority"}

PANEL_HTML = """\
<!DOCTYPE html>
<html lang="nl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Display Control</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      background: #1e293b;
      color: #f1f5f9;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 100vh;
      gap: 10px;
    }
    .label {
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: .08em;
      color: #64748b;
    }
    .status-row {
      display: flex;
      align-items: center;
      gap: 5px;
      font-size: 12px;
      color: #94a3b8;
    }
    .dot {
      width: 8px; height: 8px;
      border-radius: 50%;
      background: #22c55e;
      flex-shrink: 0;
    }
    .dot.off { background: #475569; }
    .buttons { display: flex; gap: 8px; }
    button {
      padding: 7px 20px;
      border: 1px solid transparent;
      border-radius: 8px;
      cursor: pointer;
      font-size: 13px;
      font-weight: 600;
      transition: all .15s ease;
      letter-spacing: .02em;
    }
    button:active { transform: scale(.95); }
    button:disabled { opacity: .35; cursor: default; transform: none; }
    .btn-on  { background: #16a34a; color: #f0fdf4; border-color: #15803d; }
    .btn-on:not(:disabled):hover  { background: #15803d; }
    .btn-off { background: #1e293b; color: #94a3b8; border-color: #334155; }
    .btn-off:not(:disabled):hover { background: #0f172a; border-color: #475569; }
    .feedback { font-size: 11px; color: #64748b; min-height: 14px; }
  </style>
</head>
<body>
  <div class="label">Kiosk Display</div>
  <div class="status-row">
    <span class="dot" id="dot"></span>
    <span id="st">Laden…</span>
  </div>
  <div class="buttons">
    <button class="btn-on"  id="btn-on"  onclick="ctrl('on')">Aan</button>
    <button class="btn-off" id="btn-off" onclick="ctrl('off')">Uit</button>
  </div>
  <div class="feedback" id="fb"></div>
  <script>
    const dot  = document.getElementById('dot');
    const st   = document.getElementById('st');
    const fb   = document.getElementById('fb');
    const btns = [document.getElementById('btn-on'), document.getElementById('btn-off')];

    function setStatus(display) {
      const on = display === 'on';
      dot.className = 'dot' + (on ? '' : ' off');
      st.textContent = on ? 'Display aan' : 'Display uit';
    }

    function ctrl(action) {
      btns.forEach(b => b.disabled = true);
      fb.textContent = action === 'on' ? 'Inschakelen…' : 'Uitschakelen…';
      fetch('/' + action)
        .then(r => r.json())
        .then(d => { setStatus(d.display); fb.textContent = ''; })
        .catch(() => { fb.textContent = '⚠ Verbindingsfout'; })
        .finally(() => btns.forEach(b => b.disabled = false));
    }

    fetch('/status')
      .then(r => r.json())
      .then(d => setStatus(d.display))
      .catch(() => { dot.className = 'dot off'; st.textContent = 'Offline'; });
  </script>
</body>
</html>
"""


class DisplayHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send_json(self, data, code=200):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html, code=200):
        body = html.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _run_ctrl(self, action):
        r = subprocess.run([DISPLAY_CTRL, action], capture_output=True, env=ENV)
        return r.returncode == 0

    def _get_status(self):
        r = subprocess.run(["xset", "-q"], capture_output=True, text=True, env=ENV)
        return "off" if "Monitor is Off" in r.stdout else "on"

    def do_GET(self):
        if self.path in ("/on", "/off"):
            action = self.path[1:]
            ok = self._run_ctrl(action)
            self._send_json({"status": "ok" if ok else "error",
                             "display": action if ok else "unknown"})
        elif self.path == "/status":
            self._send_json({"display": self._get_status()})
        elif self.path in ("/", "/index.html"):
            self._send_html(PANEL_HTML)
        else:
            self._send_json({"error": "not found"}, 404)


if __name__ == "__main__":
    server = http.server.HTTPServer(("0.0.0.0", PORT), DisplayHandler)
    print(f"Display API :{PORT}")
    server.serve_forever()
