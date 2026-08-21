# down-check

[![Python](https://img.shields.io/badge/python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-22c55e?style=flat-square)](LICENSE)
[![Services](https://img.shields.io/badge/services-44-8b5cf6?style=flat-square)](down_check/services.yaml)

Is it you, or is the service down? A tiny CLI that checks the services you care about.

```console
$ down-check check

Service        Status      Detail
AWS            ◐ DEGRADED  Increased Packet loss — AWS Direct Connect (Frankfurt)
GitHub         ● OK        All Systems Operational
Google Cloud   ● OK        No open incidents
Grafana Cloud  ◐ DEGRADED  Service Under Maintenance
Slack          ◐ DEGRADED  Trouble Accessing Historical Messages
Stripe         ● OK        All Systems Operational

3 ok  ·  3 degraded  (status page)

Look here:
AWS            https://health.aws.amazon.com/health/status
               https://downdetector.com/status/aws-amazon-web-services/
Grafana Cloud  https://status.grafana.com
Slack          https://slack-status.com
               https://istheservicedown.com/problems/slack
               https://downdetector.com/status/slack/
```

🟢 `OK` all is well · 🟡 `DEGRADED` known incident or partial outage · 🔴 `DOWN` major outage ·
⚪ `UNKNOWN` couldn't read it, here's the link

## Install

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/) (`brew install uv`, or
`curl -LsSf https://astral.sh/uv/install.sh | sh`).

```bash
uv tool install git+https://github.com/MateMauto/down-check && down-check list
```

That installs `down-check` onto your PATH and drops you straight into the picker, so you're set up
in one paste. `pipx install` works the same way. To hack on it, clone and
`uv tool install --editable .`.

```bash
uv tool upgrade down-check      # update
uv tool uninstall down-check    # remove  (rm -rf ~/.down-check to forget your picks)
```

## Use

### `down-check list`

Interactive picker over the catalog. **Just type** to search by name (currently 44 services), 
filtering to `graf` beats arrowing past 20 rows. <kbd>Space</kbd> toggles, <kbd>↑</kbd><kbd>↓</kbd> 
moves, <kbd>Enter</kbd> saves, to `~/.down-check/selection.json`.

### `down-check check`

Checks your selection concurrently against official status pages. Anything not clearly OK is
cross-checked against user reports, and you get the links to look at yourself.

```bash
down-check check          # status pages, with user reports as fallback
down-check check --all    # the whole catalog, ignoring your selection  (-a)
down-check check -r       # skip status pages, go straight to user reports
```

## Where the numbers come from

**Official status pages** are the primary signal, an Atlassian Statuspage `status.json` for most,
plus purpose-built readers for the AWS, Google Cloud, Google Workspace and Azure feeds, Status.io,
Instatus, Meta's product feed, and Slack's own API.

**User reports** come from [istheservicedown.com](https://istheservicedown.com), for when a status
page insists everything is fine and your gut says otherwise. Coverage is consumer-leaning, so only
about a third of the catalog has a page there.

**Scraped pages.** Grok, Mistral and DeepSeek publish no API, so down-check matches phrases against
their status banner. If a redesign breaks the match you get `UNKNOWN` and a link (to try and avoid 
a false `OK`).

**Downdetector** is linked but never fetched. It returns 403 to any plain HTTP client, so down-check
just hands you the URL if you want to check it out.

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

## Debug

**`command not found: down-check`** — the executable isn't on your PATH. Run `uv tool update-shell`
(or `pipx ensurepath`), then open a new terminal.

**Grok, Mistral or DeepSeek always `UNKNOWN`** — those three are scraped, and sit behind bot
protection that rejects old TLS stacks. Check with
`python3 -c "import ssl; print(ssl.OPENSSL_VERSION)"`; if it's OpenSSL 1.1.1 or 3.0, reinstall onto
a newer interpreter: `uv tool install --force --python 3.12 git+https://github.com/MateMauto/down-check`.

**Everything `UNKNOWN`** — you're offline, or behind a proxy that intercepts TLS.

**One service `UNKNOWN`, fine on retry** — a timeout under load. down-check never guesses, so a slow
response reads as unknown rather than OK.

## License

[MIT](LICENSE) — use it, ship it, sell it. Just keep the copyright notice.
