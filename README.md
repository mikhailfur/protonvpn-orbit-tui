# Proton Orbit — ProtonVPN TUI

**Your ProtonVPN control deck in the terminal.** A single Python file, an interactive world map, mouse or arrow-key region selection, and animated routes from your location to the server.

[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Textual](https://img.shields.io/badge/TUI-Textual-8b5cf6)](https://textual.textualize.io/)
[![ProtonVPN CLI](https://img.shields.io/badge/protonvpn--cli-1.0.x-6d4aff)](https://protonvpn.com/support/official-linux-client/)

<p align="center">
  <img src="docs/screenshots/orbit-connected.png" alt="Proton Orbit connected to Japan" width="100%">
</p>

> **Important for existing ProtonVPN CLI users:** if you are already signed in, do not run `protonvpn signout` unless you really need to. This is especially critical if you no longer have access to 2FA and cannot sign in again. Proton Orbit never asks for or stores your password or 2FA code. All sign-in and sign-out operations are handled by the official CLI.

---

## Features

- **World map** — 149 regions on a braille map with a Robinson projection and no external map services.
- **Mouse and keyboard** — select a region by clicking, use the arrow keys, or search by name, code, or continent.
- **Beautiful routes** — animated “you → server” arcs, a preview before connecting, a live route, and two-segment Secure Core routes.
- **All main CLI commands** — `connect`, `disconnect`, `status`, `info`, `servers`, `countries`, `cities`, `config`, `signin`, `signout`.
- **All 8 CLI settings** — NetShield, Kill Switch, Port Forwarding, Custom DNS, VPN Accelerator, Moderate NAT, IPv6, Anonymous Crash Reports.
- **AutoConnect** — connect on launch, a preferred region, weighted selection by capacity/load, and **Exclude Regions from Autoconnect**.
- **Cities and Server ID** — connect to a specific city (`--city`) or logical server (`JP#23`).
- **CLI log** — every command and its raw output are available on the Activity screen.
- **Responsive** — from 80×24 to wide terminals; on narrow screens the sidebar is hidden, while all sections remain accessible from the keyboard.

### Screenshots

<p align="center">
  <img src="docs/screenshots/orbit-main.png" alt="Proton Orbit main screen" width="49%">
  <img src="docs/screenshots/orbit-autoconnect.png" alt="AutoConnect with an excluded region" width="49%">
</p>
<p align="center">
  <img src="docs/screenshots/orbit-settings.png" alt="ProtonVPN CLI settings" width="49%">
  <img src="docs/screenshots/orbit-connected.png" alt="Active connection" width="49%">
</p>

*Screenshots were taken with a demo account and a test CLI. No real credentials are present in the repository.*

---

## Requirements

| Component | Version |
|---|---|
| Linux | official ProtonVPN Linux client |
| Python | 3.10+ |
| `protonvpn` CLI | 1.0.x, installed and available in `PATH` |
| Textual | 8.x |
| Rich | 13+ |
| Terminal | 100×30 recommended; 80×24 minimum |

Install the official ProtonVPN Linux client by following [Proton's guide](https://protonvpn.com/support/official-linux-client/). The CLI should respond:

```bash
protonvpn --help
protonvpn status
```

If you are already signed in, **do not touch the sign-in state**. Orbit reads the current state through `protonvpn info` and `protonvpn status`.

---

## Installation

```bash
git clone https://github.com/mikhailfur/protonvpn-orbit-tui.git
cd protonvpn-orbit-tui

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python3 proton_orbit.py
```

Or make the file executable:

```bash
chmod +x proton_orbit.py
./proton_orbit.py
```

If the CLI is installed in a non-standard location:

```bash
PROTONVPN_BIN=/path/to/protonvpn python3 proton_orbit.py
```

---

## Configuration

### Authentication

The TUI never intercepts your password or stores secrets. Sign-in and sign-out are handled by the official `protonvpn` CLI in a separate terminal mode.

- If the CLI is already authenticated, simply launch Orbit.
- If not, open the **ACCOUNT** screen (`I`) and use **SIGN IN VIA CLI**. Enter your password and 2FA code in the CLI terminal.
- You can leave an existing session untouched: `status` and `info` are read-only.

> Do not run `protonvpn signout` if you have lost access to 2FA and cannot sign in again.

### ProtonVPN settings

The **SETTINGS** screen (`S`) reads `protonvpn config list` and applies changes through `protonvpn config set`:

| Setting | Values |
|---|---|
| NetShield | `off`, `malware-only`, `malware-ads-trackers` |
| Kill Switch | `off`, `standard` |
| Port Forwarding | `off`, `on` |
| Custom DNS | `off`, `on --dns 1.1.1.1,8.8.8.8` |
| VPN Accelerator | `off`, `on` |
| Moderate NAT | `off`, `on` |
| IPv6 | `off`, `on` |
| Anonymous Crash Reports | `off`, `on` |

Kill Switch is locked in the UI while a connection is active. Custom DNS and IPv6 take effect on the next connection.

### Route source

The source is determined from the system timezone (`/etc/timezone`) and shown on the map and in the route card. On the **ACCOUNT** screen you can:

- **USE TIMEZONE** — reset the source to the system timezone.
- **REFINE VIA IP** — make a one-time request to `ipinfo.io` to refine the city. The request happens only when you click it, never automatically.

The source only affects route rendering and is not used for the VPN connection.

### AutoConnect and region exclusions

The **AUTOCONNECT** screen (`A`):

- **Autoconnect on launch** — connect when Orbit starts.
- **Preferred region** — always choose this region when it is allowed.
- **Any allowed region** — weighted random selection across allowed regions based on server count and load.
- **Exclusions** — regions that AutoConnect must not choose. Exclusions do not affect manual connections.
- **AUTOCONNECT NOW** — make a selection and connect through the CLI.

Exclusions are saved immediately. The same settings are available via `E` (with focus on the exclusion search).

### Files

```text
~/.config/protonvpn-tui/config.json    # AutoConnect, exclusions, source, filters
~/.cache/protonvpn-tui/server_index.json
~/.cache/Proton/VPN/serverlist.json    # read only for stats and cities
```

The config is created atomically with `600` permissions. It never stores passwords, 2FA codes, or tokens.

---

## Keys

| Key | Action |
|---|---|
| `↑ ↓ ← →` | Select the nearest region in a direction |
| `Enter` | Connect to the selected region/city |
| `C` | Quick Connect: fastest server |
| `D` | Disconnect |
| `F` | Search regions |
| `X` | Cities in the selected region |
| `V` | Connect by Server ID |
| `A` / `E` | AutoConnect / exclusions |
| `S` | CLI settings |
| `I` | Account and source |
| `L` | Activity: CLI commands and output |
| `?` | Help |
| `P` `U` `T` `R` | P2P / Secure Core / Tor / Random |
| `+` `-` `0` | Zoom in / out / reset |
| `Esc` | Close a modal; on the map, reset city/zoom |
| `Q` | Quit |
| Mouse | Click a region, double-click to connect, wheel to zoom |

---

## CLI parity

| CLI | In Orbit |
|---|---|
| `protonvpn signin` / `signout` / `info` | ACCOUNT |
| `protonvpn connect` | ENTER / QUICK / SERVER ID |
| `protonvpn connect --country` | region selection on the map |
| `protonvpn connect --city` | CITIES |
| `protonvpn connect --p2p/--securecore/--tor/--random` | P2P / SECURE / TOR / RANDOM filters |
| `protonvpn disconnect` / `status` | D / background polling |
| `protonvpn servers` | ACCOUNT → link |
| `protonvpn countries list` | catalog loaded at startup |
| `protonvpn cities list` | CITIES |
| `protonvpn config list` / `config set` | SETTINGS |

Orbit does not reimplement VPN logic: all state changes, tunneling, configuration, and authentication go through the installed CLI.

---

## How it works

- A single `proton_orbit.py`; only `textual`, `rich`, and the Python standard library.
- Embedded Natural Earth 110m geography: land outlines and country coordinates; borders are deliberately disabled at world scale.
- Robinson projection, braille rendering, and custom route/marker drawing.
- CLI calls are serialized behind a single lock; background status polling does not spam the log.
- A server index built from the official Proton cache enriches the map with server counts, load, cities, and features.
- AutoConnect picks an allowed region first, then asks the CLI for the fastest server within it.

---

## Known limitations and roadmap

Remaining work is tracked in [GitHub Issues](https://github.com/mikhailfur/protonvpn-orbit-tui/issues):

- [#2 — validate account flows without losing the current session](https://github.com/mikhailfur/protonvpn-orbit-tui/issues/2);
- [#3 — verify Secure Core / Tor / P2P on a real account](https://github.com/mikhailfur/protonvpn-orbit-tui/issues/3);
- [#4 — compact Settings/Account layout for 80×24](https://github.com/mikhailfur/protonvpn-orbit-tui/issues/4);
- [#5 — final footer/sidebar polish and cleanup](https://github.com/mikhailfur/protonvpn-orbit-tui/issues/5);
- [#6 — automated smoke tests with a fake CLI](https://github.com/mikhailfur/protonvpn-orbit-tui/issues/6).

If you are already signed in and do not want to risk your session, do not use sign-out, and test account flows only on a separate test account.

---

## Tests

```bash
python3 -m unittest discover -s tests -v
```

The tests use a temporary fake CLI and never access the real account or credentials.

---

## License

MIT. See [LICENSE](LICENSE).
