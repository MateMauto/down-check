# down-check

[![Python](https://img.shields.io/badge/python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-22c55e?style=flat-square)](LICENSE)
[![Services](https://img.shields.io/badge/services-44-8b5cf6?style=flat-square)](down_check/services.yaml)

Is it you, or is the service down? A tiny CLI that checks the services you care about — two
commands, no config, no daemon.

```console
$ down-check check

Service        Status      Detail
GitHub         ● OK        All Systems Operational
Grafana Cloud  ◐ DEGRADED  Service Under Maintenance
AWS            ◐ DEGRADED  Increased Packet loss — AWS Direct Connect (Frankfurt)
Google Cloud   ● OK        No open incidents
Slack          ◐ DEGRADED  Trouble Accessing Historical Messages
Stripe         ● OK        All Systems Operational

4 ok  ·  3 degraded  (status page)

Look here:
Grafana Cloud  https://status.grafana.com
AWS            https://health.aws.amazon.com/health/status
               https://downdetector.com/status/aws-amazon-web-services/
```

🟢 `OK` all is well · 🟡 `DEGRADED` known incident or partial outage · 🔴 `DOWN` major outage ·
⚪ `UNKNOWN` couldn't read it, here's the link

## Install

Requires Python 3.10+. The point is to have `down-check` on your PATH, ready from any directory.

```bash
# with uv (recommended)
uv tool install git+https://github.com/MateMauto/down-check && down-check list

# with pipx
pipx install git+https://github.com/MateMauto/down-check && down-check list
```

The second half drops you into the picker, so you're set up in one paste. Both tools isolate
down-check's dependencies and link the executable into `~/.local/bin`. Missing them? macOS:
`brew install uv`. Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`.

`pip install --user git+https://github.com/MateMauto/down-check` also works, but shares your user
site-packages with everything else.

> [!NOTE]
> Not on PyPI yet — once it is, `uv tool install down-check` becomes the whole story.

To hack on it, clone and `uv tool install --editable .` — edits to `services.yaml` then apply on the
next run, with no reinstall.

**`command not found`?** Run `uv tool update-shell` or `pipx ensurepath`, then open a new terminal.
For `pip install --user`, add the directory from `python3 -m site --user-base` (plus `/bin`) to your
PATH.

**Old OpenSSL?** The three scraped AI pages (Grok, Mistral, DeepSeek) sit behind TLS-fingerprint bot
protection that rejects OpenSSL 1.1.1 and 3.0 outright, so they report `UNKNOWN` no matter what the
service is doing. Check with `python3 -c "import ssl; print(ssl.OPENSSL_VERSION)"`; if it's old,
install onto a newer interpreter with `uv tool install --python 3.12 …`.

Upgrade with `uv tool upgrade down-check`, remove with `uv tool uninstall down-check`
(and `rm -rf ~/.down-check` to forget your picks).

## Use

### `down-check list`

Interactive picker over the catalog. **Just type** to search by name — with 44 services, filtering
to `graf` beats arrowing past 20 rows. <kbd>Space</kbd> toggles, <kbd>↑</kbd><kbd>↓</kbd> moves,
<kbd>Enter</kbd> saves, to `~/.down-check/selection.json`.

### `down-check check`

Checks your selection concurrently against official status pages. Anything not clearly OK is
cross-checked against user reports, and you get the links to look at yourself.

```bash
down-check check          # status pages, with user reports as fallback
down-check check --all    # the whole catalog, ignoring your selection  (-a)
down-check check -r       # skip status pages, go straight to user reports
```

`--all` is the "is the whole internet on fire?" button. It doesn't change what you picked.

## Where the numbers come from

**Official status pages** are the primary signal — an Atlassian Statuspage `status.json` for most,
plus purpose-built readers for the AWS, Google Cloud, Google Workspace and Azure feeds, Status.io,
Instatus, Meta's product feed, and Slack's own API.

**User reports** come from [istheservicedown.com](https://istheservicedown.com), for when a status
page insists everything is fine and your gut says otherwise. Coverage is consumer-leaning: about a
third of the catalog has a page there.

**Scraped pages.** Grok, Mistral and DeepSeek publish no API, so down-check matches phrases against
their status banner. If a redesign breaks the match you get `UNKNOWN` and a link — never a false `OK`.

**Downdetector** is linked, never fetched: it returns 403 to any plain HTTP client, so down-check
hands you the URL rather than pretending to have read it.

## The catalog

44 services in [`down_check/services.yaml`](down_check/services.yaml), across dev tools, cloud,
AI, communication, productivity, payments and media. Adding one is a few lines:

```yaml
- id: my-api
  name: My API
  category: Internal
  api: https://status.mycompany.com/api/v2/status.json
  page: https://status.mycompany.com
  reports: my-api        # optional, istheservicedown.com slug
  downdetector: my-api   # optional, link only
```

`api` defaults to the Atlassian Statuspage schema. Set `kind` to `aws`, `gcp`, `azure`, `slack`,
`statusio`, `instatus` or `meta` for services with their own feed, or `html` (plus a `match:` block
of phrases) for those with no API at all.

## License

[MIT](LICENSE) — use it, ship it, sell it. Just keep the copyright notice.
