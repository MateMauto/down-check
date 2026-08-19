# down-check

> Is it you, or is the service down? A tiny CLI that checks the services you care about.

```
$ down-check check

Service        Status      Detail
GitHub         ● OK        All Systems Operational
Grafana Cloud  ◐ DEGRADED  Service Under Maintenance
AWS            ◐ DEGRADED  Increased Packet loss — AWS Direct Connect (Frankfurt)
Google Cloud   ● OK        No open incidents
Slack          ◐ DEGRADED  Trouble Accessing Historical Messages
Stripe         ● OK        All Systems Operational

4 ok  ·  3 degraded  (status page)

Service        Status     Detail
Grafana Cloud  · UNKNOWN  No user-report page known
AWS            · UNKNOWN  No user-report page known
Slack          ● OK       No problems detected

1 ok  ·  2 unknown  (user reports)

Look here:
Grafana Cloud  https://status.grafana.com
AWS            https://health.aws.amazon.com/health/status
               https://downdetector.com/status/aws-amazon-web-services/
```

Two commands, no config, no daemon.

## Install

Requires Python 3.10 or newer. The goal is to have `down-check` on your PATH, so you can run it
from any directory the moment something feels off.

### With uv (recommended)

```bash
uv tool install git+https://github.com/MateMauto/down-check
```

### With pipx

```bash
pipx install git+https://github.com/MateMauto/down-check
```

Either one installs the CLI into its own isolated environment and links the executable into your
PATH (`~/.local/bin` by default), so down-check's dependencies can never collide with another
project's. Don't have either? On macOS, `brew install uv` or `brew install pipx`; on Linux,
`curl -LsSf https://astral.sh/uv/install.sh | sh`.

### With pip

```bash
pip install --user git+https://github.com/MateMauto/down-check
```

Works, but shares your user site-packages with everything else you have pip-installed.

> **Not on PyPI yet.** Once it is published, `uv tool install down-check` — no git URL — becomes
> the whole story.

### From a clone, to hack on it

```bash
git clone https://github.com/MateMauto/down-check.git
cd down-check
uv tool install --editable .      # or: pipx install --editable .
```

Editable means your edits to `services.yaml` take effect on the next run, with no reinstall.

### Check it worked

```bash
cd ~                  # anywhere at all
down-check --help
down-check list       # pick your services, once
down-check check
```

### `command not found: down-check`

The executable landed somewhere that is not on your PATH. Fix it once, then open a new terminal:

```bash
uv tool update-shell      # uv
pipx ensurepath           # pipx
```

For `pip install --user`, add the directory printed by `python3 -m site --user-base` (plus `/bin`)
to your PATH in `~/.zshrc` or `~/.bashrc`.

### Upgrading and removing

```bash
uv tool upgrade down-check          # or: pipx upgrade down-check
uv tool uninstall down-check        # or: pipx uninstall down-check
rm -rf ~/.down-check                # also forgets which services you picked
```

## Use

### `down-check list`

Interactive checkbox picker over the built-in catalog.

**Just type** to search by name — with 33 services, filtering to `graf` beats arrowing past 20 rows.
**Space** toggles, **↑↓** moves, **Backspace** narrows the search, **Enter** saves.

Your selection is stored in `~/.down-check/selection.json`.

### `down-check check`

Checks everything you selected, concurrently, against its official status page. Anything that
is not clearly OK gets cross-checked against what users are reporting, and you get the links
to look at yourself.

```bash
down-check check        # status pages, with user reports as fallback
down-check check -r     # skip status pages, go straight to user reports
```

## Where the numbers come from

**Official status pages** are the primary signal — an Atlassian Statuspage `status.json` for most
services, plus purpose-built readers for the AWS health feed, the Google Cloud incident feed, the
Azure status feed, and Slack's own API.

**User reports** come from [istheservicedown.com](https://istheservicedown.com), which answers
plain HTTP requests. This is the fallback for when a status page insists everything is fine and
your gut says otherwise. Coverage is consumer-leaning: about a third of the catalog has a page there.

**Downdetector** is linked, never fetched. It sits behind a bot check that returns 403 to any
plain HTTP client, so down-check hands you the URL rather than pretending to have read it.

## The catalog

Everything lives in [`down_check/services.yaml`](down_check/services.yaml) — 33 services across
dev tools, cloud & hosting, AI, communication, productivity, payments, and media.

Adding one is a few lines:

```yaml
- id: my-api
  name: My API
  category: Internal
  api: https://status.mycompany.com/api/v2/status.json
  page: https://status.mycompany.com
  reports: my-api        # optional, istheservicedown.com slug
  downdetector: my-api   # optional, link only
```

`api` defaults to the Atlassian Statuspage schema. Set `kind` to `aws`, `gcp`, `azure`, `slack`, or
`statusio` for services that don't use it.

## License

[MIT](LICENSE) — use it, ship it, sell it. Just keep the copyright notice.
