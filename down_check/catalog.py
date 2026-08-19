"""The service catalog (services.yaml) and the user's saved selection."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

CATALOG_FILE = Path(__file__).with_name("services.yaml")
SELECTION_FILE = Path.home() / ".down-check" / "selection.json"


@dataclass(frozen=True)
class Service:
    id: str
    name: str
    category: str
    api: str
    page: str
    kind: str = "statuspage"
    # For kind "html": {status: [phrase, ...]} matched against the page banner.
    match: dict[str, list[str]] | None = None
    reports: str | None = None       # istheservicedown.com slug — checked
    downdetector: str | None = None  # downdetector.com slug — linked only

    @property
    def reports_url(self) -> str | None:
        if not self.reports:
            return None
        return f"https://istheservicedown.com/problems/{self.reports}"

    @property
    def downdetector_url(self) -> str | None:
        if not self.downdetector:
            return None
        return f"https://downdetector.com/status/{self.downdetector}/"

    @property
    def links(self) -> list[str]:
        """Where a human should look, most authoritative first."""
        return [url for url in (self.page, self.reports_url, self.downdetector_url) if url]


def load_catalog() -> list[Service]:
    """Return every service shipped in services.yaml, in file order."""
    entries = yaml.safe_load(CATALOG_FILE.read_text()) or []
    return [Service(**entry) for entry in entries]


def by_category(services: list[Service]) -> dict[str, list[Service]]:
    groups: dict[str, list[Service]] = {}
    for service in services:
        groups.setdefault(service.category, []).append(service)
    return groups


def load_selection() -> list[str]:
    """Return the service ids the user picked with `down-check list`."""
    try:
        return json.loads(SELECTION_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return []


def save_selection(ids: list[str]) -> None:
    SELECTION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SELECTION_FILE.write_text(json.dumps(ids, indent=2))


def selected_services() -> list[Service]:
    """Catalog entries the user selected, in catalog order."""
    chosen = set(load_selection())
    return [service for service in load_catalog() if service.id in chosen]
