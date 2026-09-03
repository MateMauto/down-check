"""A tiny web view for down-check"""
from __future__ import annotations

import asyncio
import html
import socket
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from down_check.catalog import Service
from down_check.checks import Result, Status, check_all, check_reports

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000


def _lan_ip() -> str:
    """The address other devices on the network can reach this machine on."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def _collect(services: list[Service]) -> tuple[list[Result], list[Result]]:
    """Run the same checks as `down-check check`: status pages, then user reports."""
    results = asyncio.run(check_all(services))
    problems = [r.service for r in results if r.is_problem]
    reports: list[Result] = []
    if problems:
        fallback = asyncio.run(check_reports(problems))
        if any(r.status is not Status.UNKNOWN for r in fallback):
            reports = fallback
    return results, reports


# ── HTML ─────────────────────────────────────────────────────────────────────

_STYLES = """
:root {
  --bg: #0d1017;
  --panel: #141925;
  --border: #232b3b;
  --text: #e8ecf4;
  --muted: #8a94a7;
  --ok: #3fb950;
  --degraded: #d29922;
  --down: #f85149;
  --unknown: #8a94a7;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 24px 16px 48px;
  background: var(--bg);
  color: var(--text);
  font: 15px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}
.wrap { max-width: 640px; margin: 0 auto; }
header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
h1 { margin: 0; font-size: 20px; letter-spacing: -0.02em; }
.refresh {
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--panel);
  color: var(--text);
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
  cursor: pointer;
}
.refresh:hover { border-color: var(--muted); }
.meta { margin: 0 0 14px; color: var(--muted); font-size: 13px; }
.summary { margin: 0 0 14px; font-size: 13px; }
.summary span { font-weight: 600; margin-right: 12px; }
.summary .ok, .badge.ok { color: var(--ok); }
.summary .degraded, .badge.degraded { color: var(--degraded); }
.summary .down, .badge.down { color: var(--down); }
.summary .unknown, .badge.unknown { color: var(--unknown); }
table {
  width: 100%;
  border-collapse: collapse;
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
  background: var(--panel);
}
th {
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  color: var(--muted);
  font-size: 11px;
  font-weight: 600;
  text-align: left;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
td {
  padding: 11px 14px;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
}
tr:last-child td { border-bottom: none; }
td.name { font-weight: 600; white-space: nowrap; }
td.detail { color: var(--muted); }
.badge { font-size: 12px; font-weight: 700; white-space: nowrap; }
section { margin-top: 24px; }
section h2 {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.links ul {
  margin: 0;
  padding: 0;
  list-style: none;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--panel);
  overflow: hidden;
}
.links li {
  display: flex;
  gap: 12px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  align-items: baseline;
}
.links li:last-child { border-bottom: none; }
.links .lname { min-width: 120px; font-weight: 600; }
.links a { color: #58a6ff; text-decoration: none; word-break: break-all; }
.links a:hover { text-decoration: underline; }
footer { margin-top: 28px; color: var(--muted); font-size: 12px; line-height: 1.8; }
"""


def _badge(status: Status) -> str:
    return f'<span class="badge {status.value}">{status.icon} {status.value.upper()}</span>'


def _rows(results: list[Result]) -> str:
    return "\n".join(
        "<tr>"
        f'<td class="name">{html.escape(r.service.name)}</td>'
        f'<td class="status-cell">{_badge(r.status)}</td>'
        f'<td class="detail">{html.escape(r.detail)}</td>'
        "</tr>"
        for r in results
    )


def _summary(results: list[Result]) -> tuple[str, str]:
    counts = {status: sum(r.status is status for r in results) for status in Status}
    source = results[0].source if results else "status page"
    pills = "  ·  ".join(
        f'<span class="{status.value}">{count} {status.value}</span>'
        for status, count in counts.items()
        if count
    )
    return pills, source


def _links(results: list[Result]) -> str:
    unresolved = [r for r in results if r.status is not Status.OK]
    if not unresolved:
        return ""
    items = []
    for result in unresolved:
        for index, link in enumerate(result.service.links):
            name = html.escape(result.service.name) if index == 0 else ""
            items.append(
                "<li>"
                f'<span class="lname">{name}</span>'
                f'<a href="{html.escape(link, quote=True)}" target="_blank" rel="noopener">'
                f"{html.escape(link)}</a>"
                "</li>"
            )
    return '<section class="links"><h2>Look here</h2><ul>' + "".join(items) + "</ul></section>"


def _reports_table(reports: list[Result]) -> str:
    if not reports:
        return ""
    return (
        '<section class="reports"><h2>User reports</h2>'
        "<table><tbody>"
        + _rows(reports)
        + "</tbody></table></section>"
    )


def _page(results: list[Result], reports: list[Result]) -> str:
    generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    summary, source = _summary(results)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>down-check</title>
<style>
{_STYLES}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>down-check</h1>
    <a class="refresh" href="/">Refresh</a>
  </header>
  <p class="meta">updated {generated} · {source}</p>
  <p class="summary">{summary}</p>
  <table>
    <thead>
      <tr><th>Service</th><th>Status</th><th>Detail</th></tr>
    </thead>
    <tbody>
{_rows(results)}
    </tbody>
  </table>
{_reports_table(reports)}
{_links(results)}
  <footer>
    ● OK all is well · ◐ DEGRADED known incident or partial outage
    <br>
    ○ DOWN major outage · · UNKNOWN couldn't read it, here's the link
  </footer>
</div>
</body>
</html>
"""


# ── HTTP server ──────────────────────────────────────────────────────────────


class _Handler(BaseHTTPRequestHandler):
    server_version = "down-check"
    services: list[Service] = []

    def do_GET(self) -> None:
        if self.path != "/":
            self.send_error(404)
            return
        try:
            results, reports = _collect(self.services)
            body = _page(results, reports).encode("utf-8")
            status = 200
        except Exception as exc:  # a flaky check must never take the page down
            body = (
                "<!doctype html><html><body><h1>down-check</h1>"
                f"<p>Something went wrong: {html.escape(str(exc))}</p></body></html>"
            ).encode()
            status = 500
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, msg: str, *args: object) -> None:  # keep the console clean
        return


def serve(services: list[Service], host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    """Run the web view until Ctrl-C. Reachable from any device on the network."""
    _Handler.services = services
    server = ThreadingHTTPServer((host, port), _Handler)
    server.daemon_threads = True
    try:
        lan = _lan_ip()
        print(f"down-check web view on http://{host}:{port} — Ctrl-C to stop")
        print(f"  local:   http://localhost:{port}")
        print(f"  network: http://{lan}:{port}  (open this on your phone)")
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()