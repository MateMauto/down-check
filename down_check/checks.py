"""Status checks: official status pages, with crowd-sourced reports as a fallback."""
from __future__ import annotations

import asyncio
import html
import re
from dataclasses import dataclass
from enum import Enum
from importlib import metadata
from xml.etree import ElementTree

import httpx

from down_check.catalog import Service

TIMEOUT = httpx.Timeout(10.0, connect=5.0)

try:  # running from a checkout, rather than an install, is fine
    _VERSION = metadata.version("down-check")
except metadata.PackageNotFoundError:
    _VERSION = "dev"

USER_AGENT = f"down-check/{_VERSION} (+https://github.com/MateMauto/down-check)"

# istheservicedown.com serves plain HTML, but only to something browser-shaped.
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class Status(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"
    UNKNOWN = "unknown"

    @property
    def icon(self) -> str:
        return {"ok": "●", "degraded": "◐", "down": "○", "unknown": "·"}[self.value]

    @property
    def style(self) -> str:
        return {
            "ok": "bold green",
            "degraded": "bold yellow",
            "down": "bold red",
            "unknown": "dim",
        }[self.value]


@dataclass
class Result:
    service: Service
    status: Status
    detail: str
    source: str  # "status page" | "user reports"

    @property
    def is_problem(self) -> bool:
        return self.status is not Status.OK


def _result(service: Service, status: Status, detail: str) -> Result:
    return Result(service, status, detail, "status page")


# ── Official status pages ────────────────────────────────────────────────────

# Atlassian Statuspage indicator → our status level.
_INDICATOR = {
    "none": Status.OK,
    "minor": Status.DEGRADED,
    "maintenance": Status.DEGRADED,
    "major": Status.DOWN,
    "critical": Status.DOWN,
}


async def _statuspage(client: httpx.AsyncClient, service: Service) -> Result:
    """Read an Atlassian Statuspage `/api/v2/status.json` endpoint."""
    data = await _get_json(client, service.api)
    if not isinstance(data, dict):
        return _result(service, Status.UNKNOWN, "Status page unreachable")

    status = data.get("status") or {}
    indicator = str(status.get("indicator", "")).lower()
    detail = status.get("description") or "No description"
    return _result(service, _INDICATOR.get(indicator, Status.UNKNOWN), detail)


async def _aws(client: httpx.AsyncClient, service: Service) -> Result:
    """Read the AWS health feed — a list of recent events, `status` 1/2 = open."""
    data = await _get_json(client, service.api)
    if not isinstance(data, list):
        return _result(service, Status.UNKNOWN, "Health feed unreachable")

    open_events = [event for event in data if str(event.get("status")) in {"1", "2"}]
    if not open_events:
        return _result(service, Status.OK, "No open events")

    first = open_events[0]
    detail = f"{first.get('summary', 'Open event')} — {first.get('service_name', '?')}"
    if first.get("region_name"):
        detail += f" ({first['region_name']})"
    detail += _and_more(len(open_events))

    disruption = any(str(event.get("status")) == "2" for event in open_events)
    return _result(service, Status.DOWN if disruption else Status.DEGRADED, detail)


async def _gcp(client: httpx.AsyncClient, service: Service) -> Result:
    """Read the Google Cloud incident feed — an incident is open until it has an `end`."""
    data = await _get_json(client, service.api)
    if not isinstance(data, list):
        return _result(service, Status.UNKNOWN, "Incident feed unreachable")

    open_incidents = [incident for incident in data if not incident.get("end")]
    if not open_incidents:
        return _result(service, Status.OK, "No open incidents")

    first = open_incidents[0]
    # These descriptions are markdown with hard newlines; flatten for one table cell.
    raw = first.get("external_desc") or "Open incident"
    detail = _summarize(raw) + _and_more(len(open_incidents))

    high = any(i.get("severity") == "high" for i in open_incidents)
    return _result(service, Status.DOWN if high else Status.DEGRADED, detail)


async def _slack(client: httpx.AsyncClient, service: Service) -> Result:
    """Read Slack's own status API — `active_incidents` is empty when all is well."""
    data = await _get_json(client, service.api)
    if not isinstance(data, dict):
        return _result(service, Status.UNKNOWN, "Status API unreachable")

    incidents = data.get("active_incidents") or []
    if not incidents:
        return _result(service, Status.OK, "No active incidents")

    detail = incidents[0].get("title") or "Active incident"
    return _result(service, Status.DEGRADED, detail + _and_more(len(incidents)))


# Status.io severity codes: 100 operational, 200 maintenance, 300 degraded,
# 400 partial disruption, 500 disruption, 600 security event.
_STATUSIO = {100: Status.OK, 200: Status.DEGRADED, 300: Status.DEGRADED,
             400: Status.DEGRADED, 500: Status.DOWN, 600: Status.DOWN}


async def _statusio(client: httpx.AsyncClient, service: Service) -> Result:
    """Read a Status.io page — the platform GitLab and friends run on."""
    data = await _get_json(client, service.api)
    if not isinstance(data, dict):
        return _result(service, Status.UNKNOWN, "Status API unreachable")

    overall = (data.get("result") or {}).get("status_overall") or {}
    code = overall.get("status_code")
    detail = overall.get("status") or "No description"
    return _result(service, _STATUSIO.get(code, Status.UNKNOWN), detail)


# Instatus reports one word for the whole page.
_INSTATUS = {
    "UP": Status.OK,
    "HASISSUES": Status.DEGRADED,
    "UNDERMAINTENANCE": Status.DEGRADED,
}


async def _instatus(client: httpx.AsyncClient, service: Service) -> Result:
    """Read an Instatus `summary.json` — `page.status` is UP / HASISSUES / …"""
    data = await _get_json(client, service.api)
    if not isinstance(data, dict):
        return _result(service, Status.UNKNOWN, "Status page unreachable")

    state = str((data.get("page") or {}).get("status", "")).upper()
    detail = {"UP": "All systems up", "HASISSUES": "Reported issues",
              "UNDERMAINTENANCE": "Under maintenance"}.get(state, state or "No description")
    return _result(service, _INSTATUS.get(state, Status.UNKNOWN), detail)


async def _meta(client: httpx.AsyncClient, service: Service) -> Result:
    """Read metastatus.com's orgs feed — every product carries its own status string."""
    data = await _get_json(client, service.api)
    if not isinstance(data, list):
        return _result(service, Status.UNKNOWN, "Status feed unreachable")

    troubled = [
        (org.get("name", "?"), svc)
        for org in data
        for svc in org.get("services", [])
        if svc.get("status") and svc["status"] != "No known issues"
    ]
    if not troubled:
        return _result(service, Status.OK, "No known issues")

    org_name, svc = troubled[0]
    detail = f"{svc['status']} — {org_name}: {svc.get('name', '?')}"
    return _result(service, Status.DEGRADED, detail + _and_more(len(troubled)))


# Pages with no API at all. We read the banner text and, crucially, fall back to
# UNKNOWN rather than OK when nothing matches — a redesign must never read as "fine".
_TAGS = re.compile(r"<(script|style)[^>]*>.*?</\1>|<[^>]+>", re.S)
_BANNER_CHARS = 800


async def _html(client: httpx.AsyncClient, service: Service) -> Result:
    """Match phrases from the catalog against a status page's banner text."""
    page = await _get_text(client, service.api)
    if page is None:
        return _result(service, Status.UNKNOWN, "Status page unreachable")

    banner = " ".join(html.unescape(_TAGS.sub(" ", page)).split())[:_BANNER_CHARS].lower()
    rules = service.match or {}
    for level in (Status.DOWN, Status.DEGRADED, Status.OK):  # most severe wins
        for phrase in rules.get(level.value, []):
            if phrase.lower() in banner:
                return _result(service, level, phrase)

    return _result(service, Status.UNKNOWN, "Could not read the page — open the link")


async def _azure(client: httpx.AsyncClient, service: Service) -> Result:
    """Read the Azure status RSS feed — it carries one item per active issue."""
    text = await _get_text(client, service.api)
    if text is None:
        return _result(service, Status.UNKNOWN, "Status feed unreachable")

    try:
        items = ElementTree.fromstring(text).findall("./channel/item")
    except ElementTree.ParseError:
        return _result(service, Status.UNKNOWN, "Could not read the status feed")

    if not items:
        return _result(service, Status.OK, "No active issues")

    title = items[0].findtext("title") or "Active issue"
    return _result(service, Status.DEGRADED, title.strip() + _and_more(len(items)))


def _summarize(text: str, limit: int = 110) -> str:
    """Google's incident text is a markdown essay; keep the first sentence."""
    flat = " ".join(text.replace("*", "").split()).removeprefix("Summary ")
    first = flat.split(". ")[0].rstrip(".")
    return first if len(first) <= limit else first[: limit - 1].rstrip() + "…"


def _and_more(count: int) -> str:
    return f" +{count - 1} more" if count > 1 else ""


_CHECKERS = {
    "statuspage": _statuspage,
    "aws": _aws,
    "gcp": _gcp,
    "slack": _slack,
    "statusio": _statusio,
    "instatus": _instatus,
    "meta": _meta,
    "html": _html,
    "azure": _azure,
}


async def check_all(services: list[Service]) -> list[Result]:
    """Check every service concurrently against its official status page."""
    async with httpx.AsyncClient(
        timeout=TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        checkers = [_CHECKERS.get(s.kind, _statuspage)(client, s) for s in services]
        return list(await asyncio.gather(*checkers))


async def _get_json(client: httpx.AsyncClient, url: str) -> dict | list | None:
    try:
        response = await client.get(url, headers={"Accept": "application/json"})
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError):
        return None


async def _get_text(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        response = await client.get(url)
        response.raise_for_status()
        return response.text
    except httpx.HTTPError:
        return None


# ── User reports (istheservicedown.com) ──────────────────────────────────────

# The page leads with a verdict, e.g.
#   <p class="... font-medium ...">Problems detected</p>
#   <p class="... text-secondary">Users are reporting problems related to: …</p>
_VERDICT = re.compile(
    r'<p class="[^"]*font-medium[^"]*">\s*(?P<headline>[^<]+?)\s*</p>\s*'
    r'<p class="[^"]*text-secondary[^"]*">\s*(?P<detail>[^<]+?)\s*</p>'
)


async def check_reports(services: list[Service]) -> list[Result]:
    """Ask istheservicedown.com what users are reporting, concurrently."""
    async with httpx.AsyncClient(
        timeout=TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": BROWSER_UA, "Accept": "text/html"},
    ) as client:
        return list(await asyncio.gather(*(_reports(client, s) for s in services)))


def _unknown(service: Service, detail: str) -> Result:
    return Result(service, Status.UNKNOWN, detail, "user reports")


async def _reports(client: httpx.AsyncClient, service: Service) -> Result:
    url = service.reports_url
    if url is None:
        return _unknown(service, "No user-report page known")

    try:
        response = await client.get(url)
    except httpx.HTTPError:
        return _unknown(service, "istheservicedown.com unreachable")

    if response.status_code >= 400:
        return _unknown(service, f"istheservicedown.com HTTP {response.status_code}")

    match = _VERDICT.search(response.text)
    if match is None:
        return _unknown(service, "Could not read the page — open the link")

    headline = html.unescape(match.group("headline"))
    detail = html.unescape(match.group("detail"))
    lowered = headline.lower()
    if "no problems" in lowered:
        status = Status.OK
    elif "possible" in lowered or "some problems" in lowered:
        status = Status.DEGRADED
    elif "problems" in lowered:
        status = Status.DOWN
    else:
        status = Status.UNKNOWN

    # When all is well the second line is just boilerplate ("submit a report below").
    summary = headline if status is Status.OK else f"{headline} — {detail}"
    return Result(service, status, summary, "user reports")
